from typing import Any

from sqlmodel import select

from omka.app.connectors.registry import ConnectorRegistry
from omka.app.core.logging import logger
from omka.app.storage.db import NormalizedItem, RawItem, get_session


def clean_and_normalize() -> dict[str, Any]:
    with get_session() as session:
        existing_ids = {
            row[0] for row in session.exec(select(NormalizedItem.id)).all()
        }
        if existing_ids:
            raw_items = session.exec(
                select(RawItem).where(RawItem.id.notin_(existing_ids))
            ).all()
        else:
            raw_items = session.exec(select(RawItem)).all()

    pending_raws = raw_items

    if not pending_raws:
        logger.info("没有需要规范化的原始数据")
        return {"normalized_count": 0}

    normalized_count = 0
    skipped_count = 0

    with get_session() as session:
        for raw in pending_raws:
            try:
                connector = ConnectorRegistry.get(raw.source_type)
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
                    item_metadata=normalized.get("item_metadata", {}),
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
    import hashlib
    text = (title + content[:1000]).lower().strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
