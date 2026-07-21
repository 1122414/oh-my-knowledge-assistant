import base64
import hashlib
import hmac
import time
from typing import Any

import httpx

from omka.app.core.logging import logger
from omka.app.core.settings_service import get_setting
from omka.app.notifications.base import NotificationChannel, SendResult


class FeishuWebhookChannel(NotificationChannel):
    """飞书群机器人 Webhook 推送渠道（已废弃）"""

    def __init__(self, webhook_url: str | None = None, secret: str | None = None):
        self._webhook_url = webhook_url
        self._secret = secret

    @property
    def is_available(self) -> bool:
        return bool(self._webhook_url)

    async def send_digest(self, digest: dict[str, Any]) -> SendResult:
        if not self._webhook_url:
            return SendResult(success=False, error="Webhook URL not configured")

        content = self._build_content(digest)
        if not content:
            return SendResult(success=False, error="Empty content")

        timestamp = str(int(time.time()))
        sign = self._generate_sign(timestamp)

        payload: dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": content},
        }
        if sign:
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    self._webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    body = resp.json()
                    if body.get("code") == 0 or body.get("StatusCode") == 0:
                        logger.info("飞书 Webhook 推送成功")
                        return SendResult(success=True)
                    msg = body.get("msg", str(body))
                    logger.error("飞书 Webhook 推送失败 | resp=%s", body)
                    return SendResult(success=False, error=msg)
                logger.error("飞书 Webhook 推送失败 | status=%d | body=%s", resp.status_code, resp.text[:200])
                return SendResult(success=False, error=f"HTTP {resp.status_code}")
        except Exception as e:
            logger.error("飞书 Webhook 推送异常 | error=%s", e)
            return SendResult(success=False, error=str(e))

    def _generate_sign(self, timestamp: str) -> str:
        if not self._secret:
            return ""
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            self._secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        )
        return base64.b64encode(hmac_code.digest()).decode("utf-8")

    def _build_content(self, digest: dict[str, Any]) -> str:
        phases = digest.get("phases", {})
        fetch = phases.get("fetch", {})
        dedup = phases.get("dedup", {})

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

        public_url = get_setting("feishu_public_callback_url", "")
        if public_url:
            lines.extend([
                "查看完整简报：",
                f"{public_url.rstrip('/')}/digest",
            ])

        return "\n".join(lines)
