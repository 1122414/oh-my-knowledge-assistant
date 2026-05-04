"""GitHub 搜索任务模型

SearchTask 是搜索源头治理的核心抽象。它将 sources.yaml 中的搜索配置
从简单 query 升级为结构化搜索任务，包含意图、关键词约束、负向词过滤、
star 分层、语言偏好等维度。

兼容旧配置：仅含 name/query/limit 的旧搜索配置自动转换为默认 SearchTask。
"""

from dataclasses import dataclass, field


VALID_INTENTS = {"discover_tool", "discover_framework", "discover_trend", "track_known_area"}


@dataclass
class SearchTask:
    """GitHub 搜索任务"""

    name: str
    query: str
    enabled: bool = True
    intent: str = "discover_tool"
    description: str = ""
    limit: int = 5
    priority: float = 1.0

    must_terms: list[str] = field(default_factory=list)
    nice_terms: list[str] = field(default_factory=list)
    negative_terms: list[str] = field(default_factory=list)

    languages: list[str] = field(default_factory=list)
    star_bands: list[str] = field(default_factory=lambda: ["20..300", "300..5000"])
    pushed_after_days: int = 365
    limit_per_query: int = 5

    def __post_init__(self):
        if self.intent not in VALID_INTENTS:
            raise ValueError(f"无效的搜索意图: {self.intent}，可选: {VALID_INTENTS}")

    @property
    def min_stars(self) -> int:
        left = self.star_bands[0].split("..")[0] if self.star_bands else "20"
        return int(left)

    @property
    def max_requests(self) -> int:
        return min(6, len(self.star_bands) * min(len(self.languages) or 1, 2) * 3)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "query": self.query,
            "enabled": self.enabled,
            "intent": self.intent,
            "description": self.description,
            "limit": self.limit,
            "priority": self.priority,
            "must_terms": self.must_terms,
            "nice_terms": self.nice_terms,
            "negative_terms": self.negative_terms,
            "languages": self.languages,
            "star_bands": self.star_bands,
            "pushed_after_days": self.pushed_after_days,
            "limit_per_query": self.limit_per_query,
        }


def search_task_from_config(config: dict) -> SearchTask:
    """从 sources.yaml 的搜索配置创建 SearchTask，兼容旧配置"""
    name = config.get("name", config.get("query", "unnamed"))
    query = config.get("query", "")
    limit = config.get("limit", config.get("limit_per_query", 5))

    return SearchTask(
        name=name,
        query=query,
        enabled=config.get("enabled", True),
        intent=config.get("intent", "discover_tool"),
        description=config.get("description", ""),
        limit=limit,
        priority=float(config.get("priority", 1.0)),
        must_terms=config.get("must_terms", []),
        nice_terms=config.get("nice_terms", []),
        negative_terms=config.get("negative_terms", []),
        languages=config.get("languages", []),
        star_bands=config.get("star_bands", ["20..300", "300..5000"]),
        pushed_after_days=int(config.get("pushed_after_days", 365)),
        limit_per_query=int(config.get("limit_per_query", config.get("limit", 5))),
    )


def search_tasks_from_yaml(yaml_data: dict) -> list[SearchTask]:
    """从 YAML 数据加载搜索任务列表"""
    searches = yaml_data.get("github", {}).get("searches", [])
    return [search_task_from_config(s) for s in searches if s.get("enabled", True)]
