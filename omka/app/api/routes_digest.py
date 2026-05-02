from fastapi import APIRouter
from sqlmodel import select

from omka.app.services.recommendation_service import run_ranking as service_run_ranking
from omka.app.storage.db import CandidateItem, get_session

router = APIRouter()


@router.post("/run-ranking")
async def run_ranking():
    result = service_run_ranking()
    return result


@router.get("/ranked")
async def get_ranked_candidates(limit: int = 20):
    with get_session() as session:
        candidates = session.exec(
            select(CandidateItem)
            .where(CandidateItem.status == "pending")
            .order_by(CandidateItem.score.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": c.id,
                "title": c.title,
                "url": c.url,
                "item_type": c.item_type,
                "score": c.score,
                "score_detail": c.score_detail,
                "matched_interests": c.matched_interests,
                "matched_projects": c.matched_projects,
                "summary": c.summary,
                "recommendation_reason": c.recommendation_reason,
            }
            for c in candidates
        ]


@router.post("/run-today")
async def run_today_digest():
    from omka.app.services.daily_job import run_daily_job
    result = await run_daily_job()
    return result
