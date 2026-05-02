from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from omka.app.core.logging import logger
from omka.app.storage.db import KnowledgeItem, UserFeedback, get_session

router = APIRouter()


class KnowledgeCreateRequest(BaseModel):
    id: str
    candidate_item_id: str
    title: str
    url: str
    item_type: str
    content: str
    summary: str | None = None
    tags: list[str] | None = None
    item_metadata: dict | None = None


class KnowledgeFeedbackRequest(BaseModel):
    feedback_type: str = "not_interested"
    notes: str | None = None


@router.get("")
async def list_knowledge():
    with get_session() as session:
        items = session.exec(select(KnowledgeItem).order_by(KnowledgeItem.created_at.desc())).all()
        return [i.model_dump() for i in items]


@router.get("/{item_id:path}")
async def get_knowledge(item_id: str):
    with get_session() as session:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="知识条目不存在")
        return item.model_dump()


@router.post("")
async def create_knowledge(data: KnowledgeCreateRequest):
    item = KnowledgeItem(**data.model_dump())
    with get_session() as session:
        session.add(item)
        session.commit()
        logger.info("创建知识条目 | id=%s", item.id)
    return {"id": item.id, "message": "知识条目已创建"}


@router.delete("/{item_id:path}")
async def delete_knowledge(item_id: str):
    with get_session() as session:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="知识条目不存在")
        session.delete(item)
        session.commit()
        logger.info("删除知识条目 | id=%s", item_id)
    return {"id": item_id, "message": "知识条目已删除"}


@router.post("/{item_id:path}/feedback")
async def feedback_knowledge(item_id: str, data: KnowledgeFeedbackRequest):
    with get_session() as session:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="知识条目不存在")

        feedback = UserFeedback(
            candidate_item_id=item_id,
            feedback_type=data.feedback_type,
            notes=data.notes,
        )
        session.add(feedback)
        session.commit()
        logger.info("知识库反馈 | id=%s | type=%s", item_id, data.feedback_type)
    return {"id": item_id, "feedback_type": data.feedback_type}
