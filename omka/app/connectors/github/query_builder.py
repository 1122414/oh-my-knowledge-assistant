"""GitHub Search query builder

根据 SearchTask 配置生成实际 GitHub Search API query 字符串。
支持: star band, pushed date, language, search scope, negative terms。
"""

from datetime import datetime, timezone, timedelta

from omka.app.connectors.github.search_task import SearchTask
from omka.app.core.config import settings


SEARCH_SCOPES = [
    "in:name,description,topics",
    "in:readme",
]

SORT_STRATEGIES = [
    (None, "best_match"),
    ("updated", "updated"),
    ("stars", "stars"),
]

NOISE_TERMS = ["awesome", "tutorial", "template", "demo", "course"]


def build_github_queries(task: SearchTask) -> list[dict]:
    """为 SearchTask 生成一组 GitHub Search API 请求参数

    每个请求返回: {query: str, sort: str|None, per_page: int, scope: str, star_band: str}

    控制组合爆炸: 每个 task 最多 6 个请求
    """
    requests: list[dict] = []
    pushed_date = (
        datetime.now(timezone.utc) - timedelta(days=task.pushed_after_days)
    ).strftime("%Y-%m-%d")

    star_bands = task.star_bands[:2]
    languages = task.languages[:2] if task.languages else [""]
    scopes = SEARCH_SCOPES[:2]
    strategies = SORT_STRATEGIES[:3]

    for star_band in star_bands:
        for lang in languages:
            lang_part = f" language:{lang}" if lang else ""
            for scope in scopes:
                base = f"{build_base_query(task, star_band, pushed_date)}{lang_part} {scope}"
                for sort_param, strategy_name in strategies:
                    if len(requests) >= task.max_requests:
                        break
                    negative_part = build_negative_part(task)
                    full_query = f"{base}{negative_part}"
                    requests.append({
                        "query": full_query,
                        "sort": sort_param,
                        "per_page": task.limit_per_query,
                        "scope": scope,
                        "star_band": star_band,
                        "strategy": strategy_name,
                        "language": lang or None,
                        "task_name": task.name,
                    })
                if len(requests) >= task.max_requests:
                    break
            if len(requests) >= task.max_requests:
                break

    return requests


def build_base_query(task: SearchTask, star_band: str, pushed_date: str) -> str:
    query = task.query
    if star_band:
        stars_part = star_band.replace("..", "..")
        query = f"{query} stars:{stars_part}"
    return f"{query} archived:false fork:false pushed:>{pushed_date}"


def build_negative_part(task: SearchTask) -> str:
    """构建负向词 NOT 子句，仅对明确噪声词"""
    parts = []
    for term in task.negative_terms:
        if term in NOISE_TERMS:
            parts.append(f"NOT {term}")
    return " " + " ".join(parts) if parts else ""


def build_metadata(task: SearchTask, request: dict) -> dict:
    """构建搜索结果 metadata，记录搜索来源证据"""
    return {
        "search_task_name": task.name,
        "search_task_intent": task.intent,
        "search_task_priority": task.priority,
        "actual_query": request["query"],
        "search_scope": request["scope"],
        "search_strategy": request["strategy"],
        "star_band": request["star_band"],
        "language": request.get("language"),
    }
