from datetime import datetime
from typing import Any

from sqlmodel import col, select

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.pipeline.ranker import compute_scores, rank_candidates as _rank_candidates
from omka.app.storage.db import (
    CandidateItem,
    NormalizedItem,
    RecommendationDecision,
    RecommendationRun,
    get_session,
)


def run_ranking() -> dict[str, Any]:
    logger.info("通过 RecommendationService 执行排序")
    return _rank_candidates()


class RecommendationService:
    @staticmethod
    def run_recommendation(
        trigger_type: str = "manual",
        user_external_id: str | None = None,
        strategy: str = "default",
    ) -> RecommendationRun:
        with get_session() as session:
            run = RecommendationRun(
                trigger_type=trigger_type,
                user_external_id=user_external_id,
                strategy=strategy,
            )
            session.add(run)
            session.commit()
            session.refresh(run)

        logger.info("开始推荐运行 | run_id=%d | trigger=%s", run.id, trigger_type)

        candidates = RecommendationService._get_pending_candidates()
        ranked = RecommendationService._rank_with_explanation(candidates, run.id)

        with get_session() as session:
            run.selected_count = len(ranked)
            session.add(run)
            session.commit()

        logger.info("推荐运行完成 | run_id=%d | selected=%d", run.id, len(ranked))
        return run

    @staticmethod
    def get_explanation(candidate_item_id: str) -> dict[str, Any] | None:
        with get_session() as session:
            decision = session.exec(
                select(RecommendationDecision)
                .where(RecommendationDecision.candidate_item_id == candidate_item_id)
                .order_by(col(RecommendationDecision.created_at).desc())
            ).first()
            if not decision:
                return None
            return {
                "explanation": decision.explanation,
                "explanation_json": decision.explanation_json,
                "final_score": decision.final_score,
                "rank": decision.rank,
            }

    @staticmethod
    def record_feedback(
        candidate_item_id: str,
        feedback_type: str,
        user_external_id: str | None = None,
    ) -> None:
        from omka.app.services.memory_service import MemoryService

        if feedback_type == "confirm":
            MemoryService.create_memory(
                memory_type="user",
                subject="preference",
                content=f"用户对候选 {candidate_item_id} 给出确认反馈，表示感兴趣",
                scope="user",
                source_type="feedback",
                source_ref=candidate_item_id,
                importance=0.9,
            )
        elif feedback_type == "dislike":
            MemoryService.create_memory(
                memory_type="user",
                subject="preference",
                content=f"用户对候选 {candidate_item_id} 给出不喜欢反馈",
                scope="user",
                source_type="feedback",
                source_ref=candidate_item_id,
                importance=0.8,
            )
        elif feedback_type == "read_later":
            MemoryService.create_memory(
                memory_type="user",
                subject="read_later",
                content=f"用户标记候选 {candidate_item_id} 为稍后阅读",
                scope="user",
                source_type="feedback",
                source_ref=candidate_item_id,
                importance=0.6,
            )

        logger.info("反馈已记录到记忆 | candidate=%s | feedback=%s", candidate_item_id, feedback_type)

    @staticmethod
    def _get_pending_candidates() -> list[CandidateItem]:
        with get_session() as session:
            return list(session.exec(
                select(CandidateItem)
                .where(CandidateItem.status == "pending")
                .order_by(col(CandidateItem.score).desc())
            ).all())

    @staticmethod
    def _rank_with_explanation(candidates: list[CandidateItem], run_id: int) -> list[RecommendationDecision]:
        from omka.app.profiles.interest_model import UserProfile

        profile = UserProfile.load()
        decisions = []

        for rank, candidate in enumerate(candidates, 1):
            with get_session() as session:
                normalized = session.get(NormalizedItem, candidate.normalized_item_id)
                if not normalized:
                    continue

                scores = compute_scores(normalized, profile)
                explanation = RecommendationService._build_explanation(candidate, scores)

                decision = RecommendationDecision(
                    run_id=run_id,
                    candidate_item_id=candidate.id,
                    final_score=candidate.score,
                    rank=rank,
                    explanation=explanation["why_recommended"],
                    explanation_json=explanation,
                    action_hint="建议查看详情或加入知识库",
                )
                session.add(decision)
                session.commit()
                decisions.append(decision)

        return decisions

    @staticmethod
    def _build_explanation(candidate: CandidateItem, scores: dict[str, Any]) -> dict[str, Any]:
        reasons = []
        matched_memories = []

        if candidate.matched_interests:
            reasons.append(f"匹配兴趣: {', '.join(candidate.matched_interests)}")
        if candidate.matched_projects:
            reasons.append(f"匹配项目: {', '.join(candidate.matched_projects)}")

        freshness = scores.get("freshness_score", 0)
        if freshness > 0.8:
            reasons.append("内容非常新鲜")
        elif freshness > 0.5:
            reasons.append("内容较新")

        popularity = scores.get("popularity_score", 0)
        if popularity > 0.8:
            reasons.append("热度很高")

        return {
            "why_recommended": "；".join(reasons) if reasons else "基于综合评分推荐",
            "matched_memories": matched_memories,
            "matched_interests": candidate.matched_interests or [],
            "freshness": f"新鲜度得分: {freshness:.2f}",
            "source_reason": f"来自数据源: {candidate.item_type}",
            "suggested_action": "建议查看详情或加入知识库",
        }
