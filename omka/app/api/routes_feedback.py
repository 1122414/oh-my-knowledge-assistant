from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from omka.app.core.logging import logger
from omka.app.storage.db import CandidateItem, get_session

router = APIRouter()


@router.get("")
async def list_candidates(status: str | None = None):
    with get_session() as session:
        query = select(CandidateItem)
        if status:
            query = query.where(CandidateItem.status == status)
        candidates = session.exec(query).all()
        return [
            {
                "id": c.id,
                "normalized_item_id": c.normalized_item_id,
                "title": c.title,
                "url": c.url,
                "item_type": c.item_type,
                "score": c.score,
                "summary": c.summary,
                "recommendation_reason": c.recommendation_reason,
                "status": c.status,
                "matched_interests": c.matched_interests,
                "matched_projects": c.matched_projects,
                "created_at": c.created_at,
            }
            for c in candidates
        ]


@router.post("/{candidate_id:path}/confirm")
async def confirm_candidate(candidate_id: str):
    from omka.app.storage.db import KnowledgeItem, NormalizedItem
    from omka.app.storage.markdown_store import save_knowledge_markdown

    with get_session() as session:
        candidate = session.get(CandidateItem, candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="候选条目不存在")

        normalized = session.get(NormalizedItem, candidate.normalized_item_id)
        if not normalized:
            raise HTTPException(status_code=404, detail="关联数据不存在")

        knowledge = KnowledgeItem(
            id=f"knowledge:{candidate.id}",
            candidate_item_id=candidate.id,
            title=candidate.title,
            url=candidate.url,
            item_type=candidate.item_type,
            content=normalized.content,
            summary=candidate.summary,
            tags=normalized.tags,
            item_metadata=normalized.item_metadata,
        )
        session.merge(knowledge)

        candidate.status = "confirmed"
        session.add(candidate)
        session.commit()

        try:
            save_knowledge_markdown({
                "title": candidate.title,
                "url": candidate.url,
                "item_type": candidate.item_type,
                "author": normalized.author,
                "summary": candidate.summary or "",
                "content": normalized.content,
                "tags": normalized.tags,
                "repo_full_name": normalized.repo_full_name,
            })
        except Exception as e:
            logger.error("保存 Markdown 失败 | id=%s | error=%s", candidate_id, e)

        logger.info("候选条目已确认并入库 | id=%s", candidate_id)
    return {"id": candidate_id, "status": "confirmed"}


@router.post("/{candidate_id:path}/ignore")
async def ignore_candidate(candidate_id: str):
    with get_session() as session:
        candidate = session.get(CandidateItem, candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="候选条目不存在")
        candidate.status = "ignored"
        session.add(candidate)
        session.commit()
        logger.info("候选条目已忽略 | id=%s", candidate_id)
    return {"id": candidate_id, "status": "ignored"}


@router.post("/{candidate_id:path}/feedback")
async def feedback_candidate(candidate_id: str, data: dict[str, Any]):
    from omka.app.storage.db import UserFeedback

    feedback_type = data.get("feedback_type", "not_interested")
    with get_session() as session:
        candidate = session.get(CandidateItem, candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="候选条目不存在")

        feedback = UserFeedback(
            candidate_item_id=candidate_id,
            feedback_type=feedback_type,
            notes=data.get("notes"),
        )
        session.add(feedback)
        session.commit()
        logger.info("用户反馈 | id=%s | type=%s", candidate_id, feedback_type)
    return {"id": candidate_id, "feedback_type": feedback_type}
