from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from omka.app.core.logging import logger
from omka.app.storage.db import CandidateItem, get_session

router = APIRouter()


class FeedbackRequest(BaseModel):
    feedback_type: str = "not_interested"
    notes: str | None = None


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
    from omka.app.services.recommendation_service import RecommendationService
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

    RecommendationService.record_feedback(candidate_id, "confirm")
    logger.info("候选条目已确认并入库 | id=%s", candidate_id)
    return {"id": candidate_id, "status": "confirmed"}


def _set_candidate_status(candidate_id: str, status: str, log_msg: str) -> dict[str, str]:
    with get_session() as session:
        candidate = session.get(CandidateItem, candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="候选条目不存在")
        candidate.status = status
        session.add(candidate)
        session.commit()
        logger.info(log_msg, candidate_id)
    return {"id": candidate_id, "status": status}


@router.post("/{candidate_id:path}/ignore")
async def ignore_candidate(candidate_id: str):
    return _set_candidate_status(candidate_id, "ignored", "候选条目已忽略 | id=%s")


@router.post("/{candidate_id:path}/dislike")
async def dislike_candidate(candidate_id: str):
    from omka.app.services.recommendation_service import RecommendationService
    result = _set_candidate_status(candidate_id, "disliked", "候选条目已标记不感兴趣 | id=%s")
    RecommendationService.record_feedback(candidate_id, "dislike")
    return result


@router.post("/{candidate_id:path}/read-later")
async def read_later_candidate(candidate_id: str):
    from omka.app.services.recommendation_service import RecommendationService
    result = _set_candidate_status(candidate_id, "read_later", "候选条目已标记稍后阅读 | id=%s")
    RecommendationService.record_feedback(candidate_id, "read_later")
    return result


@router.post("/{candidate_id:path}/feedback")
async def feedback_candidate(candidate_id: str, data: FeedbackRequest):
    from omka.app.storage.db import UserFeedback

    with get_session() as session:
        candidate = session.get(CandidateItem, candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="候选条目不存在")

        feedback = UserFeedback(
            candidate_item_id=candidate_id,
            feedback_type=data.feedback_type,
            notes=data.notes,
        )
        session.add(feedback)
        session.commit()
        logger.info("用户反馈 | id=%s | type=%s", candidate_id, data.feedback_type)
    return {"id": candidate_id, "feedback_type": data.feedback_type}
