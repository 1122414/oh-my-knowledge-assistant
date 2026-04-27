from datetime import datetime
from typing import Any

from omka.app.core.logging import logger
from omka.app.pipeline.cleaner import clean_and_normalize
from omka.app.pipeline.deduper import dedup_and_create_candidates
from omka.app.pipeline.digest_builder import generate_digest
from omka.app.pipeline.fetcher import fetch_all_sources
from omka.app.pipeline.ranker import rank_candidates
from omka.app.storage.db import FetchRun, get_session


async def run_daily_job() -> dict[str, Any]:
    logger.info("=" * 50)
    logger.info("开始执行每日任务 | %s", datetime.now().isoformat())
    logger.info("=" * 50)

    result = {"phases": {}}
    run_id: int | None = None

    try:
        fetch_result = await fetch_all_sources()
        result["phases"]["fetch"] = fetch_result
        run_id = fetch_result.get("run_id")
        logger.info("[Phase 1] 抓取完成 | fetched=%d", fetch_result.get("fetched_count", 0))
    except Exception as e:
        logger.error("[Phase 1] 抓取失败 | error=%s", e)
        result["phases"]["fetch"] = {"status": "failed", "error": str(e)}
        return result

    try:
        clean_result = clean_and_normalize()
        result["phases"]["clean"] = clean_result
        logger.info("[Phase 2] 规范化完成 | normalized=%d", clean_result.get("normalized_count", 0))
    except Exception as e:
        logger.error("[Phase 2] 规范化失败 | error=%s", e)
        result["phases"]["clean"] = {"status": "failed", "error": str(e)}

    try:
        dedup_result = dedup_and_create_candidates()
        result["phases"]["dedup"] = dedup_result
        logger.info("[Phase 3] 去重完成 | candidates=%d", dedup_result.get("candidate_count", 0))
    except Exception as e:
        logger.error("[Phase 3] 去重失败 | error=%s", e)
        result["phases"]["dedup"] = {"status": "failed", "error": str(e)}

    try:
        rank_result = rank_candidates()
        result["phases"]["rank"] = rank_result
        logger.info("[Phase 4] 排序完成 | ranked=%d", rank_result.get("ranked_count", 0))
    except Exception as e:
        logger.error("[Phase 4] 排序失败 | error=%s", e)
        result["phases"]["rank"] = {"status": "failed", "error": str(e)}

    try:
        digest_result = await generate_digest()
        result["phases"]["digest"] = digest_result
        logger.info("[Phase 5] 简报完成 | path=%s", digest_result.get("digest_path"))
    except Exception as e:
        logger.error("[Phase 5] 简报生成失败 | error=%s", e)
        result["phases"]["digest"] = {"status": "failed", "error": str(e)}

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

    logger.info("=" * 50)
    logger.info("每日任务执行完毕")
    logger.info("=" * 50)

    return result
