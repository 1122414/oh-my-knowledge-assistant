from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from omka.app.core.logging import logger
from omka.app.core.settings_service import get_setting
from omka.app.integrations.feishu.config import FeishuConfig
from omka.app.integrations.feishu.event_handler import FeishuEventHandler
from omka.app.integrations.feishu.service import feishu_notification_service
from omka.app.storage.db import FeishuDirectConversation, FeishuEventLog, FeishuMessageRun, get_session
from sqlmodel import select

router = APIRouter()


class FeishuTestResponse(BaseModel):
    success: bool
    message: str


def _build_full_config() -> FeishuConfig:
    return FeishuConfig(
        enabled=get_setting("feishu_enabled", False),
        app_id=get_setting("feishu_app_id", ""),
        app_secret=get_setting("feishu_app_secret", ""),
        verification_token=get_setting("feishu_verification_token", ""),
        encrypt_key=get_setting("feishu_encrypt_key", ""),
        api_base_url=get_setting("feishu_api_base_url", "https://open.feishu.cn/open-apis"),
        request_timeout_seconds=get_setting("feishu_request_timeout_seconds", 10),
        max_retries=get_setting("feishu_max_retries", 3),
        default_receive_id_type=get_setting("feishu_default_receive_id_type", "chat_id"),
        default_chat_id=get_setting("feishu_default_chat_id", ""),
        command_prefix=get_setting("feishu_command_prefix", "/omka"),
        require_mention=get_setting("feishu_require_mention", True),
        group_allowlist=get_setting("feishu_group_allowlist", "").split(",") if get_setting("feishu_group_allowlist", "") else [],
        user_allowlist=get_setting("feishu_user_allowlist", "").split(",") if get_setting("feishu_user_allowlist", "") else [],
        push_digest_enabled=get_setting("feishu_push_digest_enabled", True),
        push_digest_top_n=get_setting("feishu_push_digest_top_n", 6),
        event_callback_path=get_setting("feishu_event_callback_path", "/api/integrations/feishu/events"),
        public_callback_url=get_setting("feishu_public_callback_url", ""),
        agent_conversation_enabled=get_setting("feishu_agent_conversation_enabled", False),
        agent_session_ttl_minutes=get_setting("feishu_agent_session_ttl_minutes", 60),
        agent_max_message_chars=get_setting("feishu_agent_max_message_chars", 4000),
        doc_folder_token=get_setting("feishu_doc_folder_token", ""),
        base_folder_token=get_setting("feishu_base_folder_token", ""),
        sheet_folder_token=get_setting("feishu_sheet_folder_token", ""),
        default_calendar_id=get_setting("feishu_default_calendar_id", ""),
    )


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

    config = _build_full_config()
    handler = FeishuEventHandler(config)

    try:
        result = await handler.handle_event(payload, headers)

        event_id = payload.get("header", {}).get("event_id", "")
        event_type = payload.get("header", {}).get("event_type", "")
        chat_id = None
        sender_id = None
        message_id = None

        event_data = payload.get("event", {})
        if event_type == "im.message.receive_v1":
            message = event_data.get("message", {})
            sender = event_data.get("sender", {})
            chat_id = message.get("chat_id")
            sender_id = sender.get("sender_id", {}).get("open_id")
            message_id = message.get("message_id")

        with get_session() as session:
            existing = session.exec(
                select(FeishuEventLog).where(FeishuEventLog.event_id == event_id)
            ).first()
            if existing:
                existing.chat_id = chat_id or existing.chat_id
                existing.sender_id = sender_id or existing.sender_id
                existing.message_id = message_id or existing.message_id
                existing.handled_status = "routed" if result.get("code") == 0 else "failed"
                existing.error_message = result.get("error")
                session.add(existing)
            else:
                log = FeishuEventLog(
                    event_id=event_id,
                    event_type=event_type,
                    chat_id=chat_id,
                    sender_id=sender_id,
                    message_id=message_id,
                    raw_event_json=payload,
                    handled_status="routed" if result.get("code") == 0 else "failed",
                    error_message=result.get("error"),
                )
                session.add(log)
            session.commit()

        return result
    except Exception as e:
        logger.error("处理飞书事件失败 | error=%s", e)
        return {"code": -1, "msg": str(e)}


@router.get("/status")
async def get_feishu_status():
    config = _build_full_config()

    with get_session() as session:
        conversation_count = session.exec(
            select(FeishuDirectConversation).where(FeishuDirectConversation.enabled == True)
        ).all()
        latest_event = session.exec(
            select(FeishuEventLog).order_by(FeishuEventLog.created_at.desc())
        ).first()
        latest_message = session.exec(
            select(FeishuMessageRun).order_by(FeishuMessageRun.created_at.desc())
        ).first()

    return {
        "enabled": config.enabled,
        "configured": config.is_configured(),
        "agent_enabled": config.agent_conversation_enabled,
        "bound_users": len(conversation_count),
        "latest_event": {
            "event_type": latest_event.event_type if latest_event else None,
            "created_at": latest_event.created_at if latest_event else None,
        } if latest_event else None,
        "latest_message": {
            "status": latest_message.status if latest_message else None,
            "message_type": latest_message.message_type if latest_message else None,
            "created_at": latest_message.created_at if latest_message else None,
        } if latest_message else None,
    }


@router.get("/conversations")
async def list_conversations():
    with get_session() as session:
        conversations = session.exec(
            select(FeishuDirectConversation).order_by(FeishuDirectConversation.created_at.desc())
        ).all()
        return [
            {
                "id": c.id,
                "open_id": c.open_id[:8] + "****" if len(c.open_id) > 8 else c.open_id,
                "chat_id": c.chat_id[:8] + "****" if len(c.chat_id) > 8 else c.chat_id,
                "enabled": c.enabled,
                "is_default": c.is_default,
                "last_message_at": c.last_message_at,
                "created_at": c.created_at,
            }
            for c in conversations
        ]


@router.post("/conversations/{conversation_id}/disable")
async def disable_conversation(conversation_id: int):
    with get_session() as session:
        conversation = session.get(FeishuDirectConversation, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")

        conversation.enabled = False
        session.add(conversation)
        session.commit()

    return {"message": "已解绑", "id": conversation_id}


class FeishuTestApiServiceResponse(BaseModel):
    ok: bool
    code: int = -1
    msg: str = ""
    error: str = ""


@router.post("/test-api-service", response_model=FeishuTestApiServiceResponse)
async def test_api_service():
    """测试 FeishuApiService 连通性（使用 lark.Client 获取用户列表）"""
    from omka.app.integrations.feishu.api_service import FeishuApiService

    config = _build_full_config()
    if not config.is_configured():
        return FeishuTestApiServiceResponse(ok=False, error="飞书凭证未配置")

    try:
        svc = FeishuApiService(config)
        from lark_oapi.api.contact.v3 import ListUserRequest

        req = ListUserRequest.builder().page_size(1).build()
        resp = svc.client.contact.v3.user.list(req)
        return FeishuTestApiServiceResponse(
            ok=resp.code == 0,
            code=resp.code,
            msg=resp.msg,
        )
    except Exception as e:
        logger.error("FeishuApiService 测试失败 | error=%s", e)
        return FeishuTestApiServiceResponse(ok=False, error=str(e))


@router.post("/test-credentials", response_model=FeishuTestResponse)
async def test_credentials():
    from omka.app.integrations.feishu.auth import FeishuAuthService

    config = _build_full_config()
    if not config.is_configured():
        return FeishuTestResponse(success=False, message="飞书凭证未配置")

    try:
        auth_service = FeishuAuthService(config)
        token = await auth_service.get_tenant_access_token()
        return FeishuTestResponse(success=True, message="凭证验证成功")
    except Exception as e:
        return FeishuTestResponse(success=False, message=f"凭证验证失败: {str(e)}")
