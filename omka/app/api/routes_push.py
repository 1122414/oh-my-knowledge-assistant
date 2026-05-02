from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import col, func, select

from omka.app.services.action_service import PushService
from omka.app.storage.db import PushEvent, PushPolicy, get_session

router = APIRouter()


class PushPolicyCreateRequest(BaseModel):
    id: str
    name: str
    trigger_type: str
    threshold: float | None = None
    max_per_day: int = Field(default=5, ge=1)


class PushPolicyUpdateRequest(BaseModel):
    enabled: bool | None = None
    threshold: float | None = None
    max_per_day: int | None = Field(default=None, ge=1)


@router.get("/policies")
async def list_policies(enabled_only: bool = False):
    policies = PushService.list_policies(enabled_only=enabled_only)
    return {"policies": [p.model_dump() for p in policies]}


@router.post("/policies")
async def create_policy(data: PushPolicyCreateRequest):
    policy = PushService.create_policy(
        policy_id=data.id,
        name=data.name,
        trigger_type=data.trigger_type,
        threshold=data.threshold,
        max_per_day=data.max_per_day,
    )
    return {"id": policy.id, "message": "推送策略已创建"}


@router.put("/policies/{policy_id}")
async def update_policy(policy_id: str, data: PushPolicyUpdateRequest):
    with get_session() as session:
        policy = session.get(PushPolicy, policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail="策略不存在")
        if data.enabled is not None:
            policy.enabled = data.enabled
        if data.threshold is not None:
            policy.threshold = data.threshold
        if data.max_per_day is not None:
            policy.max_per_day = data.max_per_day
        session.add(policy)
        session.commit()
    return {"id": policy_id, "message": "推送策略已更新"}


@router.get("/events")
async def list_events(limit: int = 20):
    with get_session() as session:
        events = session.exec(
            select(PushEvent).order_by(col(PushEvent.created_at).desc()).limit(limit)
        ).all()
    return {"events": [e.model_dump() for e in events]}


@router.get("/status")
async def get_push_status():
    today_count = PushService.count_today_events()
    return {
        "today_pushes": today_count,
        "max_per_day_default": 5,
    }
