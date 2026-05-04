import asyncio
import json
from typing import Any

import httpx

from omka.app.core.logging import logger
from omka.app.integrations.feishu.auth import FeishuAuthService
from omka.app.integrations.feishu.config import FeishuConfig
from omka.app.integrations.feishu.errors import FeishuConfigError, FeishuSendError
from omka.app.integrations.feishu.models import FeishuSendResult


class FeishuAppBotClient:

    def __init__(self, config: FeishuConfig, auth_service: FeishuAuthService):
        if not config.is_configured():
            raise FeishuConfigError("飞书配置不完整：缺少 app_id 或 app_secret")
        self._config: FeishuConfig = config
        self._auth: FeishuAuthService = auth_service
        self._base_url: str = config.api_base_url.rstrip("/")

    async def send_text(
        self,
        receive_id: str,
        text: str,
        receive_id_type: str | None = None,
    ) -> FeishuSendResult:
        """发送文本消息

        Args:
            receive_id: 接收者 ID（群聊 ID、用户 ID 等）
            text: 消息文本内容
            receive_id_type: 接收者类型，默认使用配置中的值
        """
        content = json.dumps({"text": text})
        return await self._send_message(
            receive_id=receive_id,
            msg_type="text",
            content=content,
            receive_id_type=receive_id_type or self._config.default_receive_id_type,
        )

    async def send_post(
        self,
        receive_id: str,
        title: str,
        content_blocks: list[list[dict[str, Any]]],
        receive_id_type: str | None = None,
    ) -> FeishuSendResult:
        """发送富文本消息（post 类型）

        Args:
            receive_id: 接收者 ID
            title: 消息标题
            content_blocks: 富文本内容块，格式参考飞书 post 消息规范
            receive_id_type: 接收者类型
        """
        content = json.dumps(
            {"zh_cn": {"title": title, "content": content_blocks}},
            ensure_ascii=False,
        )
        return await self._send_message(
            receive_id=receive_id,
            msg_type="post",
            content=content,
            receive_id_type=receive_id_type or self._config.default_receive_id_type,
        )

    async def send_interactive_card(
        self,
        receive_id: str,
        card_json: dict[str, Any],
        receive_id_type: str | None = None,
    ) -> FeishuSendResult:
        """发送互动卡片消息

        Args:
            receive_id: 接收者 ID
            card_json: 飞书卡片 JSON DSL
            receive_id_type: 接收者类型
        """
        content = json.dumps(card_json, ensure_ascii=False)
        return await self._send_message(
            receive_id=receive_id,
            msg_type="interactive",
            content=content,
            receive_id_type=receive_id_type or self._config.default_receive_id_type,
        )

    async def reply_text(
        self,
        message_id: str,
        text: str,
    ) -> FeishuSendResult:
        """回复一条消息

        Args:
            message_id: 要回复的消息 ID
            text: 回复文本内容
        """
        url = f"{self._base_url}/im/v1/messages/{message_id}/reply"
        content = json.dumps({"text": text})
        payload = {"msg_type": "text", "content": content}

        return await self._request_with_retry(url, payload)

    async def _send_message(
        self,
        receive_id: str,
        msg_type: str,
        content: str,
        receive_id_type: str,
    ) -> FeishuSendResult:
        """构造并发送消息（非回复）"""
        url = f"{self._base_url}/im/v1/messages?receive_id_type={receive_id_type}"
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content,
        }
        return await self._request_with_retry(url, payload)

    async def _request_with_retry(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> FeishuSendResult:
        """发送请求，带重试逻辑"""
        max_retries = self._config.max_retries
        timeout = self._config.request_timeout_seconds
        last_error = ""

        for attempt in range(max_retries):
            try:
                token = await self._auth.get_tenant_access_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                }

                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    data = response.json()

                code = data.get("code", -1)
                msg = data.get("msg", "")
                request_id = data.get("request_id", "")

                if code == 0:
                    msg_data = data.get("data", {})
                    message_id = msg_data.get("message_id", "")
                    logger.info(
                        "飞书消息发送成功 | message_id=%s | request_id=%s",
                        message_id,
                        request_id,
                    )
                    return FeishuSendResult(
                        success=True,
                        message="发送成功",
                        message_id=message_id,
                        request_id=request_id,
                        response=data,
                    )

                if code == 99991663:
                    logger.warning(
                        "飞书 token 无效，刷新后重试 | attempt=%d/%d | request_id=%s",
                        attempt + 1,
                        max_retries,
                        request_id,
                    )
                    self._auth.invalidate()
                    last_error = f"code={code}, msg={msg}"
                    continue

                logger.warning(
                    "飞书消息发送失败 | code=%d | msg=%s | attempt=%d/%d | request_id=%s",
                    code,
                    msg,
                    attempt + 1,
                    max_retries,
                    request_id,
                )
                return FeishuSendResult(
                    success=False,
                    message=f"飞书 API 错误: {msg}",
                    error_code=str(code),
                    request_id=request_id,
                    response=data,
                )

            except httpx.TimeoutException:
                last_error = "请求超时"
                logger.warning(
                    "飞书消息发送超时 | attempt=%d/%d | timeout=%ds",
                    attempt + 1,
                    max_retries,
                    timeout,
                )

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}"
                logger.warning(
                    "飞书消息 HTTP 错误 | status=%d | attempt=%d/%d",
                    e.response.status_code,
                    attempt + 1,
                    max_retries,
                )

            except FeishuSendError:
                raise

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "飞书消息发送异常 | error=%s | attempt=%d/%d",
                    type(e).__name__,
                    attempt + 1,
                    max_retries,
                )

            if attempt < max_retries - 1:
                delay = 2**attempt
                await asyncio.sleep(delay)

        logger.error("飞书消息发送最终失败 | error=%s", last_error)
        return FeishuSendResult(
            success=False,
            message=f"发送失败（重试 {max_retries} 次）: {last_error}",
        )
