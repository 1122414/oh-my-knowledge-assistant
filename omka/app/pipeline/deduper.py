from typing import Any

from sqlmodel import select

from omka.app.core.logging import logger
from omka.app.storage.db import CandidateItem, NormalizedItem, get_session


def dedup_and_create_candidates() -> dict[str, Any]:
    """去重并创建候选条目"""
    with get_session() as session:
        normalized_items = session.exec(select(NormalizedItem)).all()

    if not normalized_items:
        logger.info("没有需要处理的规范化数据")
        return {"candidate_count": 0, "duplicate_count": 0}

    seen_urls = set()
    seen_hashes = set()
    candidate_count = 0
    duplicate_count = 0

    with get_session() as session:
        existing_candidates = session.exec(select(CandidateItem)).all()
        for c in existing_candidates:
            seen_urls.add(c.url)
            normalized = session.get(NormalizedItem, c.normalized_item_id)
            if normalized:
                seen_hashes.add(normalized.content_hash)

        for item in normalized_items:
            if item.url in seen_urls:
                duplicate_count += 1
                continue
            if item.content_hash in seen_hashes:
                duplicate_count += 1
                continue

            seen_urls.add(item.url)
            seen_hashes.add(item.content_hash)

            candidate = CandidateItem(
                id=f"candidate:{item.id}",
                normalized_item_id=item.id,
                title=item.title,
                url=item.url,
                item_type=item.item_type,
                status="pending",
            )
            session.merge(candidate)
            candidate_count += 1

        session.commit()

    logger.info(
        "候选池更新完成 | candidates=%d | duplicates=%d",
        candidate_count,
        duplicate_count,
    )
    return {
        "candidate_count": candidate_count,
        "duplicate_count": duplicate_count,
    }
