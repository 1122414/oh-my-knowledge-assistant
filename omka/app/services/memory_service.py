from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlmodel import col, func, select

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.storage.db import MemoryEvent, MemoryItem, get_session


def generate_memory_id() -> str:
    import uuid
    return f"mem_{uuid.uuid4().hex[:16]}"


class MemoryService:
    """记忆服务：提供记忆的 CRUD、查询和生命周期管理"""

    @staticmethod
    def create_memory(
        memory_type: str,
        subject: str,
        content: str,
        scope: str = "global",
        owner_external_id: str | None = None,
        conversation_id: str | None = None,
        summary: str | None = None,
        source_type: str = "manual",
        source_ref: str | None = None,
        confidence: float = 0.8,
        importance: float = 0.5,
        status: str = "active",
        tags: list[str] | None = None,
        metadata_json: dict | None = None,
        expires_at: datetime | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MemoryItem:
        memory = MemoryItem(
            id=generate_memory_id(),
            memory_type=memory_type,
            scope=scope,
            owner_external_id=owner_external_id,
            conversation_id=conversation_id,
            subject=subject,
            content=content,
            summary=summary,
            source_type=source_type,
            source_ref=source_ref,
            confidence=confidence,
            importance=importance,
            status=status,
            tags=tags or [],
            metadata_json=metadata_json or {},
            expires_at=expires_at,
        )
        with get_session() as session:
            session.add(memory)
            session.commit()
            session.refresh(memory)

        MemoryService._log_event(
            memory.id,
            "created",
            actor_type,
            actor_id,
            {"initial_status": status},
        )
        logger.info("创建记忆 | id=%s | type=%s | subject=%s", memory.id, memory_type, subject)
        return memory

    @staticmethod
    def get_memory(
        memory_id: str,
        owner_external_id: str | None = None,
    ) -> MemoryItem | None:
        with get_session() as session:
            memory = session.get(MemoryItem, memory_id)
            if (
                memory
                and owner_external_id
                and memory.owner_external_id
                and memory.owner_external_id != owner_external_id
            ):
                return None
            return memory

    @staticmethod
    def list_memories(
        memory_type: str | None = None,
        status: str | None = None,
        scope: str | None = None,
        subject: str | None = None,
        owner_external_id: str | None = None,
        conversation_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryItem]:
        with get_session() as session:
            query = select(MemoryItem)
            if memory_type:
                query = query.where(MemoryItem.memory_type == memory_type)
            if status:
                query = query.where(MemoryItem.status == status)
            if scope:
                query = query.where(MemoryItem.scope == scope)
            if subject:
                query = query.where(MemoryItem.subject == subject)
            if owner_external_id:
                query = query.where(
                    or_(
                        MemoryItem.owner_external_id.is_(None),
                        MemoryItem.owner_external_id == owner_external_id,
                    )
                )
            if conversation_id:
                query = query.where(
                    or_(
                        MemoryItem.scope != "conversation",
                        MemoryItem.conversation_id.is_(None),
                        MemoryItem.conversation_id == conversation_id,
                    )
                )
            query = query.order_by(col(MemoryItem.created_at).desc()).limit(limit).offset(offset)
            return list(session.exec(query).all())

    @staticmethod
    def update_memory(
        memory_id: str,
        content: str | None = None,
        summary: str | None = None,
        confidence: float | None = None,
        importance: float | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        metadata_json: dict | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        event_type: str = "edited",
    ) -> MemoryItem | None:
        with get_session() as session:
            memory = session.get(MemoryItem, memory_id)
            if not memory:
                return None

            if content is not None:
                memory.content = content
            if summary is not None:
                memory.summary = summary
            if confidence is not None:
                memory.confidence = confidence
            if importance is not None:
                memory.importance = importance
            if status is not None:
                memory.status = status
            if tags is not None:
                memory.tags = tags
            if metadata_json is not None:
                memory.metadata_json = metadata_json

            memory.updated_at = datetime.utcnow()
            session.add(memory)
            session.commit()
            session.refresh(memory)

        MemoryService._log_event(memory_id, event_type, actor_type, actor_id, {})
        logger.info("更新记忆 | id=%s", memory_id)
        return memory

    @staticmethod
    def confirm_memory(memory_id: str, actor_id: str | None = None) -> MemoryItem | None:
        if not MemoryService.get_memory(memory_id, owner_external_id=actor_id):
            return None
        return MemoryService.update_memory(
            memory_id,
            status="active",
            actor_type="user",
            actor_id=actor_id,
            event_type="confirmed",
        )

    @staticmethod
    def reject_memory(memory_id: str, actor_id: str | None = None) -> MemoryItem | None:
        if not MemoryService.get_memory(memory_id, owner_external_id=actor_id):
            return None
        return MemoryService.update_memory(
            memory_id,
            status="rejected",
            actor_type="user",
            actor_id=actor_id,
            event_type="rejected",
        )

    @staticmethod
    def delete_memory(memory_id: str, actor_id: str | None = None) -> bool:
        with get_session() as session:
            memory = session.get(MemoryItem, memory_id)
            if not memory:
                return False
            if actor_id and memory.owner_external_id and memory.owner_external_id != actor_id:
                return False
            session.delete(memory)
            session.commit()

        MemoryService._log_event(memory_id, "expired", "user" if actor_id else "system", actor_id, {})
        logger.info("删除记忆 | id=%s", memory_id)
        return True

    @staticmethod
    def get_active_memories_for_context(
        memory_type: str | None = None,
        owner_external_id: str | None = None,
        conversation_id: str | None = None,
        query_text: str | None = None,
        max_items: int = 10,
    ) -> list[MemoryItem]:
        with get_session() as session:
            query = (
                select(MemoryItem)
                .where(MemoryItem.status == "active")
                .where(
                    or_(
                        MemoryItem.expires_at.is_(None),
                        MemoryItem.expires_at > datetime.utcnow(),
                    )
                )
            )
            if memory_type:
                query = query.where(MemoryItem.memory_type == memory_type)
            if owner_external_id:
                query = query.where(
                    or_(
                        MemoryItem.owner_external_id.is_(None),
                        MemoryItem.owner_external_id == owner_external_id,
                    )
                )
            if conversation_id:
                query = query.where(
                    or_(
                        MemoryItem.scope != "conversation",
                        MemoryItem.conversation_id.is_(None),
                        MemoryItem.conversation_id == conversation_id,
                    )
                )

            candidates = list(
                session.exec(
                    query.order_by(
                        col(MemoryItem.importance).desc(),
                        col(MemoryItem.last_used_at).desc().nulls_last(),
                    ).limit(max(max_items * 8, 40))
                ).all()
            )

        keywords = MemoryService._extract_keywords(query_text or "")
        if keywords:
            candidates.sort(
                key=lambda memory: (
                    MemoryService._memory_relevance(memory, keywords),
                    memory.importance,
                    memory.last_used_at or memory.created_at,
                ),
                reverse=True,
            )
        return candidates[:max_items]

    @staticmethod
    def mark_memories_used(memory_ids: list[str]) -> None:
        if not memory_ids:
            return
        with get_session() as session:
            memories = session.exec(
                select(MemoryItem).where(MemoryItem.id.in_(memory_ids))
            ).all()
            now = datetime.utcnow()
            for memory in memories:
                memory.last_used_at = now
                session.add(memory)
            session.commit()
        for memory_id in memory_ids:
            MemoryService._log_event(memory_id, "used", "agent", None, {})

    @staticmethod
    def touch_memory(memory_id: str) -> None:
        with get_session() as session:
            memory = session.get(MemoryItem, memory_id)
            if memory:
                memory.last_used_at = datetime.utcnow()
                session.add(memory)
                session.commit()

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        normalized = text.lower()
        for separator in "，。！？,.!?/\\:;；()（）[]【】":
            normalized = normalized.replace(separator, " ")
        stop_words = {"什么", "怎么", "可以", "这个", "那个", "我们", "你们", "他们", "是否"}
        return [word for word in normalized.split() if len(word) > 1 and word not in stop_words]

    @staticmethod
    def _memory_relevance(memory: MemoryItem, keywords: list[str]) -> int:
        haystack = " ".join(
            [
                memory.subject,
                memory.content,
                memory.summary or "",
                " ".join(memory.tags or []),
            ]
        ).lower()
        return sum(1 for keyword in keywords if keyword in haystack)

    @staticmethod
    def count_memories(
        memory_type: str | None = None,
        status: str | None = None,
        owner_external_id: str | None = None,
    ) -> int:
        with get_session() as session:
            query = select(func.count(MemoryItem.id))
            if memory_type:
                query = query.where(MemoryItem.memory_type == memory_type)
            if status:
                query = query.where(MemoryItem.status == status)
            if owner_external_id:
                query = query.where(
                    or_(
                        MemoryItem.owner_external_id.is_(None),
                        MemoryItem.owner_external_id == owner_external_id,
                    )
                )
            return session.exec(query).one()

    @staticmethod
    def import_profile_to_memory(
        owner_external_id: str = "local",
    ) -> dict[str, int]:
        from omka.app.profiles.profile_loader import load_interests, load_projects

        created = {"interests": 0, "projects": 0, "skipped": 0}
        existing = MemoryService.list_memories(
            owner_external_id=owner_external_id,
            limit=1000,
        )
        existing_refs = {
            memory.source_ref
            for memory in existing
            if memory.source_ref
        }

        interests = load_interests()
        for interest in interests:
            name = interest.get("name", "")
            keywords = interest.get("keywords", [])
            weight = interest.get("weight", 1.0)
            if name:
                source_ref = f"profile:interest:{name}"
                if source_ref in existing_refs:
                    created["skipped"] += 1
                    continue
                MemoryService.create_memory(
                    memory_type="user",
                    subject="interest",
                    content=f"用户兴趣: {name}。关键词: {', '.join(keywords)}",
                    scope="user",
                    owner_external_id=owner_external_id,
                    source_type="import",
                    source_ref=source_ref,
                    importance=min(weight, 1.0),
                    tags=["interest", name],
                    metadata_json={
                        "weight": weight,
                        "keywords": keywords,
                        "profile_name": name,
                    },
                )
                created["interests"] += 1
                existing_refs.add(source_ref)

        projects = load_projects()
        for project in projects:
            name = project.get("name", "")
            keywords = project.get("keywords", [])
            weight = project.get("weight", 1.0)
            if name:
                source_ref = f"profile:project:{name}"
                if source_ref in existing_refs:
                    created["skipped"] += 1
                    continue
                MemoryService.create_memory(
                    memory_type="user",
                    subject="project",
                    content=f"用户项目: {name}。关键词: {', '.join(keywords)}",
                    scope="user",
                    owner_external_id=owner_external_id,
                    source_type="import",
                    source_ref=source_ref,
                    importance=min(weight, 1.0),
                    tags=["project", name],
                    metadata_json={
                        "weight": weight,
                        "keywords": keywords,
                        "profile_name": name,
                    },
                )
                created["projects"] += 1
                existing_refs.add(source_ref)

        logger.info("从用户画像导入记忆 | interests=%d | projects=%d", created["interests"], created["projects"])
        return created

    @staticmethod
    def _log_event(
        memory_id: str,
        event_type: str,
        actor_type: str = "system",
        actor_id: str | None = None,
        detail_json: dict | None = None,
    ) -> None:
        try:
            with get_session() as session:
                event = MemoryEvent(
                    memory_id=memory_id,
                    event_type=event_type,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    detail_json=detail_json or {},
                )
                session.add(event)
                session.commit()
        except Exception as e:
            logger.error("记录记忆事件失败 | memory_id=%s | error=%s", memory_id, e)
