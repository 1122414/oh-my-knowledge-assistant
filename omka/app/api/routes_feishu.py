from fastapi import APIRouter, Request
from pydantic import BaseModel

from omka.app.core.logging import logger
from omka.app.core.settings_service import get_setting
from omka.app.integrations.feishu.event_handler import FeishuEventHandler
from omka.app.integrations.feishu.service import feishu_notification_service
from omka.app.storage.db import FeishuEventLog, FeishuMessageRun, get_session

router = APIRouter()


class FeishuTestResponse(BaseModel):
    success: bool
    message: str


@router.post("/send-test", response_model=FeishuTestResponse)
async def send_test_message():
    receive_id = get_setting("feishu_default_chat_id", "")
    result = await feishu_notification_service.send_test_message(receive_id)
    return FeishuTestResponse(success=result.success, message=result.message)


@router.post("/send-latest-digest", response_model=FeishuTestResponse)
async def send_latest_digest():
    receive_id = get_setting("feishu_default_chat_id", "")
    result = await feishu_notification_service.send_latest_digest(receive_id)
    return FeishuTestResponse(success=result.success, message=result.message)


@router.get("/message-runs")
async def list_message_runs(limit: int = 20):
    from sqlmodel import select

    with get_session() as session:
        runs = session.exec(
            select(FeishuMessageRun).order_by(FeishuMessageRun.created_at.desc()).limit(limit)
        ).all()
        return [
            {
                "id": r.id,
                "message_type": r.message_type,
                "receive_id_type": r.receive_id_type,
                "receive_id_masked": r.receive_id_masked,
                "status": r.status,
                "message_id": r.message_id,
                "error_code": r.error_code,
                "error_message": r.error_message,
                "request_id": r.request_id,
                "created_at": r.created_at,
            }
            for r in runs
        ]


@router.get("/event-logs")
async def list_event_logs(limit: int = 20):
    from sqlmodel import select

    with get_session() as session:
        logs = session.exec(
            select(FeishuEventLog).order_by(FeishuEventLog.created_at.desc()).limit(limit)
        ).all()
        return [
            {
                "id": l.id,
                "event_id": l.event_id,
                "event_type": l.event_type,
                "chat_id": l.chat_id,
                "sender_id": l.sender_id,
                "message_id": l.message_id,
                "handled_status": l.handled_status,
                "error_message": l.error_message,
                "created_at": l.created_at,
            }
            for l in logs
        ]


@router.post("/events")
async def handle_feishu_event(request: Request):
    payload = await request.json()
    headers = dict(request.headers)

    config_enabled = get_setting("feishu_enabled", False)
    if not config_enabled:
        return {"code": 0, "msg": "feishu not enabled"}

    from omka.app.integrations.feishu.config import FeishuConfig

    config = FeishuConfig(
        enabled=get_setting("feishu_enabled", False),
        app_id=get_setting("feishu_app_id", ""),
        app_secret=get_setting("feishu_app_secret", ""),
        verification_token=get_setting("feishu_verification_token", ""),
        encrypt_key=get_setting("feishu_encrypt_key", ""),
    )

    handler = FeishuEventHandler(config)

    try:
        result = await handler.handle_event(payload, headers)

        event_id = payload.get("header", {}).get("event_id", "")
        event_type = payload.get("header", {}).get("event_type", "")

        with get_session() as session:
            log = FeishuEventLog(
                event_id=event_id,
                event_type=event_type,
                raw_event_json=payload,
                handled_status="routed" if result.get("success") else "failed",
                error_message=result.get("error"),
            )
            session.add(log)
            session.commit()

        return result
    except Exception as e:
        logger.error("处理飞书事件失败 | error=%s", e)
        return {"code": -1, "msg": str(e)}
