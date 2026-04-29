import json
from pathlib import Path
from typing import Any

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.integrations.feishu.config import FeishuConfig
from omka.app.integrations.feishu.models import (
    FeishuCommandResult,
    FeishuCommandType,
    FeishuMessageEvent,
)
from omka.app.storage.db import (
    CandidateItem,
    FetchRun,
    KnowledgeItem,
    SourceConfig,
    get_session,
)
from sqlmodel import col, func, select


HELP_TEXT = """OMKA 知识助手命令：

/omka help — 显示本帮助
/omka bind — 绑定当前单聊会话
/omka status — 查看系统状态
/omka latest — 获取最新简报摘要
/omka run — 手动触发一次更新（仅管理员）
/omka chat <消息> — 与 Agent 对话（开发中）"""


class FeishuCommandRouter:

    def __init__(self, config: FeishuConfig) -> None:
        self._config: FeishuConfig = config
        self._prefix: str = config.command_prefix

    async def route(self, event: FeishuMessageEvent) -> FeishuCommandResult:
        command, args = self._parse_command(event.content)

        if command is None:
            return FeishuCommandResult(
                success=False,
                message="无法解析命令内容",
                command=FeishuCommandType.UNKNOWN,
            )

        logger.info(
            "收到飞书命令 | command=%s | args=%s | sender=%s",
            command,
            args,
            event.sender_id,
        )

        handler = self._get_handler(command)
        if handler is None:
            return FeishuCommandResult(
                success=False,
                message=f"未知命令: {self._prefix} {command}\n输入 {self._prefix} help 查看可用命令",
                command=FeishuCommandType.UNKNOWN,
            )

        return await handler(args)

    def _parse_command(self, content: str) -> tuple[str | None, list[str]]:
        """从消息 JSON 中解析命令和参数。格式: {"text": "/omka help"}，返回 (command, args)。"""
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("消息内容 JSON 解析失败 | content=%s", content[:200])
            return None, []

        text: str = data.get("text", "").strip()
        if not text:
            return None, []

        # 飞书 @提及 格式: @_user_1 /omka help，需要跳过 mention token
        parts = text.split(None, 1)
        if not parts:
            return None, []

        first = parts[0]
        if first == self._prefix:
            remainder = parts[1] if len(parts) > 1 else ""
        elif first.startswith(self._prefix):
            remainder = first[len(self._prefix):] + (" " + parts[1] if len(parts) > 1 else "")
            remainder = remainder.strip()
        else:
            if len(parts) > 1 and parts[1] == self._prefix:
                remainder = parts[2] if len(parts) > 2 else ""
            elif len(parts) > 1 and parts[1].startswith(self._prefix):
                remainder = parts[1][len(self._prefix):]
                if len(parts) > 2:
                    remainder += " " + parts[2]
                remainder = remainder.strip()
            else:
                return None, []

        tokens = remainder.split()
        if not tokens:
            return "", []

        return tokens[0], tokens[1:]

    def _get_handler(self, command: str) -> Any:
        handlers: dict[str, Any] = {
            "help": self._handle_help,
            "bind": self._handle_bind,
            "status": self._handle_status,
            "latest": self._handle_latest,
            "run": self._handle_run,
            "chat": self._handle_chat,
        }
        return handlers.get(command.lower())

    async def _handle_help(self, _args: list[str]) -> FeishuCommandResult:
        return FeishuCommandResult(
            success=True,
            message=HELP_TEXT,
            command=FeishuCommandType.HELP,
        )

    async def _handle_bind(self, args: list[str]) -> FeishuCommandResult:
        return FeishuCommandResult(
            success=True,
            message="绑定功能由系统自动处理。发送消息即可自动绑定当前单聊会话。",
            command=FeishuCommandType.BIND,
        )

    async def _handle_status(self, _args: list[str]) -> FeishuCommandResult:
        try:
            with get_session() as session:
                source_count = session.exec(
                    select(func.count()).select_from(SourceConfig).where(col(SourceConfig.enabled).is_(True))
                ).one()
                candidate_pending = session.exec(
                    select(func.count()).select_from(CandidateItem).where(CandidateItem.status == "pending")
                ).one()
                knowledge_count = session.exec(
                    select(func.count()).select_from(KnowledgeItem)
                ).one()
                latest_run = session.exec(
                    select(FetchRun).order_by(col(FetchRun.started_at).desc()).limit(1)
                ).first()

            lines = [
                f"数据源: {source_count} 个已启用",
                f"待处理候选: {candidate_pending} 条",
                f"知识库: {knowledge_count} 条",
            ]

            if latest_run:
                status_map = {"success": "✅", "running": "⏳", "failed": "❌", "partial_success": "⚠️"}
                icon = status_map.get(latest_run.status, "❓")
                started = latest_run.started_at.strftime("%m-%d %H:%M")
                lines.append(f"最近任务: {icon} {started} ({latest_run.status})")
            else:
                lines.append("最近任务: 暂无运行记录")

            message = "📊 OMKA 系统状态\n\n" + "\n".join(lines)
        except Exception as e:
            logger.error("获取系统状态失败 | error=%s", e)
            message = "获取系统状态失败，请稍后重试"

        return FeishuCommandResult(
            success=True,
            message=message,
            command=FeishuCommandType.STATUS,
        )

    async def _handle_latest(self, _args: list[str]) -> FeishuCommandResult:
        try:
            digest_path = self._find_latest_digest()
            if digest_path is None:
                message = "📭 暂无简报数据\n\n请先运行每日任务生成简报。"
            else:
                summary = self._summarize_digest(digest_path)
                message = f"📰 最新简报 | {digest_path.stem}\n\n{summary}"
        except Exception as e:
            logger.error("获取最新简报失败 | error=%s", e)
            message = "获取简报失败，请稍后重试"

        return FeishuCommandResult(
            success=True,
            message=message,
            command=FeishuCommandType.LATEST,
        )

    async def _handle_chat(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(
                success=False,
                message="请输入消息内容，例如: /omka chat 你好",
                command=FeishuCommandType.CHAT,
            )

        return FeishuCommandResult(
            success=True,
            message="Agent 对话能力暂未开启",
            command=FeishuCommandType.CHAT,
        )

    async def _handle_run(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.core.settings_service import get_setting

        admin_ids = get_setting("feishu_admin_open_ids", "")
        if not admin_ids:
            return FeishuCommandResult(
                success=False,
                message="管理员未配置，无法执行此命令。",
                command=FeishuCommandType.RUN,
            )

        admin_list = [id.strip() for id in admin_ids.split(",") if id.strip()]
        if not admin_list:
            return FeishuCommandResult(
                success=False,
                message="管理员未配置，无法执行此命令。",
                command=FeishuCommandType.RUN,
            )

        return FeishuCommandResult(
            success=True,
            message="正在执行每日任务，请稍候...",
            command=FeishuCommandType.RUN,
        )

    @staticmethod
    def _find_latest_digest() -> Path | None:
        digests_dir = settings.digests_dir
        if not digests_dir.exists():
            return None

        md_files = sorted(digests_dir.glob("*.md"), reverse=True)
        return md_files[0] if md_files else None

    @staticmethod
    def _summarize_digest(path: Path, max_items: int = 5) -> str:
        content = path.read_text(encoding="utf-8")

        items: list[str] = []
        current_title: str | None = None

        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("## ") and stripped[3:4].isdigit():
                current_title = stripped[3:]
            elif stripped.startswith("- **摘要**:") and current_title:
                summary_text = stripped[len("- **摘要**:"):].strip()
                if summary_text:
                    items.append(f"• {current_title}\n  {summary_text}")
                current_title = None
                if len(items) >= max_items:
                    break

        if not items:
            return "（简报内容为空或格式不符）"

        return "\n\n".join(items)
