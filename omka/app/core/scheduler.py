"""OMKA 调度器配置

基于 APScheduler 实现每日定时抓取任务。
支持手动触发和自动调度。
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from omka.app.core.config import settings
from omka.app.core.logging import get_logger

logger = get_logger("system")

# 全局调度器实例
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """获取或创建全局调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
        logger.info("调度器实例创建完成")
    return _scheduler


def start_scheduler() -> None:
    """启动调度器"""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("调度器已启动 | 时区=%s", settings.scheduler_timezone)


def shutdown_scheduler() -> None:
    """关闭调度器"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("调度器已关闭")
        _scheduler = None


def schedule_daily_job(job_func, job_id: str = "github_daily_job") -> None:
    """注册每日定时任务

    Args:
        job_func: 任务执行函数
        job_id: 任务唯一标识
    """
    scheduler = get_scheduler()

    # Cron 表达式解析: 分 时 日 月 周
    parts = settings.scheduler_daily_cron.split()
    trigger = CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
        timezone=settings.scheduler_timezone,
    )

    scheduler.add_job(
        job_func,
        trigger=trigger,
        id=job_id,
        name="GitHub 每日抓取任务",
        replace_existing=True,
        misfire_grace_time=3600,  # 允许1小时的容错时间
    )

    logger.info(
        "每日任务已注册 | ID=%s | Cron=%s | 时区=%s",
        job_id,
        settings.scheduler_daily_cron,
        settings.scheduler_timezone,
    )
