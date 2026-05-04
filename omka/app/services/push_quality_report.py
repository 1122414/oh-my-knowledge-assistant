"""搜索质量报告服务

每日搜索任务完成后生成结构化质量报告，支持查看:
- 各搜索任务的召回量、过滤量、候选量
- 过滤原因分布
- 高贡献任务排名
"""

from dataclasses import dataclass, field


@dataclass
class SearchTaskReport:
    name: str
    intent: str
    request_count: int = 0
    fetched_count: int = 0
    unique_count: int = 0
    filtered_count: int = 0
    candidate_count: int = 0
    top_repos: list[str] = field(default_factory=list)
    filter_reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class SearchQualityReport:
    search_tasks: list[SearchTaskReport] = field(default_factory=list)
    total_request_count: int = 0
    total_unique_repos: int = 0
    total_candidates: int = 0
    top_contributing_tasks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "search_tasks": [
                {
                    "name": t.name,
                    "intent": t.intent,
                    "request_count": t.request_count,
                    "fetched_count": t.fetched_count,
                    "unique_count": t.unique_count,
                    "filtered_count": t.filtered_count,
                    "candidate_count": t.candidate_count,
                    "top_repos": t.top_repos[:3],
                    "filter_reasons": t.filter_reasons,
                }
                for t in self.search_tasks
            ],
            "total_request_count": self.total_request_count,
            "total_unique_repos": self.total_unique_repos,
            "total_candidates": self.total_candidates,
            "top_contributing_tasks": self.top_contributing_tasks[:5],
        }
