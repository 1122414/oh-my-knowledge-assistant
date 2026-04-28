import base64
import hashlib
import hmac
import time
from typing import Any

import httpx

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.core.settings_service import get_setting
from omka.app.notifications.base import NotificationChannel, SendResult


class FeishuWebhookChannel(NotificationChannel):
    channel_type = "feishu_webhook"

    async def send_digest(self, digest: dict[str, Any]) -> SendResult:
        webhook_url = get_setting("feishu_webhook_url", "")
        secret = get_setting("feishu_webhook_secret", "")

        if not webhook_url:
            return SendResult(success=False, message="飞书 Webhook URL 未配置")

        if not webhook_url.startswith("http"):
            return SendResult(success=False, message="飞书 Webhook URL 格式错误")

        # 构建消息内容
        text = self._build_message(digest)

        payload = {
            "msg_type": "text",
            "content": {"text": text},
        }

        # 添加签名
        if secret:
            timestamp = str(int(time.time()))
            string_to_sign = f"{timestamp}\n{secret}"
            sign = base64.b64encode(
                hmac.new(
                    secret.encode("utf-8"),
                    string_to_sign.encode("utf-8"),
                    digestmod=hashlib.sha256,
                ).digest()
            ).decode("utf-8")
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        max_retries = get_setting("feishu_max_retries", 3)
        timeout = get_setting("feishu_request_timeout_seconds", 10)

        last_error = ""
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        webhook_url,
                        json=payload,
                        timeout=timeout,
                    )
                    if response.status_code == 200:
                        resp_data = response.json()
                        if resp_data.get("code") == 0:
                            logger.info("飞书推送成功")
                            return SendResult(
                                success=True,
                                message="飞书推送成功",
                                response=resp_data,
                            )
                        else:
                            msg = resp_data.get("msg", "未知错误")
                            logger.warning("飞书返回错误 | msg=%s", msg)
                            return SendResult(
                                success=False,
                                message=f"飞书返回错误: {msg}",
                                response=resp_data,
                            )
                    else:
                        last_error = f"HTTP {response.status_code}"
                        logger.warning("飞书推送失败 | attempt=%d | status=%d", attempt + 1, response.status_code)
            except Exception as e:
                last_error = str(e)
                logger.warning("飞书推送异常 | attempt=%d | error=%s", attempt + 1, e)

        return SendResult(success=False, message=f"飞书推送失败: {last_error}")

    def _build_message(self, digest: dict[str, Any]) -> str:
        phases = digest.get("phases", {})
        fetch = phases.get("fetch", {})
        dedup = phases.get("dedup", {})

        top_n = get_setting("feishu_push_digest_top_n", 6)

        lines = [
            "📌 OMKA 今日 GitHub 知识简报",
            "",
            "今日概览：",
            f"- 抓取条目：{fetch.get('fetched_count', 0)}",
            f"- 候选内容：{dedup.get('candidate_count', 0)}",
            "",
            "🔥 最值得关注",
            "",
        ]

        # 这里可以添加更多详情，但目前保持简洁
        lines.extend([
            "查看完整简报：",
            f"http://127.0.0.1:5173/digest",
        ])

        return "\n".join(lines)
