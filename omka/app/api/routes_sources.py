from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from omka.app.core.logging import logger
from omka.app.storage.db import SourceConfig, get_session

router = APIRouter()


@router.get("", response_model=list[dict[str, Any]])
async def list_sources():
    with get_session() as session:
        configs = session.exec(select(SourceConfig)).all()
        return [
            {
                "id": c.id,
                "source_type": c.source_type,
                "name": c.name,
                "enabled": c.enabled,
                "mode": c.mode,
                "repo_full_name": c.repo_full_name,
                "query": c.query,
                "limit": c.limit,
                "weight": c.weight,
                "last_fetched_at": c.last_fetched_at,
            }
            for c in configs
        ]


@router.post("")
async def create_source(data: dict[str, Any]):
    config = SourceConfig(**data)
    with get_session() as session:
        session.add(config)
        session.commit()
        logger.info("创建数据源 | id=%s | mode=%s", config.id, config.mode)
    return {"id": config.id, "message": "数据源已创建"}


@router.put("/{source_id}")
async def update_source(source_id: str, data: dict[str, Any]):
    with get_session() as session:
        config = session.get(SourceConfig, source_id)
        if not config:
            raise HTTPException(status_code=404, detail="数据源不存在")
        for key, value in data.items():
            setattr(config, key, value)
        session.add(config)
        session.commit()
        logger.info("更新数据源 | id=%s", source_id)
    return {"id": source_id, "message": "数据源已更新"}


@router.delete("/{source_id}")
async def delete_source(source_id: str):
    with get_session() as session:
        config = session.get(SourceConfig, source_id)
        if not config:
            raise HTTPException(status_code=404, detail="数据源不存在")
        session.delete(config)
        session.commit()
        logger.info("删除数据源 | id=%s", source_id)
    return {"id": source_id, "message": "数据源已删除"}


@router.post("/{source_id}/run")
async def run_source(source_id: str):
    from omka.app.connectors.github.connector import GitHubConnector

    with get_session() as session:
        config = session.get(SourceConfig, source_id)
        if not config:
            raise HTTPException(status_code=404, detail="数据源不存在")

    connector = GitHubConnector()
    raw_items = await connector.fetch(config.model_dump())

    from omka.app.storage.db import RawItem
    with get_session() as session:
        for item in raw_items:
            raw = RawItem(
                id=f"{item['item_type']}:{config.id}:{hash(str(item['raw_data']))}",
                source_id=config.id,
                source_type="github",
                item_type=item["item_type"],
                fetch_url=item["fetch_url"],
                http_status=item["http_status"],
                raw_data=item["raw_data"],
                fetched_at=item["fetched_at"],
            )
            session.merge(raw)

        config.last_fetched_at = __import__("datetime").datetime.utcnow()
        session.add(config)
        session.commit()

    logger.info("手动运行数据源 | id=%s | 抓取=%d 条", source_id, len(raw_items))
    return {"source_id": source_id, "fetched_count": len(raw_items)}
