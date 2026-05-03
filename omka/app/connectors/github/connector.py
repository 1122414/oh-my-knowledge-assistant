from datetime import datetime
from typing import Any

from omka.app.connectors.base import SourceConnector
from omka.app.connectors.github.client import GitHubClient
from omka.app.connectors.github.normalizer import (
    normalize_release,
    normalize_repo,
    normalize_search_repo,
)
from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.pipeline.quality_reranker import compute_source_quality


class GitHubConnector(SourceConnector):
    source_type = "github"

    def __init__(self):
        self.client = GitHubClient()

    async def fetch(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        mode = config.get("mode")
        source_id = config.get("id", "unknown")
        results: list[dict[str, Any]] = []

        async with self.client:
            if mode == "repo":
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
                            "fetched_at": datetime.utcnow(),
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
                            "fetched_at": datetime.utcnow(),
                        })
                except Exception as e:
                    logger.error("抓取 Release 失败 | repo=%s | error=%s", repo_full_name, e)

            elif mode == "search":
                query = config.get("query", "")
                limit = config.get("limit", settings.search_results_per_query)
                if not query:
                    logger.warning("search 模式缺少 query | source_id=%s", source_id)
                    return results

                try:
                    strategies = _get_search_strategies()
                    seen_names: set[str] = set()
                    rank_counter = 0

                    for strategy_name, sort_param in strategies:
                        items = await self.client.search_repositories(
                            query, per_page=limit, sort=sort_param,
                        )
                        for item in items:
                            full_name = item.get("full_name", "")
                            if full_name in seen_names:
                                continue

                            if item.get("archived") or item.get("disabled"):
                                continue

                            stars = item.get("stargazers_count", 0)
                            if stars < settings.search_min_stars:
                                continue

                            is_fork = item.get("fork", False)
                            if is_fork:
                                continue

                            seen_names.add(full_name)
                            rank_counter += 1

                            quality = compute_source_quality(
                                item, query, strategy_name, rank_counter,
                            )
                            item["_source_quality"] = quality

                            results.append({
                                "item_type": "github_repo_search_result",
                                "source_id": source_id,
                                "fetch_url": f"{settings.github_api_base_url}/search/repositories?q={query}",
                                "http_status": 200,
                                "raw_data": item,
                                "fetched_at": datetime.utcnow(),
                            })

                            if len(seen_names) >= settings.search_max_candidates_per_query:
                                break

                        if len(seen_names) >= settings.search_max_candidates_per_query:
                            break

                except Exception as e:
                    logger.error("搜索仓库失败 | query=%s | error=%s", query, e)

            else:
                logger.warning("未知的 GitHub 模式 | mode=%s", mode)

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
            return normalize_search_repo(raw_data, source_id, search_query)
        else:
            raise ValueError(f"未知的 item_type: {item_type}")


def _get_search_strategies() -> list[tuple[str, str | None]]:
    if settings.search_expand_queries:
        return [
            ("best_match", None),
            ("stars", "stars"),
            ("updated", "updated"),
        ]
    return [("updated", "updated")]
