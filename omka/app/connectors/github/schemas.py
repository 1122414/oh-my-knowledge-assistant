from datetime import datetime

from pydantic import BaseModel


class GitHubRepoData(BaseModel):
    """GitHub 仓库事实数据"""

    id: int
    node_id: str | None = None

    full_name: str
    name: str
    owner_login: str | None = None

    html_url: str
    api_url: str | None = None

    description: str | None = None
    topics: list[str] = []
    language: str | None = None

    stargazers_count: int = 0
    forks_count: int = 0
    watchers_count: int = 0
    open_issues_count: int = 0

    default_branch: str | None = None

    archived: bool = False
    disabled: bool = False
    fork: bool = False
    private: bool = False

    license_name: str | None = None
    license_spdx_id: str | None = None

    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None = None

    search_query: str | None = None
    search_score: float | None = None


class GitHubReleaseData(BaseModel):
    """GitHub Release 事实数据"""

    id: int
    repo_full_name: str

    tag_name: str
    name: str | None = None
    body: str | None = None

    html_url: str
    api_url: str | None = None

    author_login: str | None = None

    draft: bool = False
    prerelease: bool = False

    created_at: datetime | None = None
    published_at: datetime | None = None

