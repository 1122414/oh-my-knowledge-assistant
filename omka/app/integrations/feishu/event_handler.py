from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from omka.app.integrations.feishu.command_router import FeishuCommandRouter
from omka.app.integrations.feishu.config import FeishuConfig
from omka.app.integrations.feishu.conversation_gateway import (
    DisabledFeishuConversationGateway,
    FeishuConversationGateway,
    SimpleKnowledgeAgentGateway,
)
from omka.app.integrations.feishu.errors import FeishuEventError
from omka.app.integrations.feishu.models import FeishuCommandType, FeishuMessageEvent
from omka.app.storage.db import get_session
from sqlmodel import select

logger = logging.getLogger("OMKA.feishu.event_handler")

MAX_DEDUP_SIZE = 10_000


class FeishuEventHandler:
    def __init__(self, config: FeishuConfig) -> None:
        self._config = config
        self._processed_event_ids: set[str] = set()
        self._command_router = FeishuCommandRouter(config)
        if config.agent_conversation_enabled:
            self._conversation_gateway: FeishuConversationGateway = SimpleKnowledgeAgentGateway()
        else:
            self._conversation_gateway = DisabledFeishuConversationGateway()

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
        if self._check_duplicate(event_id):
            return {"code": 0, "msg": "ok"}

        try:
            if event_type == "im.message.receive_v1":
                result = await self._handle_message_event(event_id, event_type, event)
            else:
                logger.warning("未支持的事件类型 | event_type=%s", event_type)
                result = {"code": 0, "msg": "ok"}
        finally:
            self._mark_processed(event_id)

        return result

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
        chat_type = message.get("chat_type", "")

        if chat_type != "p2p":
            logger.debug("忽略非单聊消息 | chat_type=%s", chat_type)
            return {"code": 0, "msg": "ok"}

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

        if self._config.auto_bind_direct_chat:
            await self._auto_bind(parsed.sender_id, parsed.chat_id)

        logger.info("开始路由命令 | content=%s", parsed.content[:100])
        command_result = await self._command_router.route(parsed)
        logger.info("命令路由完成 | success=%s | message=%s", command_result.success, command_result.message[:100] if command_result.message else "")

        if command_result.success:
            from omka.app.integrations.feishu.client import FeishuAppBotClient
            from omka.app.integrations.feishu.auth import FeishuAuthService

            try:
                auth_service = FeishuAuthService(self._config)
                client = FeishuAppBotClient(self._config, auth_service)
                result = await client.reply_text(parsed.message_id, command_result.message)
                if not result.success:
                    logger.error("回复命令结果失败 | error=%s | code=%s", result.message, result.error_code)
            except Exception as e:
                logger.error("回复命令结果异常 | error=%s", e)
        else:
            plain_text = parsed.content
            if command_result.command == FeishuCommandType.CHAT and command_result.args:
                plain_text = " ".join(command_result.args)
                logger.info("处理 /omka chat 命令 | message=%s", plain_text[:100])
            else:
                try:
                    import json
                    content_data = json.loads(parsed.content)
                    plain_text = content_data.get("text", parsed.content)
                except (json.JSONDecodeError, TypeError):
                    pass

            if self._config.agent_conversation_enabled:
                try:
                    reply = await asyncio.wait_for(
                        self._conversation_gateway.handle_user_message(
                            user_id=parsed.sender_id,
                            chat_id=parsed.chat_id,
                            message=plain_text,
                        ),
                        timeout=30
                    )
                except asyncio.TimeoutError:
                    logger.error("对话网关处理超时")
                    reply = "抱歉，处理超时了。请稍后再试。"
                except Exception as e:
                    logger.error("对话网关处理失败 | error=%s", e)
                    reply = "处理消息时出现错误，请稍后再试。"

                try:
                    from omka.app.integrations.feishu.client import FeishuAppBotClient
                    from omka.app.integrations.feishu.auth import FeishuAuthService

                    auth_service = FeishuAuthService(self._config)
                    client = FeishuAppBotClient(self._config, auth_service)
                    result = await client.reply_text(parsed.message_id, reply)
                    if not result.success:
                        logger.error("回复 Agent 对话失败 | error=%s | code=%s", result.message, result.error_code)
                except Exception as e:
                    logger.error("回复 Agent 对话异常 | error=%s", e)
            else:
                logger.info("Agent 对话未启用，发送提示 | sender=%s", parsed.sender_id)
                try:
                    from omka.app.integrations.feishu.client import FeishuAppBotClient
                    from omka.app.integrations.feishu.auth import FeishuAuthService

                    auth_service = FeishuAuthService(self._config)
                    client = FeishuAppBotClient(self._config, auth_service)
                    result = await client.reply_text(parsed.message_id, "请输入 /omka help 查看可用命令。Agent 对话功能暂未启用。")
                    if not result.success:
                        logger.error("回复提示消息失败 | error=%s | code=%s", result.message, result.error_code)
                except Exception as e:
                    logger.error("回复提示消息异常 | error=%s", e)

        return {"code": 0, "msg": "ok"}

    async def _auto_bind(self, open_id: str, chat_id: str) -> None:
        """自动绑定单聊会话"""
        try:
            from omka.app.storage.db import FeishuDirectConversation

            with get_session() as session:
                existing = session.exec(
                    select(FeishuDirectConversation)
                    .where(FeishuDirectConversation.open_id == open_id)
                ).first()

                if existing:
                    if existing.chat_id != chat_id:
                        existing.chat_id = chat_id
                        existing.updated_at = datetime.utcnow()
                        session.add(existing)
                        session.commit()
                        logger.info("更新单聊绑定 | open_id=%s | chat_id=%s", open_id, chat_id)
                else:
                    conv = FeishuDirectConversation(
                        open_id=open_id,
                        chat_id=chat_id,
                        enabled=True,
                        is_default=False,
                        last_message_at=datetime.utcnow(),
                    )
                    session.add(conv)
                    session.commit()
                    logger.info("新增单聊绑定 | open_id=%s | chat_id=%s", open_id, chat_id)
        except Exception as e:
            logger.error("自动绑定失败 | error=%s", e)

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

    def _check_duplicate(self, event_id: str) -> bool:
        """检查事件是否已处理过。返回 True 表示是重复事件。"""
        if not event_id:
            return False
        if event_id in self._processed_event_ids:
            logger.info("重复事件，跳过 | event_id=%s", event_id)
            return True
        if len(self._processed_event_ids) >= MAX_DEDUP_SIZE:
            evict_count = MAX_DEDUP_SIZE // 2
            evicted = set(list(self._processed_event_ids)[:evict_count])
            self._processed_event_ids -= evicted
            logger.debug("去重集合已清理 | evicted=%d", evict_count)
        return False

    def _mark_processed(self, event_id: str) -> None:
        """将事件标记为已处理。仅在 handle_event 成功完成后调用。"""
        if not event_id:
            return
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
