from datetime import datetime
from typing import Any

from omka.app.core.logging import logger
from omka.app.core.settings_service import get_setting
from omka.app.notifications.base import SendResult
from omka.app.notifications.channels.feishu_webhook import FeishuWebhookChannel
from omka.app.storage.db import NotificationRun, get_session


class NotificationService:
    def __init__(self):
        self.channels = {
            "feishu_webhook": FeishuWebhookChannel(),
        }

    async def send_digest(self, digest: dict[str, Any]) -> dict[str, Any]:
        results = {}

        # 检查是否启用飞书推送
        if get_setting("feishu_webhook_enabled", False):
            result = await self._send_with_channel("feishu_webhook", digest)
            results["feishu_webhook"] = result

        return results

    async def _send_with_channel(
        self, channel_type: str, digest: dict[str, Any]
    ) -> SendResult:
        channel = self.channels.get(channel_type)
        if not channel:
            return SendResult(success=False, message=f"未知渠道: {channel_type}")

        # 创建通知记录
        notification_run = NotificationRun(
            channel_type=channel_type,
            status="running",
        )
        with get_session() as session:
            session.add(notification_run)
            session.commit()
            run_id = notification_run.id

        try:
            result = await channel.send_digest(digest)

            # 更新记录
            with get_session() as session:
                run = session.get(NotificationRun, run_id)
                if run:
                    run.status = "success" if result.success else "failed"
                    run.sent_at = datetime.utcnow()
                    if not result.success:
                        run.error_message = result.message
                    if result.response:
                        run.response_json = result.response
                    session.add(run)
                    session.commit()

            return result
        except Exception as e:
            logger.error("通知发送异常 | channel=%s | error=%s", channel_type, e)

            # 更新记录为失败
            with get_session() as session:
                run = session.get(NotificationRun, run_id)
                if run:
                    run.status = "failed"
                    run.error_message = str(e)
                    run.sent_at = datetime.utcnow()
                    session.add(run)
                    session.commit()

            return SendResult(success=False, message=f"发送异常: {str(e)}")


# 全局服务实例
notification_service = NotificationService()
