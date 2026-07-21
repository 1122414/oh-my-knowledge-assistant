from datetime import datetime
from typing import Any

from sqlmodel import select

from omka.app.core.config import settings
from omka.app.core.logging import get_logger, trace
from omka.app.profiles.interest_model import UserProfile
from omka.app.storage.db import CandidateItem, NormalizedItem, get_session

logger = get_logger("pipeline")

@trace("pipeline")
def rank_candidates() -> dict[str, Any]:
    profile = UserProfile.load()
    with get_session() as session:
        candidates = session.exec(
            select(CandidateItem).where(CandidateItem.status == "pending")
        ).all()

    if not candidates:
        logger.info("没有待排序的候选条目")
        return {"ranked_count": 0}

    ranked_count = 0
    ignored_count = 0
    with get_session() as session:
        for candidate in candidates:
            normalized = session.get(NormalizedItem, candidate.normalized_item_id)
            if not normalized:
                continue

            scores = compute_scores(normalized, profile)
            final_score = (
                scores["interest_score"] * settings.score_weight_interest
                + scores["project_score"] * settings.score_weight_project
                + scores["freshness_score"] * settings.score_weight_freshness
                + scores["popularity_score"] * settings.score_weight_popularity
                + scores["source_quality_score"] * settings.score_weight_source_quality
            )

            candidate.score = round(final_score, 4)
            candidate.score_detail = scores
            candidate.matched_interests = scores.get("matched_interests", [])
            candidate.matched_projects = scores.get("matched_projects", [])

            if final_score < settings.candidate_score_threshold:
                candidate.status = "ignored"
                ignored_count += 1
            else:
                ranked_count += 1
            session.add(candidate)

        session.commit()

    logger.info("排序完成 | ranked=%d | ignored=%d", ranked_count, ignored_count)
    return {"ranked_count": ranked_count, "ignored_count": ignored_count}


def compute_scores(item: NormalizedItem, profile: UserProfile) -> dict[str, Any]:
    text = (item.title + " " + item.content).lower()
    tags_lower = [t.lower() for t in item.tags]

    interest_score = 0.0
    matched_interests = []
    for interest in profile.interests:
        for kw in interest.keywords:
            kw_lower = kw.lower()
            if kw_lower in text or kw_lower in tags_lower:
                interest_score += interest.weight
                if interest.name not in matched_interests:
                    matched_interests.append(interest.name)
                break

    project_score = 0.0
    matched_projects = []
    for project in profile.projects:
        for kw in project.keywords:
            kw_lower = kw.lower()
            if kw_lower in text or kw_lower in tags_lower:
                project_score += project.weight
                if project.name not in matched_projects:
                    matched_projects.append(project.name)
                break

    freshness_score = compute_freshness_score(item.updated_at or item.published_at)
    popularity_score = compute_popularity_score(item.item_metadata)
    source_quality_score = item.item_metadata.get("source_quality_score", 0)

    search_score = item.item_metadata.get("search_score")
    if search_score is not None and search_score > 0:
        relevance = min(search_score * 2, 1.0)
        interest_score *= max(relevance, 0.1)
        project_score *= max(relevance, 0.1)

    return {
        "interest_score": round(min(interest_score, 5.0), 4),
        "project_score": round(min(project_score, 5.0), 4),
        "freshness_score": round(freshness_score, 4),
        "popularity_score": round(popularity_score, 4),
        "source_quality_score": round(source_quality_score, 4),
        "matched_interests": matched_interests,
        "matched_projects": matched_projects,
    }


def compute_freshness_score(updated_at: datetime | None) -> float:
    if not updated_at:
        return 0.5
    days_ago = (datetime.utcnow() - updated_at).days
    decay = settings.freshness_decay_days
    if days_ago <= 0:
        return 1.0
    if days_ago >= decay * 2:
        return 0.1
    return max(0.1, 1.0 - (days_ago / decay))


def compute_popularity_score(metadata: dict[str, Any]) -> float:
    stars = metadata.get("stars", 0)
    if stars >= 10000:
        return 1.0
    if stars >= 1000:
        return 0.8
    if stars >= 100:
        return 0.6
    if stars >= 10:
        return 0.4
    return 0.2
