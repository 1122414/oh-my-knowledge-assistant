from datetime import datetime
from typing import Any

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
        summary: str | None = None,
        source_type: str = "manual",
        source_ref: str | None = None,
        confidence: float = 0.8,
        importance: float = 0.5,
        status: str = "active",
        tags: list[str] | None = None,
        metadata_json: dict | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryItem:
        memory = MemoryItem(
            id=generate_memory_id(),
            memory_type=memory_type,
            scope=scope,
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

        MemoryService._log_event(memory.id, "created", "system", None, {"initial_status": status})
        logger.info("创建记忆 | id=%s | type=%s | subject=%s", memory.id, memory_type, subject)
        return memory

    @staticmethod
    def get_memory(memory_id: str) -> MemoryItem | None:
        with get_session() as session:
            return session.get(MemoryItem, memory_id)

    @staticmethod
    def list_memories(
        memory_type: str | None = None,
        status: str | None = None,
        scope: str | None = None,
        subject: str | None = None,
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
            query = query.order_by(col(MemoryItem.created_at).desc()).limit(limit).offset(offset)
            return list(session.exec(query).all())

    @staticmethod
    def update_memory(
        memory_id: str,
        content: str | None = None,
        summary: str | None = None,
        importance: float | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        metadata_json: dict | None = None,
    ) -> MemoryItem | None:
        with get_session() as session:
            memory = session.get(MemoryItem, memory_id)
            if not memory:
                return None

            if content is not None:
                memory.content = content
            if summary is not None:
                memory.summary = summary
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

        MemoryService._log_event(memory_id, "edited", "system", None, {})
        logger.info("更新记忆 | id=%s", memory_id)
        return memory

    @staticmethod
    def confirm_memory(memory_id: str, actor_id: str | None = None) -> MemoryItem | None:
        return MemoryService.update_memory(memory_id, status="active")

    @staticmethod
    def reject_memory(memory_id: str, actor_id: str | None = None) -> MemoryItem | None:
        return MemoryService.update_memory(memory_id, status="rejected")

    @staticmethod
    def delete_memory(memory_id: str) -> bool:
        with get_session() as session:
            memory = session.get(MemoryItem, memory_id)
            if not memory:
                return False
            session.delete(memory)
            session.commit()

        MemoryService._log_event(memory_id, "expired", "system", None, {})
        logger.info("删除记忆 | id=%s", memory_id)
        return True

    @staticmethod
    def get_active_memories_for_context(
        memory_type: str | None = None,
        max_items: int = 10,
    ) -> list[MemoryItem]:
        with get_session() as session:
            query = (
                select(MemoryItem)
                .where(MemoryItem.status == "active")
                .order_by(col(MemoryItem.importance).desc(), col(MemoryItem.last_used_at).desc().nulls_last())
                .limit(max_items)
            )
            if memory_type:
                query = query.where(MemoryItem.memory_type == memory_type)
            return list(session.exec(query).all())

    @staticmethod
    def touch_memory(memory_id: str) -> None:
        with get_session() as session:
            memory = session.get(MemoryItem, memory_id)
            if memory:
                memory.last_used_at = datetime.utcnow()
                session.add(memory)
                session.commit()

    @staticmethod
    def count_memories(memory_type: str | None = None, status: str | None = None) -> int:
        with get_session() as session:
            query = select(func.count(MemoryItem.id))
            if memory_type:
                query = query.where(MemoryItem.memory_type == memory_type)
            if status:
                query = query.where(MemoryItem.status == status)
            return session.exec(query).one()

    @staticmethod
    def import_profile_to_memory() -> dict[str, int]:
        from omka.app.profiles.profile_loader import load_interests, load_projects

        created = {"interests": 0, "projects": 0}

        interests = load_interests()
        for interest in interests:
            name = interest.get("name", "")
            keywords = interest.get("keywords", [])
            weight = interest.get("weight", 1.0)
            if name:
                MemoryService.create_memory(
                    memory_type="user",
                    subject="interest",
                    content=f"用户兴趣: {name}。关键词: {', '.join(keywords)}",
                    scope="user",
                    source_type="import",
                    importance=min(weight, 1.0),
                    tags=["interest", name],
                    metadata_json={"weight": weight, "keywords": keywords},
                )
                created["interests"] += 1

        projects = load_projects()
        for project in projects:
            name = project.get("name", "")
            keywords = project.get("keywords", [])
            weight = project.get("weight", 1.0)
            if name:
                MemoryService.create_memory(
                    memory_type="user",
                    subject="project",
                    content=f"用户项目: {name}。关键词: {', '.join(keywords)}",
                    scope="user",
                    source_type="import",
                    importance=min(weight, 1.0),
                    tags=["project", name],
                    metadata_json={"weight": weight, "keywords": keywords},
                )
                created["projects"] += 1

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
