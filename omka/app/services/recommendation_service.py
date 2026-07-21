from datetime import datetime
from typing import Any

from sqlmodel import col, select

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.pipeline.ranker import compute_scores, rank_candidates as _rank_candidates
from omka.app.storage.db import (
    CandidateItem,
    MemoryItem,
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
        resolved_user_id = user_external_id or "local"
        with get_session() as session:
            run = RecommendationRun(
                trigger_type=trigger_type,
                user_external_id=resolved_user_id,
                strategy=strategy,
            )
            session.add(run)
            session.commit()
            session.refresh(run)

        logger.info("开始推荐运行 | run_id=%d | trigger=%s", run.id, trigger_type)

        candidates = RecommendationService._get_pending_candidates()
        ranked = RecommendationService._rank_with_explanation(
            candidates,
            run.id,
            resolved_user_id,
        )

        with get_session() as session:
            run.candidate_count = len(candidates)
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

        resolved_user_id = user_external_id or "local"
        if not settings.recommendation_feedback_learning_enabled:
            logger.info(
                "反馈学习已关闭 | candidate=%s | feedback=%s",
                candidate_item_id,
                feedback_type,
            )
            return

        with get_session() as session:
            candidate = session.get(CandidateItem, candidate_item_id)
            normalized = (
                session.get(NormalizedItem, candidate.normalized_item_id)
                if candidate
                else None
            )
            existing_feedback = session.exec(
                select(MemoryItem)
                .where(MemoryItem.owner_external_id == resolved_user_id)
                .where(MemoryItem.source_type == "feedback")
                .where(MemoryItem.source_ref == candidate_item_id)
                .order_by(col(MemoryItem.created_at).desc())
            ).first()
        title = candidate.title if candidate else candidate_item_id
        feature_tags = list(
            dict.fromkeys(
                [
                    *(candidate.matched_interests or [] if candidate else []),
                    *(candidate.matched_projects or [] if candidate else []),
                    *(normalized.tags or [] if normalized else []),
                ]
            )
        )[:20]
        feedback_specs = {
            "confirm": (
                "preference",
                f"用户喜欢并收藏了「{title}」，相关特征：{', '.join(feature_tags) or '未标注'}",
                0.9,
            ),
            "dislike": (
                "preference",
                f"用户不喜欢「{title}」，相关特征：{', '.join(feature_tags) or '未标注'}",
                0.8,
            ),
            "read_later": (
                "read_later",
                f"用户希望稍后阅读「{title}」，相关特征：{', '.join(feature_tags) or '未标注'}",
                0.6,
            ),
        }
        spec = feedback_specs.get(feedback_type)
        if not spec:
            logger.warning("忽略未知反馈类型 | feedback=%s", feedback_type)
            return
        subject, content, importance = spec
        tags = ["recommendation_feedback", feedback_type, *feature_tags]
        metadata = {
            "feedback_type": feedback_type,
            "candidate_title": title,
            "features": feature_tags,
        }

        if existing_feedback:
            MemoryService.update_memory(
                existing_feedback.id,
                content=content,
                importance=importance,
                status="active",
                tags=tags,
                metadata_json=metadata,
                actor_type="user",
                actor_id=resolved_user_id,
                event_type="edited",
            )
        else:
            MemoryService.create_memory(
                memory_type="user",
                subject=subject,
                content=content,
                importance=importance,
                scope="user",
                owner_external_id=resolved_user_id,
                source_type="feedback",
                source_ref=candidate_item_id,
                tags=tags,
                metadata_json=metadata,
                actor_type="user",
                actor_id=resolved_user_id,
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
    def _rank_with_explanation(
        candidates: list[CandidateItem],
        run_id: int,
        user_external_id: str | None = None,
    ) -> list[RecommendationDecision]:
        from omka.app.profiles.interest_model import UserProfile
        from omka.app.services.memory_service import MemoryService

        profile = UserProfile.load()
        feedback_memories = MemoryService.get_active_memories_for_context(
            memory_type="user",
            owner_external_id=user_external_id,
            max_items=200,
        )
        feedback_memories = [
            memory
            for memory in feedback_memories
            if memory.owner_external_id == user_external_id
        ]
        prepared: list[tuple[float, CandidateItem, dict[str, Any], dict[str, Any]]] = []

        for candidate in candidates:
            with get_session() as session:
                normalized = session.get(NormalizedItem, candidate.normalized_item_id)
                if not normalized:
                    continue

                scores = compute_scores(normalized, profile)
                feedback_adjustment, matched_feedback = RecommendationService._feedback_adjustment(
                    candidate,
                    normalized,
                    feedback_memories,
                )
                final_score = max(0.0, candidate.score + feedback_adjustment)
                explanation = RecommendationService._build_explanation(
                    candidate,
                    scores,
                    feedback_adjustment=feedback_adjustment,
                    matched_feedback=matched_feedback,
                )
                prepared.append((final_score, candidate, scores, explanation))

        prepared.sort(key=lambda item: item[0], reverse=True)
        decisions: list[RecommendationDecision] = []
        with get_session() as session:
            for rank, (final_score, candidate, _scores, explanation) in enumerate(prepared, 1):

                decision = RecommendationDecision(
                    run_id=run_id,
                    candidate_item_id=candidate.id,
                    final_score=round(final_score, 4),
                    rank=rank,
                    explanation=explanation["why_recommended"],
                    explanation_json=explanation,
                    action_hint="建议查看详情或加入知识库",
                )
                session.add(decision)
                decisions.append(decision)
            session.commit()

        return decisions

    @staticmethod
    def _feedback_adjustment(
        candidate: CandidateItem,
        normalized: NormalizedItem,
        feedback_memories: list[Any],
    ) -> tuple[float, list[str]]:
        candidate_features = {
            feature.lower()
            for feature in [
                *(candidate.matched_interests or []),
                *(candidate.matched_projects or []),
                *(normalized.tags or []),
            ]
            if feature
        }
        adjustment = 0.0
        matched: list[str] = []
        for memory in feedback_memories:
            if memory.source_type != "feedback":
                continue
            feedback_type = str(memory.metadata_json.get("feedback_type", ""))
            memory_features = {
                str(feature).lower()
                for feature in memory.metadata_json.get("features", [])
                if feature
            }
            overlap = candidate_features & memory_features
            if not overlap:
                continue
            if feedback_type == "confirm":
                adjustment += min(0.12, 0.03 * len(overlap))
            elif feedback_type == "dislike":
                adjustment -= min(0.25, 0.07 * len(overlap))
            elif feedback_type == "read_later":
                adjustment += min(0.05, 0.015 * len(overlap))
            matched.extend(sorted(overlap))
        return max(-0.35, min(0.2, adjustment)), list(dict.fromkeys(matched))[:8]

    @staticmethod
    def _build_explanation(
        candidate: CandidateItem,
        scores: dict[str, Any],
        *,
        feedback_adjustment: float = 0.0,
        matched_feedback: list[str] | None = None,
    ) -> dict[str, Any]:
        reasons = []
        matched_memories = matched_feedback or []

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
        if feedback_adjustment > 0:
            reasons.append("符合你过去的正向反馈")
        elif feedback_adjustment < 0:
            reasons.append("因过去的负向反馈降低排序")

        return {
            "why_recommended": "；".join(reasons) if reasons else "基于综合评分推荐",
            "matched_memories": matched_memories,
            "matched_interests": candidate.matched_interests or [],
            "feedback_adjustment": round(feedback_adjustment, 4),
            "freshness": f"新鲜度得分: {freshness:.2f}",
            "source_reason": f"来自数据源: {candidate.item_type}",
            "suggested_action": "建议查看详情或加入知识库",
        }
