from omka.app.agents.base import AgentContext
from omka.app.agents.tracing import AgentRunTracer, format_exception
from omka.app.core.config import settings
from omka.app.core.logging import get_logger, trace
from omka.app.storage.db import (
    CandidateItem,
    ConversationMessage,
    KnowledgeItem,
    get_session,
)
from sqlmodel import col, select

logger = get_logger("agent")


class ContextBuilder:
    """Agent 上下文构建器"""

    def __init__(
        self,
        max_recent_messages: int = 6,
        max_digest_items: int = 5,
        max_knowledge_items: int = 5,
        max_candidate_items: int = 5,
        max_memory_items: int = 5,
        max_context_chars: int = 12000,
    ):
        self.max_recent_messages = max_recent_messages
        self.max_digest_items = max_digest_items
        self.max_knowledge_items = max_knowledge_items
        self.max_candidate_items = max_candidate_items
        self.max_memory_items = max_memory_items
        self.max_context_chars = max_context_chars

    @trace("agent")
    async def build(
        self,
        user_message: str,
        conversation_id: str,
        user_external_id: str,
        tracer: AgentRunTracer | None = None,
        task_brief: dict | None = None,
    ) -> AgentContext:
        retrieval_query = self._retrieval_query(user_message, task_brief)
        recent_messages = self._collect_stage(
            tracer,
            stage_name="context.recent_messages",
            input_json={"conversation_id": conversation_id},
            collector=lambda: self._get_recent_messages(conversation_id),
        )
        digest_items = self._collect_stage(
            tracer,
            stage_name="context.daily_digest",
            input_json={"limit": self.max_digest_items},
            collector=self._get_latest_digest_items,
        )
        knowledge_items = self._collect_stage(
            tracer,
            stage_name="context.knowledge",
            input_json={
                "query": user_message,
                "interpreted_query": retrieval_query,
                "limit": self.max_knowledge_items,
            },
            collector=lambda: self._search_knowledge(retrieval_query),
        )
        candidate_items = self._collect_stage(
            tracer,
            stage_name="context.candidates",
            input_json={
                "query": user_message,
                "interpreted_query": retrieval_query,
                "limit": self.max_candidate_items,
            },
            collector=lambda: self._search_candidates(retrieval_query),
        )
        memory_items = self._collect_stage(
            tracer,
            stage_name="context.memory",
            input_json={
                "query": user_message,
                "interpreted_query": retrieval_query,
                "owner_external_id": user_external_id,
                "conversation_id": conversation_id,
                "limit": self.max_memory_items,
            },
            collector=lambda: self._get_active_memories(
                user_external_id=user_external_id,
                conversation_id=conversation_id,
                query_text=retrieval_query,
            ),
        )
        user_profile = self._collect_stage(
            tracer,
            stage_name="context.profile",
            input_json={"owner_external_id": user_external_id},
            collector=lambda: self._get_user_profile(user_external_id),
        )

        context = AgentContext(
            user_message=user_message,
            conversation_id=conversation_id,
            user_external_id=user_external_id,
            recent_messages=recent_messages,
            digest_items=digest_items,
            knowledge_items=knowledge_items,
            candidate_items=candidate_items,
            memory_items=memory_items,
            user_profile=user_profile,
            task_brief=task_brief or {},
        )

        trim_span = (
            tracer.start(
                step_type="context",
                stage_name="context.assemble",
                input_json={
                    "max_context_chars": self.max_context_chars,
                    "counts_before_trim": self._context_counts(context),
                    "chars_before_trim": self._context_size(context),
                },
            )
            if tracer
            else None
        )
        trimmed = self._trim_context(context)
        if tracer and trim_span:
            tracer.finish(
                trim_span,
                output_json={
                    "counts": self._context_counts(trimmed),
                    "total_chars": self._context_size(trimmed),
                },
            )
        return trimmed

    def _collect_stage(
        self,
        tracer: AgentRunTracer | None,
        *,
        stage_name: str,
        input_json: dict,
        collector,
    ):
        if not tracer:
            return collector()

        span = tracer.start(
            step_type="context",
            stage_name=stage_name,
            input_json=input_json,
        )
        try:
            result = collector()
        except Exception as exc:
            error_message = format_exception(exc)
            tracer.finish(
                span,
                status="failed",
                error_message=error_message,
            )
            raise

        tracer.finish(
            span,
            output_json=self._trace_output(result),
        )
        return result

    @classmethod
    def _trace_output(cls, result) -> dict:
        if isinstance(result, list):
            return {
                "count": len(result),
                "items": cls._preview_trace_value(result),
            }
        if isinstance(result, dict):
            return {
                "count": len(result),
                "data": cls._preview_trace_value(result),
            }
        return {"value": cls._preview_trace_value(result)}

    @classmethod
    def _preview_trace_value(cls, value):
        if isinstance(value, str):
            return value if len(value) <= 500 else value[:500] + "…"
        if isinstance(value, list):
            return [cls._preview_trace_value(item) for item in value[:10]]
        if isinstance(value, dict):
            return {
                str(key): cls._preview_trace_value(item)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _context_counts(context: AgentContext) -> dict[str, int]:
        return {
            "recent_messages": len(context.recent_messages),
            "digest_items": len(context.digest_items),
            "knowledge_items": len(context.knowledge_items),
            "candidate_items": len(context.candidate_items),
            "memory_items": len(context.memory_items),
            "profile_fields": len(context.user_profile),
        }

    def _get_recent_messages(self, conversation_id: str) -> list[dict[str, str]]:
        """获取最近对话消息"""
        try:
            with get_session() as session:
                messages = session.exec(
                    select(ConversationMessage)
                    .where(ConversationMessage.conversation_id == conversation_id)
                    .order_by(col(ConversationMessage.created_at).desc())
                    .limit(self.max_recent_messages)
                ).all()

                return [
                    {"role": msg.role, "content": msg.content}
                    for msg in reversed(messages)
                ]
        except Exception as e:
            logger.error("获取最近消息失败 | error=%s", e)
            return []

    def _get_latest_digest_items(self) -> list[dict[str, str]]:
        """获取最新 Digest 条目"""
        try:
            digests_dir = settings.digests_dir
            if not digests_dir.exists():
                return []

            md_files = sorted(digests_dir.glob("*.md"), reverse=True)
            if not md_files:
                return []

            content = md_files[0].read_text(encoding="utf-8")
            items = []
            current_title = None

            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("## ") and stripped[3:4].isdigit():
                    current_title = stripped[3:]
                elif stripped.startswith("- **摘要**:") and current_title:
                    summary = stripped[len("- **摘要**:"):].strip()
                    if summary:
                        items.append({"title": current_title, "summary": summary})
                        current_title = None
                        if len(items) >= self.max_digest_items:
                            break

            return items
        except Exception as e:
            logger.error("获取最新 Digest 失败 | error=%s", e)
            return []

    def _search_knowledge(self, query: str) -> list[dict[str, str]]:
        """搜索已收藏知识"""
        try:
            keywords = self._extract_keywords(query)
            if not keywords:
                return self._get_recent_knowledge()

            with get_session() as session:
                items = session.exec(
                    select(KnowledgeItem)
                    .order_by(col(KnowledgeItem.created_at).desc())
                    .limit(100)
                ).all()

                scored = []
                for item in items:
                    score = self._calculate_relevance(
                        keywords,
                        f"{item.title} {item.summary or ''} {' '.join(item.tags or [])}",
                    )
                    if score > 0:
                        scored.append((score, item))

                scored.sort(key=lambda x: x[0], reverse=True)
                return [
                    {
                        "id": item.id,
                        "title": item.title,
                        "summary": (item.summary or "")[:200],
                        "tags": ", ".join(item.tags or []),
                        "url": item.url,
                    }
                    for _, item in scored[:self.max_knowledge_items]
                ]
        except Exception as e:
            logger.error("搜索知识库失败 | error=%s", e)
            return []

    def _get_recent_knowledge(self) -> list[dict[str, str]]:
        """获取最近收藏的知识"""
        try:
            with get_session() as session:
                items = session.exec(
                    select(KnowledgeItem)
                    .order_by(col(KnowledgeItem.created_at).desc())
                    .limit(self.max_knowledge_items)
                ).all()

                return [
                    {
                        "id": item.id,
                        "title": item.title,
                        "summary": (item.summary or "")[:200],
                        "tags": ", ".join(item.tags or []),
                        "url": item.url,
                    }
                    for item in items
                ]
        except Exception as e:
            logger.error("获取最近知识失败 | error=%s", e)
            return []

    def _search_candidates(self, query: str) -> list[dict[str, str]]:
        """搜索候选内容"""
        try:
            keywords = self._extract_keywords(query)
            if not keywords:
                return self._get_top_candidates()

            with get_session() as session:
                items = session.exec(
                    select(CandidateItem)
                    .where(CandidateItem.status == "pending")
                    .order_by(col(CandidateItem.score).desc())
                    .limit(100)
                ).all()

                scored = []
                for item in items:
                    score = self._calculate_relevance(
                        keywords,
                        f"{item.title} {item.summary or ''} {' '.join(item.matched_interests or [])}",
                    )
                    if score > 0:
                        scored.append((score, item))

                scored.sort(key=lambda x: x[0], reverse=True)
                return [
                    {
                        "id": item.id,
                        "title": item.title,
                        "summary": (item.summary or "")[:200],
                        "score": str(item.score),
                        "url": item.url,
                    }
                    for _, item in scored[:self.max_candidate_items]
                ]
        except Exception as e:
            logger.error("搜索候选失败 | error=%s", e)
            return []

    def _get_top_candidates(self) -> list[dict[str, str]]:
        """获取排名最高的候选"""
        try:
            with get_session() as session:
                items = session.exec(
                    select(CandidateItem)
                    .where(CandidateItem.status == "pending")
                    .order_by(col(CandidateItem.score).desc())
                    .limit(self.max_candidate_items)
                ).all()

                return [
                    {
                        "id": item.id,
                        "title": item.title,
                        "summary": (item.summary or "")[:200],
                        "score": str(item.score),
                        "url": item.url,
                    }
                    for item in items
                ]
        except Exception as e:
            logger.error("获取 top 候选失败 | error=%s", e)
            return []

    def _get_active_memories(
        self,
        user_external_id: str,
        conversation_id: str,
        query_text: str,
    ) -> list[dict[str, str]]:
        try:
            from omka.app.services.memory_service import MemoryService

            memories = MemoryService.get_active_memories_for_context(
                owner_external_id=user_external_id,
                conversation_id=conversation_id,
                query_text=query_text,
                max_items=self.max_memory_items,
            )
            MemoryService.mark_memories_used([memory.id for memory in memories])
            return [
                {
                    "id": m.id,
                    "type": m.memory_type,
                    "subject": m.subject,
                    "content": m.content[:200] if len(m.content) > 200 else m.content,
                    "source_ref": m.source_ref or "",
                }
                for m in memories
            ]
        except Exception as e:
            logger.error("获取活跃记忆失败 | error=%s", e)
            return []

    def _get_user_profile(self, user_external_id: str) -> dict[str, str]:
        """获取带证据与置信度的用户画像上下文。"""
        try:
            from omka.app.services.user_profile_service import UserProfileService

            snapshot = UserProfileService.build_snapshot(user_external_id)
            return snapshot.to_context()
        except Exception as e:
            logger.error("获取用户配置失败 | error=%s", e)
            return {}

    @staticmethod
    def _retrieval_query(user_message: str, task_brief: dict | None) -> str:
        if not task_brief:
            return user_message
        parts = [str(task_brief.get("goal") or user_message)]
        entities = task_brief.get("entities")
        if isinstance(entities, list):
            parts.extend(str(entity) for entity in entities if str(entity).strip())
        return " ".join(dict.fromkeys(parts))

    def _extract_keywords(self, text: str) -> list[str]:
        """从文本中提取关键词"""
        stop_words = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}
        words = text.replace("？", " ").replace("?", " ").replace("！", " ").replace("!", " ").replace("，", " ").replace(",", " ").replace("。", " ").replace(".", " ").split()
        return [w for w in words if len(w) > 1 and w not in stop_words]

    def _calculate_relevance(self, keywords: list[str], text: str) -> int:
        """计算关键词相关性分数"""
        text_lower = text.lower()
        score = 0
        for keyword in keywords:
            if keyword.lower() in text_lower:
                score += 1
        return score

    def _trim_context(self, context: AgentContext) -> AgentContext:
        total_chars = self._context_size(context)

        if total_chars <= self.max_context_chars:
            return context

        while total_chars > self.max_context_chars:
            if context.candidate_items:
                removed = context.candidate_items.pop()
                total_chars -= len(removed.get("title", "") + removed.get("summary", ""))
            elif context.memory_items:
                removed = context.memory_items.pop()
                total_chars -= len(removed.get("content", ""))
            elif context.knowledge_items:
                removed = context.knowledge_items.pop()
                total_chars -= len(removed.get("title", "") + removed.get("summary", ""))
            elif context.digest_items:
                removed = context.digest_items.pop()
                total_chars -= len(removed.get("title", "") + removed.get("summary", ""))
            elif context.recent_messages:
                removed = context.recent_messages.pop(0)
                total_chars -= len(removed.get("content", ""))
            else:
                break

        return context

    @staticmethod
    def _context_size(context: AgentContext) -> int:
        total_chars = len(context.user_message)
        total_chars += sum(
            len(message.get("content", ""))
            for message in context.recent_messages
        )
        total_chars += sum(
            len(item.get("title", "") + item.get("summary", ""))
            for item in context.digest_items
        )
        total_chars += sum(
            len(item.get("title", "") + item.get("summary", ""))
            for item in context.knowledge_items
        )
        total_chars += sum(
            len(item.get("title", "") + item.get("summary", ""))
            for item in context.candidate_items
        )
        total_chars += sum(
            len(item.get("content", ""))
            for item in context.memory_items
        )
        return total_chars
