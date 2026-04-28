from fastapi import APIRouter

from omka.app.notifications.service import notification_service
from omka.app.services.daily_job import run_daily_job
from omka.app.storage.db import NotificationRun, get_session

router = APIRouter()


@router.post("/feishu/test")
async def test_feishu_notification():
    """测试飞书 Webhook 推送"""
    test_digest = {
        "phases": {
            "fetch": {"fetched_count": 5},
            "dedup": {"candidate_count": 3},
        }
    }
    result = await notification_service.send_digest(test_digest)
    feishu_result = result.get("feishu_webhook")
    if feishu_result:
        return {
            "success": feishu_result.success,
            "message": feishu_result.message,
        }
    return {"success": False, "message": "飞书推送未启用"}


@router.post("/feishu/send-latest-digest")
async def send_latest_digest():
    """手动发送最新 Digest 到飞书"""
    digest_result = await run_daily_job()
    notification_results = await notification_service.send_digest(digest_result)

    return {
        "digest": digest_result,
        "notifications": {
            k: {"success": v.success, "message": v.message}
            for k, v in notification_results.items()
        },
    }


@router.get("/runs")
async def list_notification_runs(limit: int = 20):
    """获取通知推送记录"""
    from sqlmodel import select

    with get_session() as session:
        runs = session.exec(
            select(NotificationRun).order_by(NotificationRun.created_at.desc()).limit(limit)
        ).all()
        return [
            {
                "id": r.id,
                "channel_type": r.channel_type,
                "status": r.status,
                "sent_at": r.sent_at,
                "error_message": r.error_message,
                "created_at": r.created_at,
            }
            for r in runs
        ]
