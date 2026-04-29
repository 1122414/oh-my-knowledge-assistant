from __future__ import annotations

import logging
from typing import Any

from omka.app.integrations.feishu.command_router import FeishuCommandRouter
from omka.app.integrations.feishu.config import FeishuConfig
from omka.app.integrations.feishu.conversation_gateway import (
    DisabledFeishuConversationGateway,
    FeishuConversationGateway,
)
from omka.app.integrations.feishu.errors import FeishuEventError
from omka.app.integrations.feishu.models import FeishuMessageEvent

logger = logging.getLogger("OMKA.feishu.event_handler")

MAX_DEDUP_SIZE = 10_000


class FeishuEventHandler:
    def __init__(self, config: FeishuConfig) -> None:
        self._config = config
        self._processed_event_ids: set[str] = set()
        self._command_router = FeishuCommandRouter(config)
        self._conversation_gateway: FeishuConversationGateway = DisabledFeishuConversationGateway()

    async def handle_event(
        self, payload: dict[str, Any], headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        logger.debug("收到飞书事件 | headers=%s", headers)

        if payload.get("type") == "url_verification":
            return self._handle_url_verification(payload)

        header = payload.get("header", {})
        event_type: str = header.get("event_type", "")
        event_id: str = header.get("event_id", "")
        token: str = header.get("token", "")

        logger.info(
            "处理飞书事件 | event_type=%s | event_id=%s", event_type, event_id
        )

        self._validate_token(token)
        event = self._decrypt_if_needed(payload.get("event", {}))
        self._check_duplicate(event_id)

        if event_type == "im.message.receive_v1":
            return await self._handle_message_event(event_id, event_type, event)

        logger.warning("未支持的事件类型 | event_type=%s", event_type)
        return {"code": 0, "msg": "ok"}

    def _handle_url_verification(self, payload: dict[str, Any]) -> dict[str, str]:
        challenge = payload.get("challenge", "")
        token = payload.get("token", "")
        self._validate_token(token)
        logger.info("URL 验证通过 | challenge=%s", challenge[:16] if challenge else "")
        return {"challenge": challenge}

    async def _handle_message_event(
        self, event_id: str, event_type: str, event: dict[str, Any]
    ) -> dict[str, Any]:
        message = event.get("message", {})
        sender = event.get("sender", {})

        parsed = FeishuMessageEvent(
            event_id=event_id,
            event_type=event_type,
            chat_id=message.get("chat_id", ""),
            sender_id=sender.get("sender_id", {}).get("open_id", ""),
            message_id=message.get("message_id", ""),
            message_type=message.get("message_type", ""),
            content=message.get("content", ""),
            mentions=message.get("mentions"),
        )

        logger.info(
            "解析消息事件 | message_id=%s | chat_id=%s | sender=%s | type=%s",
            parsed.message_id,
            parsed.chat_id,
            parsed.sender_id,
            parsed.message_type,
        )

        if parsed.message_type != "text":
            logger.debug("非文本消息，忽略 | message_type=%s", parsed.message_type)
            return {"code": 0, "msg": "ok"}

        command_result = await self._command_router.route(parsed)

        if command_result.success:
            from omka.app.integrations.feishu.client import FeishuAppBotClient
            from omka.app.integrations.feishu.auth import FeishuAuthService

            try:
                auth_service = FeishuAuthService(self._config)
                client = FeishuAppBotClient(self._config, auth_service)
                await client.reply_text(parsed.message_id, command_result.message)
            except Exception as e:
                logger.error("回复命令结果失败 | error=%s", e)
        else:
            if self._config.agent_conversation_enabled:
                reply = await self._conversation_gateway.handle_user_message(
                    user_id=parsed.sender_id,
                    chat_id=parsed.chat_id,
                    message=parsed.content,
                )
                try:
                    from omka.app.integrations.feishu.client import FeishuAppBotClient
                    from omka.app.integrations.feishu.auth import FeishuAuthService

                    auth_service = FeishuAuthService(self._config)
                    client = FeishuAppBotClient(self._config, auth_service)
                    await client.reply_text(parsed.message_id, reply)
                except Exception as e:
                    logger.error("回复 Agent 对话失败 | error=%s", e)

        return {"code": 0, "msg": "ok"}

    def _validate_token(self, token: str) -> None:
        expected = self._config.verification_token
        if not expected:
            return
        if token != expected:
            logger.error(
                "Verification Token 不匹配 | expected=%s... | got=%s...",
                expected[:8],
                token[:8] if token else "",
            )
            raise FeishuEventError("Verification token mismatch", error_code="TOKEN_INVALID")

    def _check_duplicate(self, event_id: str) -> None:
        if not event_id:
            return
        if event_id in self._processed_event_ids:
            logger.info("重复事件，跳过 | event_id=%s", event_id)
            raise FeishuEventError(
                f"Duplicate event: {event_id}", error_code="DUPLICATE_EVENT"
            )
        if len(self._processed_event_ids) >= MAX_DEDUP_SIZE:
            evict_count = MAX_DEDUP_SIZE // 2
            evicted = set(list(self._processed_event_ids)[:evict_count])
            self._processed_event_ids -= evicted
            logger.debug("去重集合已清理 | evicted=%d", evict_count)
        self._processed_event_ids.add(event_id)

    def _decrypt_if_needed(self, event: dict[str, Any]) -> dict[str, Any]:
        if not self._config.encrypt_key:
            return event

        encrypted = event.get("encrypt")
        if not encrypted:
            return event

        logger.warning("收到加密事件但解密尚未实现，请配置 encrypt_key 或关闭加密")
        raise FeishuEventError(
            "Encrypted event received but decryption is not implemented",
            error_code="DECRYPT_NOT_IMPLEMENTED",
        )
