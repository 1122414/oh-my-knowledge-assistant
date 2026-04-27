"""存储层工具函数

提供数据操作相关的辅助函数，避免核心逻辑与存储实现耦合。
"""

import hashlib
import json
from typing import Any

from omka.app.storage.db import RawItem, SourceConfig, get_session


def compute_raw_item_id(item_type: str, source_id: str, raw_data: dict[str, Any]) -> str:
    """生成稳定的 RawItem ID，避免 hash() 的随机性问题"""
    data_str = json.dumps(raw_data, sort_keys=True, ensure_ascii=False, default=str)
    hash_value = hashlib.sha256(f"{item_type}:{source_id}:{data_str}".encode("utf-8")).hexdigest()
    return f"{item_type}:{source_id}:{hash_value[:16]}"


def save_raw_items(raw_items: list[dict[str, Any]], source_config: SourceConfig) -> int:
    with get_session() as session:
        for item in raw_items:
            raw = RawItem(
                id=compute_raw_item_id(item["item_type"], source_config.id, item["raw_data"]),
                source_id=source_config.id,
                source_type=source_config.source_type,
                item_type=item["item_type"],
                fetch_url=item["fetch_url"],
                http_status=item["http_status"],
                raw_data=item["raw_data"],
                fetched_at=item["fetched_at"],
            )
            session.merge(raw)
        session.commit()
    return len(raw_items)


def load_profile_sources() -> int:
    """从 data/profiles/sources.yaml 加载预配置的数据源到数据库

    返回成功加载的数量。
    """
    from omka.app.profiles.profile_loader import load_sources_config

    config = load_sources_config()
    github_config = config.get("github", {})

    loaded = 0
    with get_session() as session:
        for repo in github_config.get("repos", []):
            source_id = f"src_github_{repo.replace('/', '_')}"
            existing = session.get(SourceConfig, source_id)
            if not existing:
                source = SourceConfig(
                    id=source_id,
                    source_type="github",
                    name=repo.split("/")[-1],
                    enabled=True,
                    mode="repo",
                    repo_full_name=repo,
                    weight=1.0,
                )
                session.merge(source)
                loaded += 1

        for search in github_config.get("searches", []):
            source_id = f"src_search_{search['name'].lower().replace(' ', '_')}"
            existing = session.get(SourceConfig, source_id)
            if not existing:
                source = SourceConfig(
                    id=source_id,
                    source_type="github",
                    name=search["name"],
                    enabled=True,
                    mode="search",
                    query=search["query"],
                    limit=search.get("limit", 5),
                    weight=1.0,
                )
                session.merge(source)
                loaded += 1

        session.commit()

    return loaded
