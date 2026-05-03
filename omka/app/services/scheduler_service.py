"""OMKA 定时任务调度服务

统一管理 APScheduler 的每日任务生命周期。
API、飞书命令、Settings UI 均通过此服务操作调度。
"""

import re
from datetime import datetime
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError
from croniter import croniter

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.core.scheduler import get_scheduler


NATURAL_TIME_PATTERNS: list[tuple[str, str]] = [
    (r"每天\s*(\d{1,2})\s*点\s*$", r"0 \1 * * *"),
    (r"每天\s*(\d{1,2}):(\d{2})\s*$", r"\2 \1 * * *"),
    (r"每日\s*(\d{1,2}):(\d{2})\s*$", r"\2 \1 * * *"),
    (r"每周一\s*(\d{1,2}):(\d{2})\s*$", r"\2 \1 * * mon"),
    (r"每周二\s*(\d{1,2}):(\d{2})\s*$", r"\2 \1 * * tue"),
    (r"每周三\s*(\d{1,2}):(\d{2})\s*$", r"\2 \1 * * wed"),
    (r"每周四\s*(\d{1,2}):(\d{2})\s*$", r"\2 \1 * * thu"),
    (r"每周五\s*(\d{1,2}):(\d{2})\s*$", r"\2 \1 * * fri"),
    (r"每周六\s*(\d{1,2}):(\d{2})\s*$", r"\2 \1 * * sat"),
    (r"每周(日|天)\s*(\d{1,2}):(\d{2})\s*$", r"\3 \2 * * sun"),
    (r"每周(\d{1,2}):(\d{2})\s*$", r"\2 \1 * * mon"),
]

CRON_PATTERN = re.compile(
    r"^[\d*,/\-]+\s+[\d*,/\-]+\s+[\d*,/\-]+\s+[\d*,/\-]+\s+[\d*,/\-]+$"
)

JOB_ID = "github_daily_job"


def normalize_schedule(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None

    if CRON_PATTERN.match(text):
        return text

    for pattern, template in NATURAL_TIME_PATTERNS:
        m = re.match(pattern, text)
        if m:
            return m.expand(template)

    return None


def validate_cron(cron_text: str) -> bool:
    try:
        croniter(cron_text)
        return True
    except (ValueError, KeyError):
        return False


def get_schedule() -> dict[str, Any]:
    scheduler = get_scheduler()
    job = scheduler.get_job(JOB_ID)
    running = scheduler.running if hasattr(scheduler, "running") else False

    cron = settings.scheduler_daily_cron
    timezone = settings.scheduler_timezone

    next_run_time = None
    if job and job.next_run_time:
        next_run_time = job.next_run_time.isoformat()

    return {
        "cron": cron,
        "timezone": timezone,
        "next_run_time": next_run_time if next_run_time else (
            _compute_next_run(cron, timezone)
        ),
        "running": running,
    }


def update_schedule(schedule_text: str) -> tuple[bool, str]:
    cron = normalize_schedule(schedule_text)
    if cron is None:
        return False, (
            "定时任务格式无法识别\n\n"
            "可用示例:\n"
            "- 每天 9:30\n"
            "- 每周一 18:00\n"
            "- 0 9 * * *"
        )

    if not validate_cron(cron):
        return False, f"Cron 表达式校验失败: {cron}"

    try:
        from omka.app.core.settings_service import set_setting

        set_setting("scheduler_daily_cron", cron)

        scheduler = get_scheduler()
        parts = cron.split()
        trigger = CronTrigger(
            minute=parts[0], hour=parts[1], day=parts[2],
            month=parts[3], day_of_week=parts[4],
            timezone=settings.scheduler_timezone,
        )

        try:
            scheduler.reschedule_job(
                job_id=JOB_ID,
                trigger=trigger,
                misfire_grace_time=3600,
            )
        except JobLookupError:
            from omka.app.core.scheduler import schedule_daily_job
            from omka.app.services.daily_job import run_daily_job
            schedule_daily_job(run_daily_job, job_id=JOB_ID)

        settings.scheduler_daily_cron = cron

        info = get_schedule()
        logger.info("定时任务已更新 | cron=%s | next_run=%s", cron, info["next_run_time"])
        return True, (
            f"已更新定时任务\n\n"
            f"Cron: {cron}\n"
            f"时区: {settings.scheduler_timezone}\n"
            f"下次运行: {info['next_run_time']}"
        )
    except Exception as e:
        logger.error("更新定时任务失败 | error=%s", e)
        return False, f"更新失败: {str(e)}"


def _compute_next_run(cron: str, timezone: str) -> str | None:
    try:
        it = croniter(cron, datetime.utcnow())
        return it.get_next(datetime).isoformat()
    except (ValueError, KeyError):
        return None
