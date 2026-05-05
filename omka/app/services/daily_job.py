import asyncio
from datetime import datetime
from typing import Any, Callable

from omka.app.core.logging import TraceContext, get_logger, trace

logger = get_logger("daily_job")
from omka.app.pipeline.cleaner import clean_and_normalize
from omka.app.pipeline.deduper import dedup_and_create_candidates
from omka.app.pipeline.digest_builder import generate_digest
from omka.app.pipeline.fetcher import fetch_all_sources
from omka.app.pipeline.ranker import rank_candidates
from omka.app.storage.db import FetchRun, get_session
from sqlmodel import select


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


@trace("daily_job")
async def run_daily_job() -> dict[str, Any]:
    logger.info("=" * 50)
    logger.info("开始执行每日任务 | %s", datetime.now().isoformat())
    logger.info("=" * 50)
    
    with TraceContext("daily_job", {"job_type": "github_daily"}) as ctx:
        return await _run_daily_job_inner()

async def _run_daily_job_inner() -> dict[str, Any]:
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
        from omka.app.core.settings_service import get_setting
        feishu_enabled = get_setting("feishu_enabled", False)
        push_digest_enabled = get_setting("feishu_push_digest_enabled", True)

        if feishu_enabled and push_digest_enabled:
            from omka.app.integrations.feishu.service import feishu_notification_service
            from omka.app.storage.db import FeishuDirectConversation

            with get_session() as session:
                conversations = session.exec(
                    select(FeishuDirectConversation)
                    .where(FeishuDirectConversation.enabled == True)
                ).all()

            if conversations:
                for conv in conversations:
                    feishu_result = await feishu_notification_service.send_digest(
                        result, receive_id=conv.open_id, receive_id_type="open_id"
                    )
                    if feishu_result.success:
                        logger.info("[feishu] 通知发送成功 | open_id=%s", conv.open_id[:8])
                    else:
                        logger.warning("[feishu] 通知发送失败 | open_id=%s | %s", conv.open_id[:8], feishu_result.message)
            else:
                feishu_result = await feishu_notification_service.send_digest(result)
                if feishu_result.success:
                    logger.info("[feishu] 通知发送成功（默认目标）")
                else:
                    logger.warning("[feishu] 通知发送失败 | %s", feishu_result.message)
        else:
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
