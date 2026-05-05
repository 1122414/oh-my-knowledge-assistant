from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import col, select

from omka.app.services.recommendation_service import RecommendationService
from omka.app.storage.db import RecommendationDecision, RecommendationRun, get_session

router = APIRouter()


class RecommendationRunRequest(BaseModel):
    trigger_type: str = "manual"
    strategy: str = "default"


class FeedbackRequest(BaseModel):
    feedback_type: str
    user_external_id: str | None = None


@router.post("/run")
async def run_recommendation(data: RecommendationRunRequest):
    run = RecommendationService.run_recommendation(
        trigger_type=data.trigger_type,
        strategy=data.strategy,
    )
    return {"run_id": run.id, "status": "success", "selected_count": run.selected_count}


@router.get("/latest")
async def get_latest_recommendation():
    with get_session() as session:
        run = session.exec(
            select(RecommendationRun).order_by(col(RecommendationRun.created_at).desc())
        ).first()
        if not run:
            return {"message": "暂无推荐记录"}

        decisions = session.exec(
            select(RecommendationDecision)
            .where(RecommendationDecision.run_id == run.id)
            .order_by(col(RecommendationDecision.rank).asc())
        ).all()

    return {
        "run": run.model_dump(),
        "decisions": [d.model_dump() for d in decisions],
    }


@router.get("/{candidate_id}/explain")
async def explain_candidate(candidate_id: str):
    explanation = RecommendationService.get_explanation(candidate_id)
    if not explanation:
        raise HTTPException(status_code=404, detail="该候选暂无推荐解释")
    return explanation


@router.post("/{candidate_id}/feedback")
async def feedback_candidate_recommendation(candidate_id: str, data: FeedbackRequest):
    RecommendationService.record_feedback(
        candidate_item_id=candidate_id,
        feedback_type=data.feedback_type,
        user_external_id=data.user_external_id,
    )
    return {
        "candidate_id": candidate_id,
        "feedback_type": data.feedback_type,
        "message": "反馈已记录",
    }


@router.get("/profile-impact")
async def get_profile_impact():
    with get_session() as session:
        total_runs = session.exec(select(RecommendationRun)).all()
        total_decisions = session.exec(select(RecommendationDecision)).all()
    return {
        "total_runs": len(total_runs),
        "total_decisions": len(total_decisions),
        "average_selected": sum(r.selected_count for r in total_runs) / len(total_runs) if total_runs else 0,
    }
