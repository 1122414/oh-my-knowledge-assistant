from omka.app.agents.base import AgentContext, AgentResponse, BaseAgent
from omka.app.agents.prompts import SYSTEM_PROMPT, build_user_prompt
from omka.app.core.config import settings
from omka.app.core.logging import get_logger, trace
from omka.app.pipeline.summarizer import LLMClient

logger = get_logger("agent")


class SimpleKnowledgeAgent(BaseAgent):
    """简单知识问答 Agent"""

    def __init__(self):
        self._llm = LLMClient()

    @trace("agent")
    async def answer(self, context: AgentContext) -> AgentResponse:
        """根据上下文生成回答

        Args:
            context: Agent 上下文

        Returns:
            Agent 响应
        """
        try:
            messages = self._build_messages(context)
            response_text = await self._llm.chat(
                messages=messages,
                temperature=settings.omka_agent_temperature,
                max_tokens=2000,
            )

            used_context = self._extract_used_context(context)
            suggested_actions = self._suggest_actions(context)

            return AgentResponse(
                answer=response_text,
                used_context=used_context,
                suggested_actions=suggested_actions,
            )
        except Exception as e:
            logger.error("Agent 回答失败 | error=%s", e)
            return AgentResponse(
                answer="我刚才处理你的问题时失败了。你可以稍后再试，或者使用 /omka latest 查看最新简报。",
                used_context=[],
                suggested_actions=["/omka latest", "/omka help"],
            )

    def _build_messages(self, context: AgentContext) -> list[dict[str, str]]:
        """构建 LLM 消息列表"""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        for msg in context.recent_messages:
            messages.append(msg)

        user_prompt = build_user_prompt(
            user_message=context.user_message,
            interests=context.user_profile.get("interests", ""),
            projects=context.user_profile.get("projects", ""),
            recent_messages=self._format_recent_messages(context.recent_messages),
            digest_items=self._format_digest_items(context.digest_items),
            knowledge_items=self._format_knowledge_items(context.knowledge_items),
            candidate_items=self._format_candidate_items(context.candidate_items),
            memory_items=self._format_memory_items(context.memory_items),
        )
        messages.append({"role": "user", "content": user_prompt})

        return messages

    def _format_recent_messages(self, messages: list[dict[str, str]]) -> str:
        """格式化最近消息"""
        if not messages:
            return ""

        lines = []
        for msg in messages[-6:]:
            role = "用户" if msg.get("role") == "user" else "助手"
            lines.append(f"{role}: {msg.get('content', '')[:200]}")
        return "\n".join(lines)

    def _format_digest_items(self, items: list[dict[str, str]]) -> str:
        """格式化 Digest 条目"""
        if not items:
            return "暂无"

        lines = []
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. {item.get('title', '')}")
            if item.get("summary"):
                lines.append(f"   摘要: {item['summary'][:100]}")
        return "\n".join(lines)

    def _format_knowledge_items(self, items: list[dict[str, str]]) -> str:
        """格式化知识条目"""
        if not items:
            return "暂无"

        lines = []
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. {item.get('title', '')}")
            if item.get("tags"):
                lines.append(f"   标签: {item['tags']}")
        return "\n".join(lines)

    def _format_candidate_items(self, items: list[dict[str, str]]) -> str:
        """格式化候选条目"""
        if not items:
            return "暂无"

        lines = []
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. {item.get('title', '')} (分数: {item.get('score', '0')})")
            if item.get("summary"):
                lines.append(f"   摘要: {item['summary'][:100]}")
        return "\n".join(lines)

    def _format_memory_items(self, items: list[dict[str, str]]) -> str:
        if not items:
            return "暂无"

        lines = []
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. [{item.get('type', '')}] {item.get('subject', '')}")
            if item.get("content"):
                lines.append(f"   {item['content'][:100]}")
        return "\n".join(lines)

    def _extract_used_context(self, context: AgentContext) -> list[dict[str, str]]:
        used = []

        if context.memory_items:
            used.append({"type": "memory", "count": str(len(context.memory_items))})
        if context.digest_items:
            used.append({"type": "digest", "count": str(len(context.digest_items))})
        if context.knowledge_items:
            used.append({"type": "knowledge", "count": str(len(context.knowledge_items))})
        if context.candidate_items:
            used.append({"type": "candidate", "count": str(len(context.candidate_items))})

        return used

    def _suggest_actions(self, context: AgentContext) -> list[str]:
        """建议下一步动作"""
        actions = []

        if context.digest_items:
            actions.append("/omka latest")
        if context.candidate_items:
            actions.append("查看候选内容")
        if not actions:
            actions.append("/omka help")

        return actions
