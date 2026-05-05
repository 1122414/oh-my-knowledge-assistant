"""存储层工具函数

提供数据操作相关的辅助函数，避免核心逻辑与存储实现耦合。
"""

import hashlib
import json
from datetime import datetime
from typing import Any

from omka.app.storage.db import RawItem, SourceConfig, get_session
from sqlmodel import select


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
    """从 data/profiles/sources.yaml 同步预配置的数据源到数据库

    新增 YAML 中存在但 DB 中不存在的源，禁用 DB 中存在但 YAML 中已删除的源（仅 yaml 管理的前缀 src_*）。
    返回变更数量。
    """
    from omka.app.profiles.profile_loader import load_sources_config
    from omka.app.core.logging import logger

    config = load_sources_config()
    github_config = config.get("github", {})

    changed = 0

    expected_ids: set[str] = set()
    for repo in github_config.get("repos", []):
        expected_ids.add(f"src_github_{repo.replace('/', '_')}")
    for search in github_config.get("searches", []):
        expected_ids.add(f"src_search_{search['name'].lower().replace(' ', '_')}")

    with get_session() as session:
        db_configs = session.exec(select(SourceConfig)).all()
        db_ids = {c.id for c in db_configs}

        yaml_managed_in_db = {cid for cid in db_ids if cid.startswith("src_")}
        stale_ids = yaml_managed_in_db - expected_ids
        for stale_id in stale_ids:
            source = session.get(SourceConfig, stale_id)
            if source and source.enabled:
                source.enabled = False
                source.updated_at = datetime.utcnow()
                session.add(source)
                logger.info("禁用已不再 YAML 中的源 | id=%s", stale_id)
                changed += 1
        if stale_ids:
            session.commit()

        new_ids = expected_ids - db_ids
        for repo in github_config.get("repos", []):
            source_id = f"src_github_{repo.replace('/', '_')}"
            if source_id in new_ids:
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
                changed += 1

        for search in github_config.get("searches", []):
            source_id = f"src_search_{search['name'].lower().replace(' ', '_')}"
            if source_id in new_ids:
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
                changed += 1

        session.commit()

    return changed
