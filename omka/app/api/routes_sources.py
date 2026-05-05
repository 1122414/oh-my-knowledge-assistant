from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from omka.app.connectors.registry import ConnectorRegistry
from omka.app.core.logging import logger
from omka.app.pipeline.cleaner import clean_and_normalize
from omka.app.pipeline.deduper import dedup_and_create_candidates
from omka.app.pipeline.ranker import rank_candidates
from omka.app.storage.db import SourceConfig, get_session
from omka.app.storage.repositories import save_raw_items


class SourceCreateRequest(BaseModel):
    id: str = Field(..., description="数据源唯一标识")
    source_type: str = Field(default="github", description="数据源类型")
    name: str = Field(..., description="显示名称")
    enabled: bool = Field(default=True)
    mode: str = Field(..., description="repo 或 search")
    repo_full_name: str | None = None
    query: str | None = None
    limit: int = Field(default=5)
    weight: float = Field(default=1.0)


class SourceUpdateRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    mode: str | None = None
    repo_full_name: str | None = None
    query: str | None = None
    limit: int | None = None
    weight: float | None = None


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
async def create_source(data: SourceCreateRequest):
    config = SourceConfig(**data.model_dump())
    with get_session() as session:
        session.merge(config)
        session.commit()
        logger.info("创建数据源 | id=%s | mode=%s", config.id, config.mode)
    return {"id": config.id, "message": "数据源已创建"}


@router.put("/{source_id}")
async def update_source(source_id: str, data: SourceUpdateRequest):
    with get_session() as session:
        config = session.get(SourceConfig, source_id)
        if not config:
            raise HTTPException(status_code=404, detail="数据源不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(config, key, value)
        config.updated_at = datetime.utcnow()
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
    with get_session() as session:
        config = session.get(SourceConfig, source_id)
        if not config:
            raise HTTPException(status_code=404, detail="数据源不存在")

    connector = ConnectorRegistry.get(config.source_type)
    raw_items = await connector.fetch(config.model_dump())
    save_raw_items(raw_items, config)

    clean_and_normalize()
    dedup_and_create_candidates()
    rank_candidates()

    with get_session() as session:
        config.last_fetched_at = datetime.utcnow()
        session.merge(config)
        session.commit()

    logger.info("手动运行数据源 | id=%s | 抓取=%d 条", source_id, len(raw_items))
    return {"source_id": source_id, "fetched_count": len(raw_items)}
