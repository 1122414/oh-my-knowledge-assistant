from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import col, func, select

from omka.app.core.logging import logger
from omka.app.services.memory_service import MemoryService
from omka.app.storage.db import MemoryEvent, MemoryItem, get_session

router = APIRouter()


class MemoryCreateRequest(BaseModel):
    memory_type: str = Field(..., description="记忆类型: user / conversation / system")
    subject: str = Field(..., description="主题")
    content: str = Field(..., description="记忆内容")
    scope: str = Field(default="global", description="作用域")
    summary: str | None = None
    source_type: str = Field(default="manual", description="来源类型")
    source_ref: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    status: str = Field(default="active", description="状态")
    tags: list[str] = Field(default_factory=list)
    metadata_json: dict = Field(default_factory=dict)


class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    summary: str | None = None
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    status: str | None = None
    tags: list[str] | None = None
    metadata_json: dict | None = None


class MemoryListResponse(BaseModel):
    items: list[dict]
    total: int


@router.get("")
async def list_memories(
    memory_type: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    items = MemoryService.list_memories(
        memory_type=memory_type,
        status=status,
        scope=scope,
        limit=limit,
        offset=offset,
    )
    total = MemoryService.count_memories(memory_type=memory_type, status=status)
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
    }


@router.post("")
async def create_memory(data: MemoryCreateRequest):
    memory = MemoryService.create_memory(
        memory_type=data.memory_type,
        subject=data.subject,
        content=data.content,
        scope=data.scope,
        summary=data.summary,
        source_type=data.source_type,
        source_ref=data.source_ref,
        confidence=data.confidence,
        importance=data.importance,
        status=data.status,
        tags=data.tags,
        metadata_json=data.metadata_json,
    )
    return {"id": memory.id, "message": "记忆已创建"}


@router.get("/{memory_id}")
async def get_memory(memory_id: str):
    memory = MemoryService.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return memory.model_dump()


@router.put("/{memory_id}")
async def update_memory(memory_id: str, data: MemoryUpdateRequest):
    memory = MemoryService.update_memory(
        memory_id=memory_id,
        content=data.content,
        summary=data.summary,
        importance=data.importance,
        status=data.status,
        tags=data.tags,
        metadata_json=data.metadata_json,
    )
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"id": memory_id, "message": "记忆已更新"}


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    success = MemoryService.delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"id": memory_id, "message": "记忆已删除"}


@router.post("/{memory_id}/confirm")
async def confirm_memory(memory_id: str):
    memory = MemoryService.confirm_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"id": memory_id, "status": "active", "message": "记忆已确认"}


@router.post("/{memory_id}/reject")
async def reject_memory(memory_id: str):
    memory = MemoryService.reject_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"id": memory_id, "status": "rejected", "message": "记忆已拒绝"}


@router.get("/{memory_id}/events")
async def get_memory_events(memory_id: str, limit: int = 20):
    with get_session() as session:
        events = session.exec(
            select(MemoryEvent)
            .where(MemoryEvent.memory_id == memory_id)
            .order_by(col(MemoryEvent.created_at).desc())
            .limit(limit)
        ).all()
    return {"memory_id": memory_id, "events": [e.model_dump() for e in events]}


@router.get("/profile/summary")
async def get_memory_profile_summary():
    with get_session() as session:
        user_count = session.exec(
            select(func.count(MemoryItem.id)).where(MemoryItem.memory_type == "user")
        ).one()
        conversation_count = session.exec(
            select(func.count(MemoryItem.id)).where(MemoryItem.memory_type == "conversation")
        ).one()
        system_count = session.exec(
            select(func.count(MemoryItem.id)).where(MemoryItem.memory_type == "system")
        ).one()
        candidate_count = session.exec(
            select(func.count(MemoryItem.id)).where(MemoryItem.status == "candidate")
        ).one()
    return {
        "user_memories": user_count,
        "conversation_memories": conversation_count,
        "system_memories": system_count,
        "candidate_memories": candidate_count,
    }


@router.post("/import-profile")
async def import_profile_to_memory():
    result = MemoryService.import_profile_to_memory()
    return {"message": "用户画像已导入记忆", "imported": result}
