from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from omka.app.core.logging import logger
from omka.app.storage.db import KnowledgeItem, UserFeedback, get_session

router = APIRouter()


@router.get("")
async def list_knowledge():
    with get_session() as session:
        items = session.exec(select(KnowledgeItem).order_by(KnowledgeItem.created_at.desc())).all()
        return [
            {
                "id": i.id,
                "title": i.title,
                "url": i.url,
                "item_type": i.item_type,
                "tags": i.tags,
                "created_at": i.created_at,
            }
            for i in items
        ]


@router.get("/{item_id:path}")
async def get_knowledge(item_id: str):
    with get_session() as session:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="知识条目不存在")
        return {
            "id": item.id,
            "title": item.title,
            "url": item.url,
            "item_type": item.item_type,
            "content": item.content,
            "summary": item.summary,
            "tags": item.tags,
            "item_metadata": item.item_metadata,
            "created_at": item.created_at,
        }


@router.post("")
async def create_knowledge(data: dict[str, Any]):
    item = KnowledgeItem(**data)
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
async def feedback_knowledge(item_id: str, data: dict[str, Any]):
    feedback_type = data.get("feedback_type", "not_interested")
    with get_session() as session:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="知识条目不存在")

        feedback = UserFeedback(
            candidate_item_id=item_id,
            feedback_type=feedback_type,
            notes=data.get("notes"),
        )
        session.add(feedback)
        session.commit()
        logger.info("知识库反馈 | id=%s | type=%s", item_id, feedback_type)
    return {"id": item_id, "feedback_type": feedback_type}
