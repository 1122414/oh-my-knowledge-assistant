from datetime import datetime
from typing import Any

from omka.app.connectors.github.schemas import GitHubReleaseData, GitHubRepoData


def _extract_owner_login(raw: dict[str, Any]) -> str | None:
    """从原始数据中提取仓库所有者登录名"""
    if "owner_login" in raw:
        return raw["owner_login"]
    owner = raw.get("owner")
    if isinstance(owner, dict):
        return owner.get("login")
    return None


def _parse_repo(raw: dict[str, Any], search_query: str | None = None) -> GitHubRepoData:
    data = dict(raw)
    if "owner_login" not in data:
        data["owner_login"] = _extract_owner_login(raw)
    if "api_url" not in data:
        data["api_url"] = data.get("url")
    repo = GitHubRepoData.model_validate(data)
    if search_query:
        repo.search_query = search_query
        repo.search_score = raw.get("score")
    return repo


def normalize_repo(raw: dict[str, Any], source_id: str, search_query: str | None = None) -> dict[str, Any]:
    """将 GitHub repo 原始数据转换为 NormalizedItem"""
    repo = _parse_repo(raw, search_query)

    content_parts = [
        repo.description or "",
        f"Topics: {', '.join(repo.topics)}",
        f"Language: {repo.language or 'N/A'}",
        f"Stars: {repo.stargazers_count}",
        f"Forks: {repo.forks_count}",
    ]
    if repo.pushed_at:
        content_parts.append(f"Recently pushed at: {repo.pushed_at.isoformat()}")

    return {
        "id": f"github:repo:{repo.full_name}",
        "source_type": "github",
        "source_id": source_id,
        "item_type": "repo",
        "title": repo.full_name,
        "url": repo.html_url,
        "content": "\n".join(filter(None, content_parts)),
        "author": repo.owner_login,
        "repo_full_name": repo.full_name,
        "published_at": repo.created_at,
        "updated_at": repo.updated_at,
        "fetched_at": datetime.utcnow(),
        "tags": repo.topics + ([repo.language] if repo.language else []),
        "item_metadata": {
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "language": repo.language,
            "open_issues": repo.open_issues_count,
            "archived": repo.archived,
            "search_query": search_query,
            "search_score": repo.search_score,
        },
    }


def normalize_release(raw: dict[str, Any], repo_full_name: str, source_id: str) -> dict[str, Any]:
    """将 GitHub release 原始数据转换为 NormalizedItem"""
    data = {**raw, "repo_full_name": repo_full_name}
    if "api_url" not in data:
        data["api_url"] = data.get("url")
    release = GitHubReleaseData.model_validate(data)

    return {
        "id": f"github:release:{repo_full_name}:{release.tag_name}",
        "source_type": "github",
        "source_id": source_id,
        "item_type": "release",
        "title": f"{repo_full_name} {release.tag_name}: {release.name or ''}".strip(),
        "url": release.html_url,
        "content": release.body or release.name or "",
        "author": release.author_login,
        "repo_full_name": repo_full_name,
        "published_at": release.published_at,
        "updated_at": release.created_at,
        "fetched_at": datetime.utcnow(),
        "tags": ["release", repo_full_name],
        "item_metadata": {
            "tag_name": release.tag_name,
            "draft": release.draft,
            "prerelease": release.prerelease,
        },
    }


def normalize_search_repo(raw: dict[str, Any], source_id: str, search_query: str) -> dict[str, Any]:
    repo = _parse_repo(raw, search_query)

    content_parts = [
        repo.description or "",
        f"Topics: {', '.join(repo.topics)}",
        f"Language: {repo.language or 'N/A'}",
        f"Stars: {repo.stargazers_count}",
        f"Updated at: {repo.updated_at.isoformat()}",
    ]

    quality = raw.get("_source_quality", {})

    return {
        "id": f"github:search_repo:{repo.full_name}",
        "source_type": "github",
        "source_id": source_id,
        "item_type": "repo_search_result",
        "title": repo.full_name,
        "url": repo.html_url,
        "content": "\n".join(filter(None, content_parts)),
        "author": repo.owner_login,
        "repo_full_name": repo.full_name,
        "published_at": repo.created_at,
        "updated_at": repo.updated_at,
        "fetched_at": datetime.utcnow(),
        "tags": repo.topics + ([repo.language] if repo.language else []),
        "item_metadata": {
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "language": repo.language,
            "search_query": search_query,
            "search_score": repo.search_score,
            "source_quality_score": quality.get("source_quality_score", 0),
            "source_quality_reasons": quality.get("source_quality_reasons", []),
            "search_strategy": quality.get("search_strategy", ""),
            "search_rank": quality.get("search_rank", 0),
        },
    }
