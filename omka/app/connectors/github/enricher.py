"""GitHub Repo Enricher

轻量 enrich 候选仓库，仅获取 repo detail 和 README excerpt。
每日 enrich 总量受 SEARCH_DAILY_ENRICH_LIMIT 控制。
"""

from omka.app.connectors.github.client import GitHubClient
from omka.app.core.config import settings
from omka.app.core.logging import logger


async def enrich_repo_profile(repo_full_name: str) -> dict | None:
    """获取仓库详细信息，返回 github_profile dict"""
    client = GitHubClient()
    try:
        async with client:
            owner, repo = repo_full_name.split("/", 1)
            repo_data = await client.get_repo(owner, repo)
            readme = await client.get_readme(owner, repo)
            release = await client.get_latest_release(owner, repo, per_page=1)
    except Exception as e:
        logger.error("enrich 失败 | repo=%s | error=%s", repo_full_name, e)
        return None

    if not repo_data:
        return None

    return {
        "full_name": repo_data.get("full_name"),
        "description": repo_data.get("description", ""),
        "stars": repo_data.get("stargazers_count", 0),
        "forks": repo_data.get("forks_count", 0),
        "language": repo_data.get("language", ""),
        "license": repo_data.get("license", {}).get("spdx_id", "") if repo_data.get("license") else "",
        "homepage": repo_data.get("homepage", ""),
        "default_branch": repo_data.get("default_branch", ""),
        "pushed_at": repo_data.get("pushed_at", ""),
        "created_at": repo_data.get("created_at", ""),
        "subscribers_count": repo_data.get("subscribers_count", 0),
        "network_count": repo_data.get("network_count", 0),
        "open_issues_count": repo_data.get("open_issues_count", 0),
        "topics": repo_data.get("topics", []),
        "readme_excerpt": readme[:500] if readme else "",
        "latest_release": release[0].get("tag_name", "") if release and len(release) > 0 else "",
    }
