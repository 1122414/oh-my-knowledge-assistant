"""GitHub 搜索质量重排器

对多策略召回的搜索结果进行本地质量评分，
输出 0-1 的 source_quality_score 供 downstream ranker 使用。

权重设计:
- 查询相关度 0.38: 检查 query term 是否命中 name/full_name/description/topics
- popularity 0.28: log10(stars) / log10(100000) 标准化到 0-1
- freshness 0.18: max(0, 1 - days_since_push / 365)
- adoption 0.10: log10(forks) / log10(10000)
- GitHub rank bonus 0.06: 1 / (rank + 1)

惩罚项:
- archived → score *= 0
- fork → score *= 0.5
- open_issues / max(stars, 1) > 0.5 → score *= 0.7
"""

import math
from datetime import datetime, timezone
from typing import Any

WEIGHT_RELEVANCE = 0.38
WEIGHT_POPULARITY = 0.28
WEIGHT_FRESHNESS = 0.18
WEIGHT_ADOPTION = 0.10
WEIGHT_RANK_BONUS = 0.06


def compute_source_quality(
    item: dict[str, Any],
    query: str,
    strategy_name: str,
    rank: int,
) -> dict[str, Any]:
    """为单个搜索结果计算质量分。

    Args:
        item: GitHub search API 返回的 repo 对象
        query: 原始搜索查询
        strategy_name: 召回策略 (best_match/stars/updated)
        rank: 在该策略中的排名 (1-indexed)

    Returns:
        dict with source_quality_score, source_quality_reasons,
        search_strategy, search_rank
    """
    reasons: list[str] = []

    relevance_score = _compute_relevance(item, query)
    if relevance_score >= 0.5:
        reasons.append(f"查询匹配度={relevance_score:.2f}")

    stars = item.get("stargazers_count", 0)
    popularity = _normalize_log(stars, 100_000)
    if popularity >= 0.3:
        reasons.append(f"流行度={popularity:.2f} (stars={stars})")

    freshness = _compute_freshness(item)
    if freshness >= 0.5:
        days_ago = _days_since_push(item)
        reasons.append(f"新鲜度={freshness:.2f} (last_push={days_ago}d ago)")

    forks = item.get("forks_count", 0)
    adoption = _normalize_log(forks, 10_000)

    rank_bonus = 1.0 / (rank + 1)

    score = (
        WEIGHT_RELEVANCE * relevance_score
        + WEIGHT_POPULARITY * popularity
        + WEIGHT_FRESHNESS * freshness
        + WEIGHT_ADOPTION * adoption
        + WEIGHT_RANK_BONUS * rank_bonus
    )

    if item.get("archived"):
        reasons.append("已归档")
        score *= 0

    if item.get("fork"):
        reasons.append("Fork 仓库")
        score *= 0.5

    if stars > 0:
        open_issues = item.get("open_issues_count", 0)
        if open_issues / stars > 0.5:
            reasons.append("Issues/Stars 比率过高(>0.5)")
            score *= 0.7

    return {
        "source_quality_score": round(max(0.0, min(1.0, score)), 4),
        "source_quality_reasons": reasons,
        "search_strategy": strategy_name,
        "search_rank": rank,
    }


def _compute_relevance(item: dict[str, Any], query: str) -> float:
    if not query:
        return 0.0

    query_lower = query.lower()
    query_terms = set(query_lower.split())
    if not query_terms:
        return 0.0

    name = (item.get("name") or "").lower()
    full_name = (item.get("full_name") or "").lower()
    description = (item.get("description") or "").lower()
    topics = [t.lower() for t in (item.get("topics") or [])]

    hits = 0
    max_hits = len(query_terms) * 4

    for term in query_terms:
        if term in name:
            hits += 1
        if term in full_name:
            hits += 1
        if term in description:
            hits += 1
        if any(term in topic for topic in topics):
            hits += 1

    return min(hits / max_hits, 1.0)


def _compute_freshness(item: dict[str, Any]) -> float:
    days = _days_since_push(item)
    if days is None:
        return 0.0
    return max(0.0, 1.0 - days / 365)


def _days_since_push(item: dict[str, Any]) -> float | None:
    pushed_at = item.get("pushed_at")
    if not pushed_at:
        return None

    if isinstance(pushed_at, str):
        try:
            pushed_dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        except ValueError:
            return None
    elif isinstance(pushed_at, datetime):
        pushed_dt = pushed_at
    else:
        return None

    return (datetime.now(timezone.utc) - pushed_dt).days


def _normalize_log(value: int, ceiling: int) -> float:
    if value <= 0:
        return 0.0
    return min(math.log10(value) / math.log10(ceiling), 1.0)
