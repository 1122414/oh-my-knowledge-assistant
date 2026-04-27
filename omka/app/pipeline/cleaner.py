from typing import Any

from sqlmodel import select

from omka.app.connectors.github.connector import GitHubConnector
from omka.app.core.logging import logger
from omka.app.storage.db import NormalizedItem, RawItem, get_session


def clean_and_normalize() -> dict[str, Any]:
    """将 RawItem 转换为 NormalizedItem"""
    with get_session() as session:
        raw_items = session.exec(select(RawItem)).all()

    if not raw_items:
        logger.info("没有需要规范化的原始数据")
        return {"normalized_count": 0}

    connector = GitHubConnector()
    normalized_count = 0
    skipped_count = 0

    with get_session() as session:
        for raw in raw_items:
            try:
                normalized = connector.normalize(raw.model_dump())
                if not normalized:
                    skipped_count += 1
                    continue

                item = NormalizedItem(
                    id=normalized["id"],
                    source_type=normalized["source_type"],
                    source_id=normalized["source_id"],
                    item_type=normalized["item_type"],
                    title=normalized["title"],
                    url=normalized["url"],
                    content=normalized["content"],
                    author=normalized.get("author"),
                    repo_full_name=normalized.get("repo_full_name"),
                    published_at=normalized.get("published_at"),
                    updated_at=normalized.get("updated_at"),
                    fetched_at=normalized["fetched_at"],
                    tags=normalized.get("tags", []),
                    metadata=normalized.get("metadata", {}),
                    content_hash=compute_content_hash(normalized["title"], normalized["content"]),
                )
                session.merge(item)
                normalized_count += 1
            except Exception as e:
                logger.error("规范化失败 | raw_id=%s | error=%s", raw.id, e)
                skipped_count += 1

        session.commit()

    logger.info("规范化完成 | normalized=%d | skipped=%d", normalized_count, skipped_count)
    return {"normalized_count": normalized_count, "skipped_count": skipped_count}


def compute_content_hash(title: str, content: str) -> str:
    """计算内容指纹用于去重"""
    import hashlib
    text = (title + content[:1000]).lower().strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
