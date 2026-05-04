from datetime import datetime, timezone
from typing import Any

from omka.app.connectors.base import SourceConnector
from omka.app.connectors.github.client import GitHubClient
from omka.app.connectors.github.normalizer import (
    normalize_release,
    normalize_repo,
    normalize_search_repo,
)
from omka.app.connectors.github.query_builder import build_github_queries, build_metadata
from omka.app.connectors.github.search_task import search_task_from_config
from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.pipeline.quality_reranker import compute_source_quality


class GitHubConnector(SourceConnector):
    source_type = "github"

    def __init__(self):
        self.client = GitHubClient()
        self._daily_requests = 0

    async def fetch(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        mode = config.get("mode")
        source_id = config.get("id", "unknown")
        results: list[dict[str, Any]] = []

        async with self.client:
            if mode == "repo":
                results = await self._fetch_repo(config, source_id)
            elif mode == "search":
                results = await self._fetch_search(config, source_id)
            else:
                logger.warning("未知的 GitHub 模式 | mode=%s", mode)

        return results

    async def _fetch_repo(self, config: dict[str, Any], source_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        repo_full_name = config.get("repo_full_name", "")
        if not repo_full_name:
            logger.warning("repo 模式缺少 repo_full_name | source_id=%s", source_id)
            return results

        owner, repo = repo_full_name.split("/", 1)

        try:
            repo_data = await self.client.get_repo(owner, repo)
            if repo_data:
                results.append({
                    "item_type": "github_repo",
                    "source_id": source_id,
                    "fetch_url": f"{settings.github_api_base_url}/repos/{owner}/{repo}",
                    "http_status": 200,
                    "raw_data": repo_data,
                    "fetched_at": datetime.now(timezone.utc),
                })
        except Exception as e:
            logger.error("抓取仓库失败 | repo=%s | error=%s", repo_full_name, e)

        try:
            releases = await self.client.get_latest_release(
                owner, repo, per_page=settings.releases_per_repo
            )
            for release in releases:
                results.append({
                    "item_type": "github_release",
                    "source_id": source_id,
                    "fetch_url": f"{settings.github_api_base_url}/repos/{owner}/{repo}/releases",
                    "http_status": 200,
                    "raw_data": release,
                    "fetched_at": datetime.now(timezone.utc),
                })
        except Exception as e:
            logger.error("抓取 Release 失败 | repo=%s | error=%s", repo_full_name, e)

        return results

    async def _fetch_search(self, config: dict[str, Any], source_id: str) -> list[dict[str, Any]]:
        if self._daily_requests >= settings.search_daily_request_limit:
            logger.warning("已达每日请求上限 | limit=%d", settings.search_daily_request_limit)
            return []

        task = search_task_from_config(config)
        if not task.query:
            logger.warning("search 模式缺少 query | source_id=%s", source_id)
            return []

        results: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        rank_counter = 0
        filter_reasons: dict[str, int] = {}

        queries = build_github_queries(task)
        logger.info(
            "搜索任务开始 | task=%s | intent=%s | queries=%d",
            task.name, task.intent, len(queries),
        )

        for req in queries:
            if self._daily_requests >= settings.search_daily_request_limit:
                logger.warning("触及每日请求上限 | task=%s", task.name)
                break

            self._daily_requests += 1
            try:
                items = await self.client.search_repositories(
                    req["query"], per_page=req["per_page"], sort=req["sort"],
                )
            except Exception as e:
                logger.error("搜索仓库失败 | task=%s | query=%s | error=%s", task.name, req["query"][:80], e)
                continue

            for item in items:
                full_name = item.get("full_name", "")
                if full_name in seen_names or not full_name:
                    continue

                reason = _check_source_filter(item, task)
                if reason:
                    filter_reasons[reason] = filter_reasons.get(reason, 0) + 1
                    continue

                seen_names.add(full_name)
                rank_counter += 1

                quality = compute_source_quality(item, task.query, req["strategy"], rank_counter)
                metadata = build_metadata(task, req)
                metadata["source_quality_score"] = quality.get("source_quality_score", 0)
                metadata["source_quality_reasons"] = quality.get("source_quality_reasons", [])
                metadata["source_filter_reasons"] = []

                item["_source_quality"] = quality
                item["_search_metadata"] = metadata

                results.append({
                    "item_type": "github_repo_search_result",
                    "source_id": source_id,
                    "fetch_url": f"{settings.github_api_base_url}/search/repositories?q={req['query'][:100]}",
                    "http_status": 200,
                    "raw_data": item,
                    "fetched_at": datetime.now(timezone.utc),
                    "search_metadata": metadata,
                })

                if len(seen_names) >= settings.search_max_candidates_per_query:
                    break

            if len(seen_names) >= settings.search_max_candidates_per_query:
                break

        logger.info(
            "搜索任务完成 | task=%s | candidates=%d | filtered=%s | requests=%d",
            task.name, len(seen_names), filter_reasons, self._daily_requests,
        )
        return results

    def normalize(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        item_type = raw_item.get("item_type")
        source_id = raw_item.get("source_id", "")
        raw_data = raw_item.get("raw_data", {})

        if item_type == "github_repo":
            return normalize_repo(raw_data, source_id)
        elif item_type == "github_release":
            repo_full_name = raw_data.get("repo_full_name", "")
            if not repo_full_name and raw_data.get("url"):
                parts = raw_data["url"].split("/repos/")[-1].split("/releases")[0].split("/")
                if len(parts) >= 2:
                    repo_full_name = f"{parts[0]}/{parts[1]}"
            return normalize_release(raw_data, repo_full_name, source_id)
        elif item_type == "github_repo_search_result":
            search_query = raw_item.get("fetch_url", "").split("q=")[-1].split("&")[0]
            result = normalize_search_repo(raw_data, source_id, search_query)
            if raw_item.get("search_metadata"):
                result["item_metadata"] = {
                    **(result.get("item_metadata", {})),
                    **(raw_item["search_metadata"]),
                }
            return result
        else:
            raise ValueError(f"未知的 item_type: {item_type}")


def _check_source_filter(item: dict[str, Any], task) -> str | None:
    """源头过滤检查，返回过滤原因或 None（通过）"""
    if item.get("archived") or item.get("disabled"):
        return "archived_or_disabled"

    if item.get("fork", False):
        return "fork"

    stars = item.get("stargazers_count", 0)
    if stars < task.min_stars:
        return "low_stars"

    pushed_at = item.get("pushed_at", "")
    if pushed_at:
        try:
            pushed_dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            days_since = (datetime.now(timezone.utc) - pushed_dt).days
            if days_since > task.pushed_after_days * 2:
                return "stale"
        except (ValueError, TypeError):
            pass

    if task.must_terms:
        name = (item.get("name") or "").lower()
        description = (item.get("description") or "").lower()
        topics = [t.lower() for t in (item.get("topics") or [])]
        searchable = f"{name} {description} {' '.join(topics)}"
        if not any(term.lower() in searchable for term in task.must_terms):
            return "must_terms_not_matched"

    return None
