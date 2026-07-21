from datetime import datetime
from typing import Any

from omka.app.core.logging import logger
from omka.app.core.settings_service import get_setting
from omka.app.integrations.feishu.auth import FeishuAuthService
from omka.app.integrations.feishu.client import FeishuAppBotClient
from omka.app.integrations.feishu.config import FeishuConfig
from omka.app.integrations.feishu.models import FeishuSendResult
from omka.app.storage.db import FeishuMessageRun, get_session


def _build_feishu_config() -> FeishuConfig:
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


class FeishuNotificationService:

    def __init__(self, client: FeishuAppBotClient | None = None):
        self._client: FeishuAppBotClient | None = client
        self._config: FeishuConfig | None = None

    def _ensure_client(self) -> FeishuAppBotClient:
        if self._client is None:
            config = self._get_config()
            auth_service = FeishuAuthService(config)
            self._client = FeishuAppBotClient(config, auth_service)
        return self._client

    def _get_config(self) -> FeishuConfig:
        if self._config is None:
            self._config = _build_feishu_config()
        return self._config

    def _invalidate_config(self) -> None:
        self._config = None
        self._client = None

    def _record_message_run(
        self,
        message_type: str,
        receive_id_type: str,
        receive_id: str,
        result: FeishuSendResult,
    ) -> None:
        masked_id = receive_id[:4] + "****" if len(receive_id) > 4 else "****"
        try:
            with get_session() as session:
                run = FeishuMessageRun(
                    message_type=message_type,
                    receive_id_type=receive_id_type,
                    receive_id_masked=masked_id,
                    status="success" if result.success else "failed",
                    message_id=result.message_id,
                    error_code=result.error_code,
                    error_message=result.message if not result.success else None,
                    request_id=result.request_id,
                )
                session.add(run)
                session.commit()
        except Exception as e:
            logger.error("记录飞书消息发送失败 | error=%s", e)

    async def send_test_message(self, receive_id: str | None = None, receive_id_type: str | None = None) -> FeishuSendResult:
        config = self._get_config()

        if not config.enabled:
            return FeishuSendResult(success=False, message="飞书应用机器人未启用")

        if not config.is_configured():
            return FeishuSendResult(success=False, message="飞书应用凭证未配置")

        target_id = receive_id or config.default_chat_id
        if not target_id:
            return FeishuSendResult(success=False, message="未指定接收者 ID")

        actual_receive_id_type = receive_id_type or config.default_receive_id_type

        test_text = (
            "OMKA 飞书机器人连接成功。\n\n"
            "当前能力：\n"
            "- 每日 GitHub 简报推送\n"
            "- /omka help\n"
            "- /omka status\n"
            "- /omka latest\n\n"
            "Agent 对话能力：暂未开启"
        )

        client = self._ensure_client()
        result = await client.send_text(
            receive_id=target_id,
            text=test_text,
            receive_id_type=actual_receive_id_type,
        )

        self._record_message_run("test", actual_receive_id_type, target_id, result)
        return result

    async def send_latest_digest(self, receive_id: str | None = None, receive_id_type: str | None = None) -> FeishuSendResult:
        config = self._get_config()

        if not config.enabled:
            return FeishuSendResult(success=False, message="飞书应用机器人未启用")

        if not config.is_configured():
            return FeishuSendResult(success=False, message="飞书应用凭证未配置")

        target_id = receive_id or config.default_chat_id
        if not target_id:
            return FeishuSendResult(success=False, message="未指定接收者 ID")

        actual_receive_id_type = receive_id_type or config.default_receive_id_type

        from omka.app.storage.db import CandidateItem
        from sqlmodel import col, select

        try:
            with get_session() as session:
                candidates = session.exec(
                    select(CandidateItem)
                    .where(CandidateItem.status == "pending")
                    .order_by(col(CandidateItem.score).desc())
                    .limit(config.push_digest_top_n)
                ).all()

            if not candidates:
                return FeishuSendResult(success=False, message="没有待推送的候选内容")

            lines = [
                "📌 OMKA 今日 GitHub 知识简报",
                "",
                f"共 {len(candidates)} 条推荐内容",
                "",
            ]

            for i, candidate in enumerate(candidates, 1):
                lines.append(f"{i}. {candidate.title}")
                if candidate.summary:
                    lines.append(f"   摘要：{candidate.summary[:100]}...")
                if candidate.recommendation_reason:
                    lines.append(f"   推荐理由：{candidate.recommendation_reason}")
                lines.append("")

            text = "\n".join(lines)

            client = self._ensure_client()
            result = await client.send_text(
                receive_id=target_id,
                text=text,
                receive_id_type=actual_receive_id_type,
            )

            self._record_message_run("digest", actual_receive_id_type, target_id, result)
            return result

        except Exception as e:
            logger.error("发送最新简报失败 | error=%s", e)
            return FeishuSendResult(success=False, message=f"发送失败: {str(e)}")

    async def send_digest(self, digest: dict[str, Any], receive_id: str | None = None, receive_id_type: str | None = None) -> FeishuSendResult:
        config = self._get_config()

        if not config.enabled:
            return FeishuSendResult(success=False, message="飞书应用机器人未启用")

        if not config.is_configured():
            return FeishuSendResult(success=False, message="飞书应用凭证未配置")

        target_id = receive_id or config.default_chat_id
        if not target_id:
            return FeishuSendResult(success=False, message="未指定接收者 ID")

        # 根据传入的 receive_id 确定类型；若未指定则使用配置默认值
        actual_receive_id_type = receive_id_type or config.default_receive_id_type

        phases = digest.get("phases", {})
        fetch = phases.get("fetch", {})
        dedup = phases.get("dedup", {})
        digest_info = phases.get("digest", {})

        lines = [
            "📌 OMKA 今日 GitHub 知识简报",
            "",
            "今日概览：",
            f"- 抓取条目：{fetch.get('fetched_count', 0)}",
            f"- 候选内容：{dedup.get('candidate_count', 0)}",
            "",
        ]

        public_url = get_setting("feishu_public_callback_url", "")
        if digest_info.get("digest_path") and public_url:
            lines.extend([
                "查看完整简报：",
                f"{public_url}/digest",
            ])

        text = "\n".join(lines)

        client = self._ensure_client()
        result = await client.send_text(
            receive_id=target_id,
            text=text,
            receive_id_type=actual_receive_id_type,
        )

        self._record_message_run("digest", actual_receive_id_type, target_id, result)
        return result


feishu_notification_service = FeishuNotificationService()
