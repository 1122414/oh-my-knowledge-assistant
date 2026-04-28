import asyncio
from datetime import datetime
from typing import Any, Callable

from omka.app.core.logging import logger
from omka.app.pipeline.cleaner import clean_and_normalize
from omka.app.pipeline.deduper import dedup_and_create_candidates
from omka.app.pipeline.digest_builder import generate_digest
from omka.app.pipeline.fetcher import fetch_all_sources
from omka.app.pipeline.ranker import rank_candidates
from omka.app.storage.db import FetchRun, get_session


async def _run_phase(name: str, fn: Callable, result: dict, metric_key: str) -> None:
    try:
        if asyncio.iscoroutinefunction(fn):
            phase_result = await fn()
        else:
            phase_result = fn()
        result["phases"][name] = phase_result
        logger.info("[%s] 完成 | %s=%s", name, metric_key, phase_result.get(metric_key, "?"))
    except Exception as e:
        logger.error("[%s] 失败 | error=%s", name, e)
        result["phases"][name] = {"status": "failed", "error": str(e)}


async def run_daily_job() -> dict[str, Any]:
    logger.info("=" * 50)
    logger.info("开始执行每日任务 | %s", datetime.now().isoformat())
    logger.info("=" * 50)

    result: dict[str, Any] = {"phases": {}}
    run_id: int | None = None

    try:
        fetch_result = await fetch_all_sources()
        result["phases"]["fetch"] = fetch_result
        run_id = fetch_result.get("run_id")
        logger.info("[fetch] 完成 | fetched=%d", fetch_result.get("fetched_count", 0))
    except Exception as e:
        logger.error("[fetch] 失败 | error=%s", e)
        result["phases"]["fetch"] = {"status": "failed", "error": str(e)}
        return result

    await _run_phase("clean", clean_and_normalize, result, "normalized_count")
    await _run_phase("dedup", dedup_and_create_candidates, result, "candidate_count")
    await _run_phase("rank", rank_candidates, result, "ranked_count")
    await _run_phase("digest", generate_digest, result, "item_count")

    if run_id:
        try:
            with get_session() as session:
                run = session.get(FetchRun, run_id)
                if run:
                    run.finished_at = datetime.utcnow()
                    run.normalized_count = result["phases"].get("clean", {}).get("normalized_count", 0)
                    run.candidate_count = result["phases"].get("dedup", {}).get("candidate_count", 0)
                    session.add(run)
                    session.commit()
        except Exception as e:
            logger.error("更新 FetchRun 失败 | run_id=%s | error=%s", run_id, e)

    # 发送飞书通知（失败不影响主任务）
    try:
        from omka.app.notifications.service import notification_service
        notification_results = await notification_service.send_digest(result)
        for channel, notif_result in notification_results.items():
            if notif_result.success:
                logger.info("[%s] 通知发送成功", channel)
            else:
                logger.warning("[%s] 通知发送失败 | %s", channel, notif_result.message)
    except Exception as e:
        logger.error("通知发送异常 | error=%s", e)

    logger.info("=" * 50)
    logger.info("每日任务执行完毕")
    logger.info("=" * 50)

    return result
