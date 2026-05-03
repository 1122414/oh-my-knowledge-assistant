from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from omka.app.services.daily_job import run_daily_job
from omka.app.services.scheduler_service import get_schedule as get_scheduler_status
from omka.app.services.scheduler_service import update_schedule as update_scheduler
from omka.app.storage.db import CandidateItem, FetchRun, KnowledgeItem, NotificationRun, get_session

router = APIRouter()


class ScheduleUpdateRequest(BaseModel):
    schedule: str


@router.get("/latest")
async def get_latest_job():
    """获取最近一次任务"""
    with get_session() as session:
        run = session.exec(
            select(FetchRun).order_by(FetchRun.started_at.desc())
        ).first()
        if not run:
            return {"message": "暂无任务记录"}
        return {
            "id": run.id,
            "job_type": run.job_type,
            "status": run.status,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "fetched_count": run.fetched_count,
            "candidate_count": run.candidate_count,
            "error_message": run.error_message,
        }


@router.get("/runs")
async def list_job_runs(limit: int = 20):
    """获取任务运行记录"""
    with get_session() as session:
        runs = session.exec(
            select(FetchRun).order_by(FetchRun.started_at.desc()).limit(limit)
        ).all()
        return [
            {
                "id": r.id,
                "job_type": r.job_type,
                "status": r.status,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "fetched_count": r.fetched_count,
                "candidate_count": r.candidate_count,
                "error_message": r.error_message,
            }
            for r in runs
        ]


@router.post("/run-now")
async def run_job_now():
    """手动运行任务"""
    result = await run_daily_job()
    return result


@router.get("/schedule")
async def get_daily_schedule():
    return get_scheduler_status()


@router.put("/schedule")
async def update_daily_schedule(data: ScheduleUpdateRequest):
    ok, message = update_scheduler(data.schedule)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return get_scheduler_status()


@router.get("/dashboard")
async def get_dashboard():
    """获取 Dashboard 数据"""
    with get_session() as session:
        # 今日任务
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_run = session.exec(
            select(FetchRun)
            .where(FetchRun.started_at >= today)
            .order_by(FetchRun.started_at.desc())
        ).first()

        # 候选数量
        pending_count = session.exec(
            select(func.count(CandidateItem.id)).where(CandidateItem.status == "pending")
        ).one()

        # 知识库数量
        knowledge_count = session.exec(
            select(func.count(KnowledgeItem.id))
        ).one()

        # 最近通知状态
        latest_notification = session.exec(
            select(NotificationRun).order_by(NotificationRun.created_at.desc())
        ).first()

        return {
            "today_run": {
                "status": today_run.status if today_run else "none",
                "started_at": today_run.started_at if today_run else None,
                "fetched_count": today_run.fetched_count if today_run else 0,
                "candidate_count": today_run.candidate_count if today_run else 0,
            },
            "pending_candidates": pending_count,
            "knowledge_count": knowledge_count,
            "latest_notification": {
                "status": latest_notification.status if latest_notification else "none",
                "channel": latest_notification.channel_type if latest_notification else None,
            },
        }
