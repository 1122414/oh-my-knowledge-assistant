from datetime import datetime
from typing import Any

from sqlmodel import select

from omka.app.connectors.registry import ConnectorRegistry
from omka.app.core.logging import get_logger, trace

logger = get_logger("pipeline")
from omka.app.storage.db import FetchRun, SourceConfig, get_session
from omka.app.storage.repositories import save_raw_items


@trace("pipeline")
async def fetch_all_sources() -> dict[str, Any]:
    with get_session() as session:
        configs = session.exec(
            select(SourceConfig).where(SourceConfig.enabled == True)
        ).all()

    if not configs:
        logger.warning("没有启用的数据源")
        return {"status": "no_sources", "fetched_count": 0}

    run = FetchRun(job_type="github_daily", status="running")
    with get_session() as session:
        session.add(run)
        session.commit()
        run_id = run.id

    total_fetched = 0
    errors = []

    for config in configs:
        try:
            connector = ConnectorRegistry.get(config.source_type)
            raw_items = await connector.fetch(config.model_dump())
            save_raw_items(raw_items, config)

            with get_session() as session:
                config.last_fetched_at = datetime.utcnow()
                session.merge(config)
                session.commit()

            total_fetched += len(raw_items)
            logger.info("抓取完成 | source=%s | count=%d", config.id, len(raw_items))
        except Exception as e:
            errors.append(f"{config.id}: {str(e)}")
            logger.error("抓取失败 | source=%s | error=%s", config.id, e)

    status = "success" if not errors else ("partial_success" if total_fetched > 0 else "failed")
    with get_session() as session:
        run = session.get(FetchRun, run_id)
        run.status = status
        run.fetched_count = total_fetched
        run.error_count = len(errors)
        run.error_message = "; ".join(errors) if errors else None
        session.add(run)
        session.commit()

    logger.info("批量抓取完成 | total=%d | errors=%d", total_fetched, len(errors))
    return {
        "status": status,
        "fetched_count": total_fetched,
        "error_count": len(errors),
        "errors": errors,
        "run_id": run_id,
    }
