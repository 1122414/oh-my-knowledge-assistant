"""GitHub 搜索结果本地质量重排

对搜索返回的每个 repo 进行多维度质量评估。
结果写入 NormalizedItem.item_metadata，供 ranker 后续使用。
"""

import math
from datetime import datetime
from typing import Any


def compute_source_quality(
    repo_data: dict[str, Any],
    query: str,
    search_strategy: str,
    search_rank: int,
) -> dict[str, Any]:
    stars = repo_data.get("stargazers_count", 0)
    forks = repo_data.get("forks_count", 0)
    open_issues = repo_data.get("open_issues_count", 0)
    archived = repo_data.get("archived", False)
    disabled = repo_data.get("disabled", False)
    is_fork = repo_data.get("fork", False)
    name = (repo_data.get("full_name") or repo_data.get("name") or "").lower()
    description = (repo_data.get("description") or "").lower()
    topics = [t.lower() for t in repo_data.get("topics", [])]

    pushed_at = repo_data.get("pushed_at")
    updated_at = repo_data.get("updated_at")

    query_lower = query.lower()
    query_terms = [t.strip() for t in query_lower.split() if t.strip()]

    query_relevance = _compute_query_relevance(query_terms, name, description, topics)
    popularity = _compute_popularity(stars)
    freshness = _compute_freshness(pushed_at or updated_at)
    adoption = _compute_adoption(forks)
    rank_bonus = _compute_rank_bonus(search_rank)

    base_score = (
        query_relevance * 0.38
        + popularity * 0.28
        + freshness * 0.18
        + adoption * 0.10
        + rank_bonus * 0.06
    )

    if archived or disabled:
        base_score *= 0.0
    if is_fork:
        base_score *= 0.5
    if stars > 0 and open_issues / stars > 0.5:
        base_score *= 0.7

    reasons = []
    if query_relevance >= 0.6:
        reasons.append("high_query_relevance")
    if popularity >= 0.6:
        reasons.append("high_popularity")
    if freshness >= 0.8:
        reasons.append("high_freshness")
    if is_fork:
        reasons.append("is_fork")
    if archived:
        reasons.append("archived")

    return {
        "source_quality_score": round(min(base_score, 1.0), 4),
        "source_quality_reasons": reasons,
        "search_strategy": search_strategy,
        "search_rank": search_rank,
        "stars": stars,
        "forks": forks,
    }


def _compute_query_relevance(
    terms: list[str], name: str, description: str, topics: list[str]
) -> float:
    if not terms:
        return 0.5
    hits = 0
    search_text = f"{name} {description} {' '.join(topics)}"
    for term in terms:
        if term in search_text:
            hits += 1
    if name and any(t in name for t in terms):
        hits += 1
    return min(hits / max(len(terms), 1), 1.0)


def _compute_popularity(stars: int) -> float:
    if stars <= 0:
        return 0.0
    return min(math.log10(stars) / math.log10(100000), 1.0)


def _compute_freshness(last_activity: str | None) -> float:
    if not last_activity:
        return 0.3
    try:
        if isinstance(last_activity, str):
            dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
        else:
            dt = last_activity
        days = (datetime.utcnow().replace(tzinfo=None) - dt.replace(tzinfo=None)).days
        return max(0.0, 1.0 - days / 365.0)
    except (ValueError, TypeError):
        return 0.3


def _compute_adoption(forks: int) -> float:
    if forks <= 0:
        return 0.0
    return min(math.log10(forks) / math.log10(10000), 1.0)


def _compute_rank_bonus(rank: int) -> float:
    return 1.0 / (rank + 1)
