from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from omka.app.core.logging import logger
from omka.app.storage.db import CandidateItem, NormalizedItem, SourceConfig, get_session

router = APIRouter()


class FeedbackRequest(BaseModel):
    feedback_type: str = "not_interested"
    notes: str | None = None


class BatchRequest(BaseModel):
    ids: list[str]


@router.get("")
async def list_candidates(status: str | None = None):
    with get_session() as session:
        query = select(CandidateItem)
        if status:
            query = query.where(CandidateItem.status == status)
        candidates = session.exec(query).all()

        normalized_ids = [c.normalized_item_id for c in candidates]
        normalized_map = {}
        if normalized_ids:
            norm_query = select(NormalizedItem).where(NormalizedItem.id.in_(normalized_ids))
            for n in session.exec(norm_query).all():
                normalized_map[n.id] = n

        source_ids = {n.source_id for n in normalized_map.values()}
        source_map = {}
        if source_ids:
            src_query = select(SourceConfig).where(SourceConfig.id.in_(source_ids))
            for s in session.exec(src_query).all():
                source_map[s.id] = s

        result = []
        for c in candidates:
            norm = normalized_map.get(c.normalized_item_id)
            source = source_map.get(norm.source_id) if norm else None
            result.append({
                "id": c.id,
                "normalized_item_id": c.normalized_item_id,
                "title": c.title,
                "url": c.url,
                "item_type": c.item_type,
                "score": c.score,
                "score_detail": c.score_detail,
                "summary": c.summary,
                "recommendation_reason": c.recommendation_reason,
                "status": c.status,
                "matched_interests": c.matched_interests,
                "matched_projects": c.matched_projects,
                "source_name": source.name if source else "",
                "created_at": c.created_at,
            })
        return result


@router.post("/batch/confirm")
async def batch_confirm_candidates(data: BatchRequest):
    from omka.app.services.recommendation_service import RecommendationService
    from omka.app.storage.db import KnowledgeItem, NormalizedItem
    from omka.app.storage.markdown_store import save_knowledge_markdown

    confirmed = 0
    not_found = 0
    with get_session() as session:
        for candidate_id in data.ids:
            candidate = session.get(CandidateItem, candidate_id)
            if not candidate:
                not_found += 1
                continue

            normalized = session.get(NormalizedItem, candidate.normalized_item_id)
            if normalized:
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
                    logger.error("批量-保存 Markdown 失败 | id=%s | error=%s", candidate_id, e)

            candidate.status = "confirmed"
            session.add(candidate)
            RecommendationService.record_feedback(candidate_id, "confirm")
            confirmed += 1
        session.commit()

    logger.info("批量确认完成 | confirmed=%d | not_found=%d", confirmed, not_found)
    return {"confirmed": confirmed, "not_found": not_found}


@router.post("/batch/ignore")
async def batch_ignore_candidates(data: BatchRequest):
    ignored = 0
    not_found = 0
    with get_session() as session:
        for candidate_id in data.ids:
            candidate = session.get(CandidateItem, candidate_id)
            if not candidate:
                not_found += 1
                continue
            candidate.status = "ignored"
            session.add(candidate)
            ignored += 1
        session.commit()

    logger.info("批量忽略完成 | ignored=%d | not_found=%d", ignored, not_found)
    return {"ignored": ignored, "not_found": not_found}


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
