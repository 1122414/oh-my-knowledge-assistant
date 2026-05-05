import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omka.app.core.config import settings
from omka.app.core.logging import get_logger

logger = get_logger("feishu")
from omka.app.integrations.feishu.config import FeishuConfig
from omka.app.integrations.feishu.models import (
    FeishuCommandResult,
    FeishuCommandType,
    FeishuMessageEvent,
)
from omka.app.services.nlu_service import NLUService
from omka.app.storage.db import (
    CandidateItem,
    FetchRun,
    KnowledgeItem,
    SourceConfig,
    get_session,
)
from sqlmodel import col, func, select


HELP_TEXT = """OMKA 知识助手命令：

基础：
/omka help — 显示本帮助
/omka bind — 绑定当前单聊会话
/omka status — 查看系统状态
/omka latest — 获取最新简报摘要
/omka run — 手动触发一次更新（仅管理员）
/omka chat <消息> — 与 Agent 对话

信息源：
/omka source list — 查看信息源列表
/omka source add repo <owner/repo> — 添加仓库源
/omka source add search <关键词> [limit <数量>] — 添加搜索源
/omka source delete <source_id> — 删除信息源
/omka source disable <source_id> — 停用信息源
/omka source enable <source_id> — 启用信息源
/omka source run <source_id> — 立即运行信息源

候选知识：
/omka candidate list — 查看候选列表
/omka candidate save <candidate_id> — 确认入库
/omka candidate ignore <candidate_id> — 忽略候选
/omka candidate ignore all — 批量忽略所有待处理候选
/omka candidate later <candidate_id> — 稍后阅读

知识库：
/omka knowledge list — 查看知识库
/omka knowledge search <关键词> — 搜索知识库
/omka knowledge delete <knowledge_id> — 删除知识条目

配置：
/omka config list — 查看配置列表
/omka config get <key> — 获取配置值
/omka config set <key> <value> — 设置配置值（非敏感）

推送：
/omka push status — 查看推送状态
/omka push pause — 暂停推送
/omka push resume — 恢复推送

定时任务：
/omka schedule — 查看定时任务
/omka schedule set <时间> — 设置定时 (如: 每天9:30 / 每周一18:00 / 0 9 * * *)

推荐反馈：
/omka why <candidate_id> — 查看推荐原因
/omka more-like <candidate_id> — 标记偏好
/omka dislike <candidate_id> — 标记不感兴趣
/omka later <candidate_id> — 稍后阅读

记忆管理：
/omka memory list — 查看记忆列表
/omka memory profile — 查看记忆统计
/omka memory add <内容> — 添加用户记忆
/omka memory confirm <记忆ID> — 确认候选记忆
/omka memory reject <记忆ID> — 拒绝候选记忆
/omka memory delete <记忆ID> — 删除记忆

多模态资产：
/omka assets — 查看资产列表

飞书云文档：
/omka doc digest — 将最新简报保存为飞书文档
/omka doc create <标题> [内容] — 创建飞书云文档

飞书多维表格：
/omka base import — 将知识库导入多维表格
/omka base create <名称> — 创建多维表格

飞书电子表格：
/omka sheet export candidates — 候选池导出为表格
/omka sheet export knowledge — 知识库导出为表格

飞书日历：
/omka calendar list — 查看日历列表
/omka calendar review <时间> — 创建知识回顾日历事件

飞书任务：
/omka task add <内容> — 添加飞书任务"""


class FeishuCommandRouter:

    def __init__(self, config: FeishuConfig) -> None:
        self._config: FeishuConfig = config
        self._prefix: str = config.command_prefix
        self._current_sender_id: str = ""
        self._pending_confirmations: dict[int, dict] = {}
        self._nlu = NLUService()

    async def route(self, event: FeishuMessageEvent) -> FeishuCommandResult:
        self._current_sender_id = event.sender_id
        command, args = self._parse_command(event.content)

        if command is None:
            text = self._extract_text(event.content)
            nlu_result = await self._nlu.parse(text)
            if nlu_result:
                command, args = self._nlu_to_command(nlu_result)
                logger.info(
                    "NLU 解析 | text=%s | command=%s | args=%s | confidence=%.2f",
                    text[:50],
                    command,
                    args,
                    nlu_result.get("confidence", 0),
                )
            else:
                return FeishuCommandResult(
                    success=False,
                    message="无法解析命令内容。输入 /omka help 查看可用命令，或用自然语言描述您的需求。",
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

        result = await handler(args)
        self._audit_if_needed(command, args, result)
        return result

    def _audit_if_needed(self, command: str, args: list[str], result: FeishuCommandResult) -> None:
        if command in ("help", "status", "latest", "list", "get", "search"):
            return
        if not result.success and result.command == FeishuCommandType.UNKNOWN:
            return
        try:
            from omka.app.services.action_service import ActionService
            action = ActionService.create_action(
                action_type=f"feishu.{command}",
                actor_channel="feishu",
                actor_external_id=self._current_sender_id,
                target_type="command",
                request_text=f"{command} {' '.join(args)}",
                params_json={"command": command, "args": args, "success": result.success},
            )
            ActionService.complete_action(
                action_id=action.id,
                status="success" if result.success else "failed",
                result_json={"message": result.message[:200] if result.message else ""},
            )
        except Exception as e:
            logger.debug("审计记录失败 | error=%s", e)

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

    def _extract_text(self, content: str) -> str:
        try:
            data = json.loads(content)
            return data.get("text", "").strip()
        except (json.JSONDecodeError, TypeError):
            return content.strip()

    def _nlu_to_command(self, nlu_result: dict) -> tuple[str, list[str]]:
        command = nlu_result["command"]
        args = nlu_result.get("args", [])
        parts = command.split(".")
        if len(parts) == 1:
            return parts[0], args
        return parts[0], parts[1:] + args

    def _get_handler(self, command: str) -> Any:
        handlers: dict[str, Any] = {
            "help": self._handle_help,
            "bind": self._handle_bind,
            "status": self._handle_status,
            "latest": self._handle_latest,
            "run": self._handle_run,
            "chat": self._handle_chat,
            "memory": self._handle_memory,
            "why": self._handle_why,
            "more-like": self._handle_more_like,
            "dislike": self._handle_dislike_feishu,
            "later": self._handle_later,
            "source": self._handle_source,
            "candidate": self._handle_candidate,
            "config": self._handle_config,
            "push": self._handle_push,
            "schedule": self._handle_schedule,
            "knowledge": self._handle_knowledge,
            "confirm": self._handle_confirm,
            "cancel": self._handle_cancel,
            "assets": self._handle_assets,
            "doc": self._handle_doc,
            "base": self._handle_base,
            "sheet": self._handle_sheet,
            "calendar": self._handle_calendar,
            "task": self._handle_task,
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
            with get_session() as session:
                candidates = session.exec(
                    select(CandidateItem)
                    .where(CandidateItem.status == "pending")
                    .order_by(CandidateItem.score.desc())
                    .limit(settings.digest_top_n)
                ).all()
            if not candidates:
                message = "暂无待推荐内容\n\n运行 /omka run 触发每日任务获取最新推荐。"
            else:
                lines = []
                for i, c in enumerate(candidates, 1):
                    lines.append(f"{i}. {c.title}")
                    if c.summary:
                        lines.append(f"   {c.summary[:150]}")
                    lines.append(f"   score={c.score:.2f} | {c.item_type}")
                message = f"当前每日推荐 Top {len(candidates)}\n\n" + "\n".join(lines)
        except Exception as e:
            logger.error("获取最新推荐失败 | error=%s", e)
            message = "获取推荐失败，请稍后重试"

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
            success=False,
            message="",
            command=FeishuCommandType.CHAT,
            args=args,
        )

    async def _handle_memory(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(
                success=True,
                message="请指定记忆子命令: list / profile / add / confirm / reject / delete",
                command=FeishuCommandType.UNKNOWN,
            )

        subcommand = args[0].lower()

        try:
            if subcommand == "list":
                return await self._handle_memory_list(args[1:])
            elif subcommand == "profile":
                return await self._handle_memory_profile()
            elif subcommand == "add":
                return await self._handle_memory_add(args[1:])
            elif subcommand == "confirm":
                return await self._handle_memory_confirm(args[1:])
            elif subcommand == "reject":
                return await self._handle_memory_reject(args[1:])
            elif subcommand == "delete":
                return await self._handle_memory_delete(args[1:])
            else:
                return FeishuCommandResult(
                    success=False,
                    message=f"未知记忆子命令: {subcommand}\n可用: list / profile / add / confirm / reject / delete",
                    command=FeishuCommandType.UNKNOWN,
                )
        except Exception as e:
            logger.error("处理记忆命令失败 | subcommand=%s | error=%s", subcommand, e)
            return FeishuCommandResult(
                success=False,
                message=f"处理记忆命令失败: {str(e)}",
                command=FeishuCommandType.UNKNOWN,
            )

    async def _handle_memory_list(self, _args: list[str]) -> FeishuCommandResult:
        from omka.app.services.memory_service import MemoryService

        memories = MemoryService.list_memories(limit=20)
        if not memories:
            message = "📝 记忆列表为空\n\n还没有记录任何记忆。"
        else:
            lines = ["📝 记忆列表（最近20条）\n"]
            for m in memories:
                status_icon = {"active": "✅", "candidate": "⏳", "rejected": "❌", "archived": "📦"}.get(m.status, "❓")
                lines.append(f"{status_icon} [{m.memory_type}] {m.subject}")
                lines.append(f"   ID: {m.id}")
                lines.append(f"   内容: {m.content[:60]}..." if len(m.content) > 60 else f"   内容: {m.content}")
                if m.tags:
                    lines.append(f"   标签: {', '.join(m.tags)}")
                lines.append("")
            message = "\n".join(lines)

        return FeishuCommandResult(success=True, message=message, command=FeishuCommandType.UNKNOWN)

    async def _handle_memory_profile(self) -> FeishuCommandResult:
        from omka.app.services.memory_service import MemoryService

        summary = {
            "user": MemoryService.count_memories(memory_type="user"),
            "conversation": MemoryService.count_memories(memory_type="conversation"),
            "system": MemoryService.count_memories(memory_type="system"),
            "candidate": MemoryService.count_memories(status="candidate"),
        }

        lines = [
            "🧠 记忆统计",
            "",
            f"用户记忆: {summary['user']} 条",
            f"对话记忆: {summary['conversation']} 条",
            f"系统记忆: {summary['system']} 条",
            f"候选记忆: {summary['candidate']} 条",
        ]
        return FeishuCommandResult(success=True, message="\n".join(lines), command=FeishuCommandType.UNKNOWN)

    async def _handle_memory_add(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.memory_service import MemoryService

        if not args:
            return FeishuCommandResult(
                success=False,
                message="请提供记忆内容，例如: /omka memory add 我最近重点关注多模态知识资产",
                command=FeishuCommandType.UNKNOWN,
            )

        content = " ".join(args)
        memory = MemoryService.create_memory(
            memory_type="user",
            subject="manual_add",
            content=content,
            scope="user",
            source_type="manual",
            importance=0.7,
        )
        return FeishuCommandResult(
            success=True,
            message=f"✅ 已添加用户记忆\n\nID: {memory.id}\n内容: {content[:100]}",
            command=FeishuCommandType.UNKNOWN,
        )

    async def _handle_memory_confirm(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.memory_service import MemoryService

        if not args:
            return FeishuCommandResult(
                success=False,
                message="请提供记忆 ID，例如: /omka memory confirm mem_xxx",
                command=FeishuCommandType.UNKNOWN,
            )

        memory_id = args[0]
        memory = MemoryService.confirm_memory(memory_id)
        if not memory:
            return FeishuCommandResult(
                success=False,
                message=f"记忆不存在: {memory_id}",
                command=FeishuCommandType.UNKNOWN,
            )
        return FeishuCommandResult(
            success=True,
            message=f"✅ 记忆已确认\n\nID: {memory_id}\n状态: active",
            command=FeishuCommandType.UNKNOWN,
        )

    async def _handle_memory_reject(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.memory_service import MemoryService

        if not args:
            return FeishuCommandResult(
                success=False,
                message="请提供记忆 ID，例如: /omka memory reject mem_xxx",
                command=FeishuCommandType.UNKNOWN,
            )

        memory_id = args[0]
        memory = MemoryService.reject_memory(memory_id)
        if not memory:
            return FeishuCommandResult(
                success=False,
                message=f"记忆不存在: {memory_id}",
                command=FeishuCommandType.UNKNOWN,
            )
        return FeishuCommandResult(
            success=True,
            message=f"❌ 记忆已拒绝\n\nID: {memory_id}\n状态: rejected",
            command=FeishuCommandType.UNKNOWN,
        )

    async def _handle_memory_delete(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.action_service import ActionService, PermissionService
        from omka.app.services.memory_service import MemoryService

        if not PermissionService.check_permission(self._current_sender_id, "operator"):
            return FeishuCommandResult(success=False, message="权限不足，删除记忆需要 operator 权限", command=FeishuCommandType.UNKNOWN)

        if not args:
            return FeishuCommandResult(
                success=False,
                message="请提供记忆 ID，例如: /omka memory delete mem_xxx",
                command=FeishuCommandType.UNKNOWN,
            )

        memory_id = args[0]
        action = ActionService.create_action(
            action_type="memory.delete",
            actor_channel="feishu",
            actor_external_id=self._current_sender_id,
            target_type="memory",
            target_id=memory_id,
            request_text=f"memory delete {memory_id}",
            params_json={"memory_id": memory_id},
        )
        message = self._create_pending_confirmation(action.id, "memory.delete", {"memory_id": memory_id})
        return FeishuCommandResult(success=False, message=message, command=FeishuCommandType.UNKNOWN)

    async def _handle_why(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.recommendation_service import RecommendationService

        if not args:
            return FeishuCommandResult(
                success=False,
                message="请提供候选 ID，例如: /omka why candidate:xxx",
                command=FeishuCommandType.UNKNOWN,
            )

        candidate_id = args[0].replace("candidate:", "")
        explanation = RecommendationService.get_explanation(candidate_id)
        if not explanation:
            return FeishuCommandResult(
                success=False,
                message=f"未找到候选 {candidate_id} 的推荐解释",
                command=FeishuCommandType.UNKNOWN,
            )

        exp_json = explanation.get("explanation_json", {})
        lines = [f"💡 为什么推荐 {candidate_id}", ""]
        lines.append(explanation.get("explanation", "暂无解释"))
        if exp_json.get("matched_interests"):
            lines.append(f"\n匹配兴趣: {', '.join(exp_json['matched_interests'])}")
        lines.append(f"\n最终得分: {explanation.get('final_score', 0):.4f}")
        lines.append(f"排名: #{explanation.get('rank', 0)}")

        return FeishuCommandResult(success=True, message="\n".join(lines), command=FeishuCommandType.UNKNOWN)

    async def _handle_more_like(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.memory_service import MemoryService

        content = " ".join(args) if args else "用户希望看到更多类似内容"
        memory = MemoryService.create_memory(
            memory_type="user",
            subject="preference",
            content=content,
            scope="user",
            source_type="feedback",
            importance=0.85,
        )
        return FeishuCommandResult(
            success=True,
            message=f"✅ 已记录偏好\n\nID: {memory.id}\n内容: {content[:100]}",
            command=FeishuCommandType.UNKNOWN,
        )

    async def _handle_dislike_feishu(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.recommendation_service import RecommendationService

        if not args:
            return FeishuCommandResult(
                success=False,
                message="请提供候选 ID，例如: /omka dislike candidate:xxx",
                command=FeishuCommandType.UNKNOWN,
            )

        candidate_id = args[0].replace("candidate:", "")
        RecommendationService.record_feedback(candidate_id, "dislike")
        return FeishuCommandResult(
            success=True,
            message=f"❌ 已标记不感兴趣\n\n候选: {candidate_id}",
            command=FeishuCommandType.UNKNOWN,
        )

    async def _handle_later(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.recommendation_service import RecommendationService

        if not args:
            return FeishuCommandResult(
                success=False,
                message="请提供候选 ID，例如: /omka later candidate:xxx",
                command=FeishuCommandType.UNKNOWN,
            )

        candidate_id = args[0].replace("candidate:", "")
        RecommendationService.record_feedback(candidate_id, "read_later")
        return FeishuCommandResult(
            success=True,
            message=f"📌 已标记稍后阅读\n\n候选: {candidate_id}",
            command=FeishuCommandType.UNKNOWN,
        )

    async def _handle_source(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.action_service import PermissionService, SourceActionService

        if not args:
            sources = SourceActionService.list_sources()
            lines = ["📡 信息源列表\n"]
            for s in sources:
                status = "✅" if s.enabled else "⏸️"
                lines.append(f"{status} {s.name} ({s.mode})")
                lines.append(f"   ID: {s.id}")
                if s.mode == "repo":
                    lines.append(f"   仓库: {s.repo_full_name}")
                else:
                    lines.append(f"   搜索: {s.query} | 限制: {s.limit}")
            return FeishuCommandResult(success=True, message="\n".join(lines), command=FeishuCommandType.SOURCE)

        subcommand = args[0].lower()
        if subcommand == "list":
            return await self._handle_source([])

        if subcommand == "add":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，添加信息源需要 operator 权限", command=FeishuCommandType.SOURCE)
            if len(args) < 3:
                return FeishuCommandResult(success=False, message="用法: /omka source add repo <owner/repo>\n或: /omka source add search <关键词> [limit <数量>]", command=FeishuCommandType.SOURCE)
            add_mode = args[1].lower()
            if add_mode == "repo":
                repo = args[2]
                source_id = f"src_repo_{repo.replace('/', '_')}"
                SourceActionService.create_source(source_id=source_id, name=repo, source_type="github", mode="repo", repo_full_name=repo)
                return FeishuCommandResult(success=True, message=f"✅ 已添加仓库源\n\nID: {source_id}\n仓库: {repo}", command=FeishuCommandType.SOURCE)
            elif add_mode == "search":
                query = args[2]
                limit = 5
                if "limit" in args:
                    try:
                        limit = int(args[args.index("limit") + 1])
                    except (ValueError, IndexError):
                        pass
                source_id = f"src_search_{query.replace(' ', '_')[:30]}"
                SourceActionService.create_source(source_id=source_id, name=query, source_type="github", mode="search", query=query, limit=limit)
                return FeishuCommandResult(success=True, message=f"✅ 已添加搜索源\n\nID: {source_id}\n关键词: {query}\n限制: {limit}", command=FeishuCommandType.SOURCE)
            return FeishuCommandResult(success=False, message="用法: /omka source add repo <owner/repo> 或 search <关键词>", command=FeishuCommandType.SOURCE)

        if subcommand in ("delete", "remove"):
            if not PermissionService.check_permission(self._current_sender_id, "admin"):
                return FeishuCommandResult(success=False, message="权限不足，删除信息源需要 admin 权限", command=FeishuCommandType.SOURCE)
            if len(args) < 2:
                return FeishuCommandResult(success=False, message="请提供信息源 ID", command=FeishuCommandType.SOURCE)
            source_id = args[1]
            from omka.app.services.action_service import ActionService
            action = ActionService.create_action(
                action_type="source.delete",
                actor_channel="feishu",
                actor_external_id=self._current_sender_id,
                target_type="source",
                target_id=source_id,
                request_text=f"source delete {source_id}",
                params_json={"source_id": source_id},
            )
            message = self._create_pending_confirmation(action.id, "source.delete", {"source_id": source_id})
            return FeishuCommandResult(success=False, message=message, command=FeishuCommandType.SOURCE)

        if subcommand == "disable":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，停用信息源需要 operator 权限", command=FeishuCommandType.SOURCE)
            if len(args) < 2:
                return FeishuCommandResult(success=False, message="请提供信息源 ID", command=FeishuCommandType.SOURCE)
            source_id = args[1]
            if SourceActionService.set_source_enabled(source_id, False):
                return FeishuCommandResult(success=True, message=f"⏸️ 已停用信息源\n\nID: {source_id}", command=FeishuCommandType.SOURCE)
            return FeishuCommandResult(success=False, message=f"信息源不存在: {source_id}", command=FeishuCommandType.SOURCE)

        if subcommand == "enable":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，启用信息源需要 operator 权限", command=FeishuCommandType.SOURCE)
            if len(args) < 2:
                return FeishuCommandResult(success=False, message="请提供信息源 ID", command=FeishuCommandType.SOURCE)
            source_id = args[1]
            if SourceActionService.set_source_enabled(source_id, True):
                return FeishuCommandResult(success=True, message=f"✅ 已启用信息源\n\nID: {source_id}", command=FeishuCommandType.SOURCE)
            return FeishuCommandResult(success=False, message=f"信息源不存在: {source_id}", command=FeishuCommandType.SOURCE)

        if subcommand == "run":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，运行信息源需要 operator 权限", command=FeishuCommandType.SOURCE)
            if len(args) < 2:
                return FeishuCommandResult(success=False, message="请提供信息源 ID", command=FeishuCommandType.SOURCE)
            source_id = args[1]
            config = SourceActionService.get_source(source_id)
            if not config:
                return FeishuCommandResult(success=False, message=f"信息源不存在: {source_id}", command=FeishuCommandType.SOURCE)
            try:
                import asyncio
                from omka.app.api.routes_sources import run_source
                asyncio.create_task(run_source(source_id))
                return FeishuCommandResult(success=True, message=f"▶️ 已触发运行\n\nID: {source_id}\n请稍候查看结果", command=FeishuCommandType.SOURCE)
            except Exception as e:
                logger.error("运行信息源失败 | error=%s", e)
                return FeishuCommandResult(success=False, message=f"运行失败: {str(e)}", command=FeishuCommandType.SOURCE)

        return FeishuCommandResult(
            success=False,
            message=f"未知信息源子命令: {subcommand}\n可用: list / add / delete / disable / enable / run",
            command=FeishuCommandType.SOURCE,
        )

    async def _handle_candidate(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.action_service import CandidateActionService, PermissionService

        if not args:
            candidates = CandidateActionService.list_candidates(status="pending", limit=10)
            if not candidates:
                return FeishuCommandResult(success=True, message="📭 暂无待处理候选", command=FeishuCommandType.CANDIDATE)
            lines = ["📋 候选列表（最近10条）\n"]
            for i, c in enumerate(candidates, 1):
                lines.append(f"{i}. {c.title}")
                lines.append(f"   ID: {c.id} | 分数: {c.score:.2f}")
                if c.summary:
                    lines.append(f"   摘要: {c.summary[:80]}...")
                lines.append("")
            return FeishuCommandResult(success=True, message="\n".join(lines), command=FeishuCommandType.CANDIDATE)

        subcommand = args[0].lower()
        if subcommand == "list":
            return await self._handle_candidate([])

        if subcommand in ("save", "confirm"):
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，确认入库需要 operator 权限", command=FeishuCommandType.CANDIDATE)
            if len(args) < 2:
                return FeishuCommandResult(success=False, message="请提供候选 ID", command=FeishuCommandType.CANDIDATE)
            candidate_id = args[1]
            if CandidateActionService.confirm_candidate(candidate_id):
                return FeishuCommandResult(success=True, message=f"✅ 已入库\n\n候选: {candidate_id}", command=FeishuCommandType.CANDIDATE)
            return FeishuCommandResult(success=False, message=f"候选不存在: {candidate_id}", command=FeishuCommandType.CANDIDATE)

        if subcommand == "ignore":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，忽略候选需要 operator 权限", command=FeishuCommandType.CANDIDATE)
            if len(args) < 2:
                return FeishuCommandResult(success=False, message="请提供候选 ID", command=FeishuCommandType.CANDIDATE)
            candidate_id = args[1]
            if candidate_id.lower() == "all":
                count = CandidateActionService.ignore_all_candidates()
                return FeishuCommandResult(success=True, message=f"🚫 已批量忽略\n\n忽略数量: {count}", command=FeishuCommandType.CANDIDATE)
            if CandidateActionService.ignore_candidate(candidate_id):
                return FeishuCommandResult(success=True, message=f"🚫 已忽略\n\n候选: {candidate_id}", command=FeishuCommandType.CANDIDATE)
            return FeishuCommandResult(success=False, message=f"候选不存在: {candidate_id}", command=FeishuCommandType.CANDIDATE)

        if subcommand == "ignore_all":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，批量忽略候选需要 operator 权限", command=FeishuCommandType.CANDIDATE)
            count = CandidateActionService.ignore_all_candidates()
            return FeishuCommandResult(success=True, message=f"🚫 已批量忽略所有待处理候选\n\n忽略数量: {count}", command=FeishuCommandType.CANDIDATE)

        if subcommand == "later":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，标记稍后读需要 operator 权限", command=FeishuCommandType.CANDIDATE)
            if len(args) < 2:
                return FeishuCommandResult(success=False, message="请提供候选 ID", command=FeishuCommandType.CANDIDATE)
            candidate_id = args[1]
            if CandidateActionService.read_later_candidate(candidate_id):
                return FeishuCommandResult(success=True, message=f"📌 已标记稍后阅读\n\n候选: {candidate_id}", command=FeishuCommandType.CANDIDATE)
            return FeishuCommandResult(success=False, message=f"候选不存在: {candidate_id}", command=FeishuCommandType.CANDIDATE)

        return FeishuCommandResult(
            success=False,
            message=f"未知候选子命令: {subcommand}\n可用: list / save / ignore / ignore_all / later",
            command=FeishuCommandType.CANDIDATE,
        )

    async def _handle_knowledge(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.action_service import KnowledgeActionService, PermissionService

        if not args:
            items = KnowledgeActionService.list_knowledge(limit=10)
            if not items:
                return FeishuCommandResult(success=True, message="📚 知识库为空", command=FeishuCommandType.KNOWLEDGE)
            lines = ["📚 知识库（最近10条）\n"]
            for i, item in enumerate(items, 1):
                lines.append(f"{i}. {item.title}")
                lines.append(f"   ID: {item.id}")
                if item.summary:
                    lines.append(f"   摘要: {item.summary[:80]}...")
                lines.append("")
            return FeishuCommandResult(success=True, message="\n".join(lines), command=FeishuCommandType.KNOWLEDGE)

        subcommand = args[0].lower()
        if subcommand == "list":
            return await self._handle_knowledge([])

        if subcommand == "search":
            if len(args) < 2:
                return FeishuCommandResult(success=False, message="请提供搜索关键词", command=FeishuCommandType.KNOWLEDGE)
            keyword = " ".join(args[1:])
            items = KnowledgeActionService.search_knowledge(keyword, limit=10)
            if not items:
                return FeishuCommandResult(success=True, message=f"🔍 未找到与 '{keyword}' 相关的知识", command=FeishuCommandType.KNOWLEDGE)
            lines = [f"🔍 搜索结果: {keyword}\n"]
            for i, item in enumerate(items, 1):
                lines.append(f"{i}. {item.title}")
                lines.append(f"   ID: {item.id}")
                if item.summary:
                    lines.append(f"   摘要: {item.summary[:80]}...")
                lines.append("")
            return FeishuCommandResult(success=True, message="\n".join(lines), command=FeishuCommandType.KNOWLEDGE)

        if subcommand == "delete":
            if not PermissionService.check_permission(self._current_sender_id, "admin"):
                return FeishuCommandResult(success=False, message="权限不足，删除知识需要 admin 权限", command=FeishuCommandType.KNOWLEDGE)
            if len(args) < 2:
                return FeishuCommandResult(success=False, message="请提供知识 ID", command=FeishuCommandType.KNOWLEDGE)
            knowledge_id = args[1]
            from omka.app.services.action_service import ActionService
            action = ActionService.create_action(
                action_type="knowledge.delete",
                actor_channel="feishu",
                actor_external_id=self._current_sender_id,
                target_type="knowledge",
                target_id=knowledge_id,
                request_text=f"knowledge delete {knowledge_id}",
                params_json={"knowledge_id": knowledge_id},
            )
            message = self._create_pending_confirmation(action.id, "knowledge.delete", {"knowledge_id": knowledge_id})
            return FeishuCommandResult(success=False, message=message, command=FeishuCommandType.KNOWLEDGE)

        return FeishuCommandResult(
            success=False,
            message=f"未知知识子命令: {subcommand}\n可用: list / search / delete",
            command=FeishuCommandType.KNOWLEDGE,
        )

    async def _handle_config(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.action_service import ConfigActionService, PermissionService

        if not args:
            return FeishuCommandResult(
                success=False,
                message="请指定配置子命令: list / get / set",
                command=FeishuCommandType.CONFIG,
            )

        subcommand = args[0].lower()
        if subcommand == "list":
            configs = ConfigActionService.list_config(mask_secrets=True)
            lines = ["⚙️ 配置列表\n"]
            for key, value in sorted(configs.items())[:30]:
                if isinstance(value, str) and len(value) > 50:
                    value = value[:50] + "..."
                lines.append(f"{key}: {value}")
            return FeishuCommandResult(success=True, message="\n".join(lines), command=FeishuCommandType.CONFIG)

        if subcommand == "get":
            if len(args) < 2:
                return FeishuCommandResult(success=False, message="请提供配置键名", command=FeishuCommandType.CONFIG)
            key = args[1]
            if ConfigActionService.is_sensitive(key):
                if not PermissionService.check_permission(self._current_sender_id, "admin"):
                    return FeishuCommandResult(success=False, message="权限不足，查看敏感配置需要 admin 权限", command=FeishuCommandType.CONFIG)
                value = ConfigActionService.get_config(key)
                if value is None:
                    return FeishuCommandResult(success=False, message=f"配置不存在: {key}", command=FeishuCommandType.CONFIG)
                from omka.app.core.settings_service import _mask_value
                masked = _mask_value(str(value))
                return FeishuCommandResult(success=True, message=f"⚙️ {key}\n\n{masked}", command=FeishuCommandType.CONFIG)
            value = ConfigActionService.get_config(key)
            if value is None:
                return FeishuCommandResult(success=False, message=f"配置不存在: {key}", command=FeishuCommandType.CONFIG)
            return FeishuCommandResult(success=True, message=f"⚙️ {key}\n\n{value}", command=FeishuCommandType.CONFIG)

        if subcommand == "set":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，修改配置需要 operator 权限", command=FeishuCommandType.CONFIG)
            if len(args) < 3:
                return FeishuCommandResult(success=False, message="用法: /omka config set <key> <value>", command=FeishuCommandType.CONFIG)
            key = args[1]
            value = " ".join(args[2:])
            success, message = ConfigActionService.set_config(key, value)
            return FeishuCommandResult(success=success, message=message, command=FeishuCommandType.CONFIG)

        return FeishuCommandResult(
            success=False,
            message=f"未知配置子命令: {subcommand}\n可用: list / get / set",
            command=FeishuCommandType.CONFIG,
        )

    async def _handle_push(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.action_service import ConfigActionService, PermissionService, PushService

        if not args:
            today_count = PushService.count_today_events()
            return FeishuCommandResult(
                success=True,
                message=f"📢 推送状态\n\n今日已推送: {today_count} 条\n每日上限: 5 条",
                command=FeishuCommandType.PUSH,
            )

        subcommand = args[0].lower()
        if subcommand == "status":
            return await self._handle_push([])

        if subcommand == "pause":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，暂停推送需要 operator 权限", command=FeishuCommandType.PUSH)
            success, message = ConfigActionService.set_config("feishu_push_digest_enabled", False)
            return FeishuCommandResult(success=success, message="⏸️ 已暂停每日简报推送", command=FeishuCommandType.PUSH)

        if subcommand == "resume":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(success=False, message="权限不足，恢复推送需要 operator 权限", command=FeishuCommandType.PUSH)
            success, message = ConfigActionService.set_config("feishu_push_digest_enabled", True)
            return FeishuCommandResult(success=success, message="▶️ 已恢复每日简报推送", command=FeishuCommandType.PUSH)

        if subcommand == "set":
            if not PermissionService.check_permission(self._current_sender_id, "admin"):
                return FeishuCommandResult(success=False, message="权限不足，修改推送策略需要 admin 权限", command=FeishuCommandType.PUSH)
            if len(args) < 3:
                return FeishuCommandResult(success=False, message="用法: /omka push set <key> <value>\n例如: /omka push set max_per_day 10", command=FeishuCommandType.PUSH)
            key = args[1]
            value = " ".join(args[2:])
            config_key = f"push_{key}"
            success, message = ConfigActionService.set_config(config_key, value)
            return FeishuCommandResult(success=success, message=message, command=FeishuCommandType.PUSH)

        return FeishuCommandResult(
            success=False,
            message=f"未知推送子命令: {subcommand}\n可用: status / pause / resume / set",
            command=FeishuCommandType.PUSH,
        )

    async def _handle_schedule(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.action_service import PermissionService
        from omka.app.services.scheduler_service import get_schedule, update_schedule

        if not args:
            info = get_schedule()
            message = (
                f"📅 定时任务\n\n"
                f"Cron: {info['cron']}\n"
                f"时区: {info['timezone']}\n"
                f"下次运行: {info['next_run_time'] or '未启动'}\n"
                f"状态: {'运行中' if info['running'] else '未启动'}"
            )
            return FeishuCommandResult(success=True, message=message, command=FeishuCommandType.UNKNOWN)

        sub = args[0].lower()
        if sub == "set":
            if not PermissionService.check_permission(self._current_sender_id, "operator"):
                return FeishuCommandResult(
                    success=False,
                    message="权限不足，设置定时任务需要 operator 权限",
                    command=FeishuCommandType.UNKNOWN,
                )
            if len(args) < 2:
                return FeishuCommandResult(
                    success=False,
                    message="请提供定时表达式\n\n可用示例:\n- 每天 9:30\n- 每周一 18:00\n- 0 9 * * *",
                    command=FeishuCommandType.UNKNOWN,
                )
            schedule_text = " ".join(args[1:])
            ok, message = update_schedule(schedule_text)
            return FeishuCommandResult(
                success=ok, message=message, command=FeishuCommandType.UNKNOWN,
            )

        return FeishuCommandResult(
            success=False,
            message=f"未知子命令: {sub}\n可用: set",
            command=FeishuCommandType.UNKNOWN,
        )

    async def _handle_doc(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(
                success=False,
                message="请指定子命令: create 或 digest\n示例: /omka doc create 标题 内容",
                command=FeishuCommandType.DOC,
            )
        sub = args[0].lower()
        if sub == "digest":
            return await self._handle_doc_digest(args[1:])
        elif sub == "create":
            return await self._handle_doc_create(args[1:])
        return FeishuCommandResult(
            success=False,
            message=f"未知子命令: {sub}\n可用: create, digest",
            command=FeishuCommandType.DOC,
        )

    async def _handle_doc_digest(self, _args: list[str]) -> FeishuCommandResult:
        try:
            from omka.app.integrations.feishu.api_service import build_feishu_api_service
            svc = build_feishu_api_service()
            if svc is None:
                return FeishuCommandResult(success=False, message="飞书未配置，无法创建文档", command=FeishuCommandType.DOC)

            with get_session() as session:
                candidates = session.exec(
                    select(CandidateItem)
                    .where(CandidateItem.status == "pending")
                    .order_by(CandidateItem.score.desc())
                    .limit(settings.digest_top_n)
                ).all()

            if not candidates:
                return FeishuCommandResult(success=False, message="暂无待推荐内容，请先运行每日任务", command=FeishuCommandType.DOC)

            from datetime import date
            content = _build_digest_content(str(date.today()), candidates)
            title = f"OMKA 每日简报 — {date.today()}"
            result = await svc.create_document(title, content)
            return FeishuCommandResult(
                success=True,
                message=f"飞书文档已创建\n\n{result['url']}",
                command=FeishuCommandType.DOC,
            )
        except Exception as e:
            logger.error("创建简报文档失败 | error=%s", e)
            return FeishuCommandResult(success=False, message=f"创建文档失败: {e}", command=FeishuCommandType.DOC)

    async def _handle_doc_create(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(success=False, message="请提供文档标题\n示例: /omka doc create 测试文档", command=FeishuCommandType.DOC)
        title = args[0]
        content = " ".join(args[1:]) if len(args) > 1 else ""
        try:
            from omka.app.integrations.feishu.api_service import build_feishu_api_service
            svc = build_feishu_api_service()
            if svc is None:
                return FeishuCommandResult(success=False, message="飞书未配置，无法创建文档", command=FeishuCommandType.DOC)
            result = await svc.create_document(title, content)
            return FeishuCommandResult(
                success=True,
                message=f"云文档已创建\n\n{result['url']}",
                command=FeishuCommandType.DOC,
            )
        except Exception as e:
            logger.error("创建云文档失败 | error=%s", e)
            return FeishuCommandResult(success=False, message=f"创建文档失败: {e}", command=FeishuCommandType.DOC)

    async def _handle_base(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(
                success=False,
                message="请指定子命令: create 或 import\n示例: /omka base import",
                command=FeishuCommandType.BASE,
            )
        sub = args[0].lower()
        if sub == "import":
            return await self._handle_base_import(args[1:])
        elif sub == "create":
            return await self._handle_base_create(args[1:])
        return FeishuCommandResult(
            success=False,
            message=f"未知子命令: {sub}\n可用: create, import",
            command=FeishuCommandType.BASE,
        )

    async def _handle_base_import(self, _args: list[str]) -> FeishuCommandResult:
        try:
            from omka.app.integrations.feishu.api_service import build_feishu_api_service
            svc = build_feishu_api_service()
            if svc is None:
                return FeishuCommandResult(success=False, message="飞书未配置，无法创建多维表格", command=FeishuCommandType.BASE)

            with get_session() as session:
                items = session.exec(select(KnowledgeItem).limit(50)).all()

            if not items:
                return FeishuCommandResult(success=False, message="知识库为空，没有可导入的内容", command=FeishuCommandType.BASE)

            base_result = await svc.create_base("OMKA 知识库")
            app_token = base_result["app_token"]

            fields = [
                {"name": "标题", "type": 1},
                {"name": "摘要", "type": 1},
                {"name": "分数", "type": 2},
                {"name": "来源", "type": 1},
            ]
            table_id = await svc.create_table_with_fields(app_token, "知识条目", fields)

            records = [
                {
                    "标题": item.title or "",
                    "摘要": (item.summary or "")[:500],
                    "分数": int((item.item_metadata.get("score", 0) if item.item_metadata else 0) * 100),
                    "来源": item.url or "",
                }
                for item in items
            ]
            await svc.insert_records(app_token, table_id, records)

            return FeishuCommandResult(
                success=True,
                message=f"多维表格已创建\n\n导入 {len(items)} 条知识条目\n{base_result['url']}",
                command=FeishuCommandType.BASE,
            )
        except Exception as e:
            logger.error("导入知识库到多维表格失败 | error=%s", e)
            return FeishuCommandResult(success=False, message=f"导入失败: {e}", command=FeishuCommandType.BASE)

    async def _handle_base_create(self, args: list[str]) -> FeishuCommandResult:
        name = args[0] if args else "OMKA 数据表"
        try:
            from omka.app.integrations.feishu.api_service import build_feishu_api_service
            svc = build_feishu_api_service()
            if svc is None:
                return FeishuCommandResult(success=False, message="飞书未配置，无法创建多维表格", command=FeishuCommandType.BASE)
            result = await svc.create_base(name)
            return FeishuCommandResult(
                success=True,
                message=f"多维表格已创建\n\n{result['url']}",
                command=FeishuCommandType.BASE,
            )
        except Exception as e:
            logger.error("创建多维表格失败 | error=%s", e)
            return FeishuCommandResult(success=False, message=f"创建失败: {e}", command=FeishuCommandType.BASE)

    async def _handle_sheet(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(
                success=False,
                message="请指定子命令: export\n示例: /omka sheet export candidates",
                command=FeishuCommandType.SHEET,
            )
        sub = args[0].lower()
        if sub == "export":
            return await self._handle_sheet_export(args[1:])
        return FeishuCommandResult(
            success=False,
            message=f"未知子命令: {sub}\n可用: export",
            command=FeishuCommandType.SHEET,
        )

    async def _handle_sheet_export(self, args: list[str]) -> FeishuCommandResult:
        target = args[0].lower() if args else ""
        if target not in ("candidates", "knowledge"):
            return FeishuCommandResult(
                success=False,
                message="请指定导出目标: candidates 或 knowledge\n示例: /omka sheet export candidates",
                command=FeishuCommandType.SHEET,
            )
        try:
            from omka.app.integrations.feishu.api_service import build_feishu_api_service
            svc = build_feishu_api_service()
            if svc is None:
                return FeishuCommandResult(success=False, message="飞书未配置，无法创建电子表格", command=FeishuCommandType.SHEET)

            title = f"OMKA {'候选池' if target == 'candidates' else '知识库'}"
            result = await svc.create_spreadsheet(title)
            token = result["spreadsheet_token"]

            if target == "candidates":
                with get_session() as session:
                    items = session.exec(
                        select(CandidateItem).where(CandidateItem.status == "pending").limit(20)
                    ).all()
                headers = ["标题", "类型", "分数", "来源"]
                rows = [headers] + [
                    [item.title or "", item.item_type or "", str(item.score or 0), item.url or ""]
                    for item in items
                ]
            else:
                with get_session() as session:
                    items = session.exec(select(KnowledgeItem).limit(30)).all()
                headers = ["标题", "摘要", "分数"]
                rows = [headers] + [
                    [item.title or "", (item.summary or "")[:200], str(item.item_metadata.get("score", 0) if item.item_metadata else 0)]
                    for item in items
                ]

            await svc.write_sheet_values(token, f"Sheet1!A1:C{len(rows)}", rows)
            return FeishuCommandResult(
                success=True,
                message=f"电子表格已创建\n\n导出 {len(rows) - 1} 条数据\n{result['url']}",
                command=FeishuCommandType.SHEET,
            )
        except Exception as e:
            logger.error("导出电子表格失败 | error=%s", e)
            return FeishuCommandResult(success=False, message=f"导出失败: {e}", command=FeishuCommandType.SHEET)

    async def _handle_calendar(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(
                success=False,
                message="请指定子命令: list 或 review\n示例: /omka calendar review 9:00",
                command=FeishuCommandType.CALENDAR,
            )
        sub = args[0].lower()
        if sub == "list":
            return await self._handle_calendar_list(args[1:])
        elif sub == "review":
            return await self._handle_calendar_review(args[1:])
        return FeishuCommandResult(
            success=False,
            message=f"未知子命令: {sub}\n可用: list, review",
            command=FeishuCommandType.CALENDAR,
        )

    async def _handle_calendar_list(self, _args: list[str]) -> FeishuCommandResult:
        try:
            from omka.app.integrations.feishu.api_service import build_feishu_api_service
            svc = build_feishu_api_service()
            if svc is None:
                return FeishuCommandResult(success=False, message="飞书未配置", command=FeishuCommandType.CALENDAR)
            calendars = await svc.list_calendars()
            if not calendars:
                return FeishuCommandResult(success=True, message="暂无日历", command=FeishuCommandType.CALENDAR)
            lines = [f"• {c['summary']} ({c['calendar_id'][:20]}...)" for c in calendars[:10]]
            return FeishuCommandResult(
                success=True,
                message="日历列表\n\n" + "\n".join(lines),
                command=FeishuCommandType.CALENDAR,
            )
        except Exception as e:
            logger.error("获取日历列表失败 | error=%s", e)
            return FeishuCommandResult(success=False, message=f"获取失败: {e}", command=FeishuCommandType.CALENDAR)

    async def _handle_calendar_review(self, args: list[str]) -> FeishuCommandResult:
        time_str = args[0] if args else "9:00"
        try:
            from omka.app.integrations.feishu.api_service import build_feishu_api_service
            svc = build_feishu_api_service()
            if svc is None:
                return FeishuCommandResult(success=False, message="飞书未配置", command=FeishuCommandType.CALENDAR)

            calendars = await svc.list_calendars()
            if not calendars:
                return FeishuCommandResult(success=False, message="未找到可用日历", command=FeishuCommandType.CALENDAR)

            cal_id = calendars[0]["calendar_id"]
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            start_ts = int(now.timestamp())
            end_ts = int((now + timedelta(hours=1)).timestamp())

            await svc.create_calendar_event(
                cal_id,
                "OMKA 知识回顾",
                f"每日知识回顾提醒 — {now.strftime('%Y-%m-%d')}",
                start_ts,
                end_ts,
            )
            return FeishuCommandResult(
                success=True,
                message=f"日历事件已创建\n\n时间: {time_str}\n日历: {calendars[0]['summary']}",
                command=FeishuCommandType.CALENDAR,
            )
        except Exception as e:
            logger.error("创建日历事件失败 | error=%s", e)
            return FeishuCommandResult(success=False, message=f"创建失败: {e}", command=FeishuCommandType.CALENDAR)

    async def _handle_task(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(
                success=False,
                message="请指定子命令: add\n示例: /omka task add 阅读 LangGraph 文档",
                command=FeishuCommandType.TASK,
            )
        sub = args[0].lower()
        if sub == "add":
            return await self._handle_task_add(args[1:])
        return FeishuCommandResult(
            success=False,
            message=f"未知子命令: {sub}\n可用: add",
            command=FeishuCommandType.TASK,
        )

    async def _handle_task_add(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(success=False, message="请提供任务内容\n示例: /omka task add 阅读 LangGraph 文档", command=FeishuCommandType.TASK)
        summary = " ".join(args)
        try:
            from omka.app.integrations.feishu.api_service import build_feishu_api_service
            svc = build_feishu_api_service()
            if svc is None:
                return FeishuCommandResult(success=False, message="飞书未配置，无法创建任务", command=FeishuCommandType.TASK)
            await svc.create_task(summary)
            return FeishuCommandResult(
                success=True,
                message=f"飞书任务已创建\n\n{summary}",
                command=FeishuCommandType.TASK,
            )
        except Exception as e:
            logger.error("创建任务失败 | error=%s", e)
            return FeishuCommandResult(success=False, message=f"创建任务失败: {e}", command=FeishuCommandType.TASK)

    async def _handle_assets(self, args: list[str]) -> FeishuCommandResult:
        from omka.app.services.action_service import AssetService

        assets = AssetService.list_assets()
        if not assets:
            return FeishuCommandResult(
                success=True,
                message="📎 资产列表为空",
                command=FeishuCommandType.UNKNOWN,
            )

        lines = ["📎 资产列表\n"]
        for a in assets[:10]:
            lines.append(f"[{a.asset_type}] {a.title}")
            lines.append(f"   ID: {a.id} | 状态: {a.status}")
        return FeishuCommandResult(success=True, message="\n".join(lines), command=FeishuCommandType.UNKNOWN)

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

        if self._current_sender_id not in admin_list:
            return FeishuCommandResult(
                success=False,
                message="权限不足，此命令仅限管理员使用。",
                command=FeishuCommandType.RUN,
            )

        try:
            import asyncio
            from omka.app.services.daily_job import run_daily_job

            asyncio.create_task(run_daily_job())

            return FeishuCommandResult(
                success=True,
                message="正在执行每日任务，请稍候...",
                command=FeishuCommandType.RUN,
            )
        except Exception as e:
            logger.error("触发每日任务失败 | error=%s", e)
            return FeishuCommandResult(
                success=False,
                message=f"触发任务失败: {str(e)}",
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

    async def _handle_confirm(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(success=False, message="请提供确认 ID，例如: /omka confirm 123", command=FeishuCommandType.UNKNOWN)
        try:
            action_id = int(args[0])
        except ValueError:
            return FeishuCommandResult(success=False, message="确认 ID 必须是数字", command=FeishuCommandType.UNKNOWN)

        pending = self._pending_confirmations.pop(action_id, None)
        if not pending:
            return FeishuCommandResult(success=False, message=f"未找到待确认操作: {action_id}\n可能已过期或已处理", command=FeishuCommandType.UNKNOWN)

        if pending.get("sender_id") != self._current_sender_id:
            return FeishuCommandResult(success=False, message="只有操作发起人可以确认此操作", command=FeishuCommandType.UNKNOWN)

        try:
            from omka.app.services.action_service import ActionService
            action_type = pending.get("action_type", "")
            params = pending.get("params", {})

            if action_type == "source.delete":
                from omka.app.services.action_service import SourceActionService
                source_id = params.get("source_id")
                if SourceActionService.delete_source(source_id):
                    ActionService.complete_action(action_id, "success", result_json={"deleted": source_id})
                    return FeishuCommandResult(success=True, message=f"🗑️ 已确认删除\n\n信息源: {source_id}", command=FeishuCommandType.SOURCE)
                return FeishuCommandResult(success=False, message=f"删除失败，信息源可能已不存在: {source_id}", command=FeishuCommandType.SOURCE)

            if action_type == "knowledge.delete":
                from omka.app.services.action_service import KnowledgeActionService
                knowledge_id = params.get("knowledge_id")
                if KnowledgeActionService.delete_knowledge(knowledge_id):
                    ActionService.complete_action(action_id, "success", result_json={"deleted": knowledge_id})
                    return FeishuCommandResult(success=True, message=f"🗑️ 已确认删除\n\n知识条目: {knowledge_id}", command=FeishuCommandType.KNOWLEDGE)
                return FeishuCommandResult(success=False, message=f"删除失败，知识条目可能已不存在: {knowledge_id}", command=FeishuCommandType.KNOWLEDGE)

            if action_type == "memory.delete":
                from omka.app.services.memory_service import MemoryService
                memory_id = params.get("memory_id")
                if MemoryService.delete_memory(memory_id):
                    ActionService.complete_action(action_id, "success", result_json={"deleted": memory_id})
                    return FeishuCommandResult(success=True, message=f"🗑️ 已确认删除\n\n记忆: {memory_id}", command=FeishuCommandType.UNKNOWN)
                return FeishuCommandResult(success=False, message=f"删除失败，记忆可能已不存在: {memory_id}", command=FeishuCommandType.UNKNOWN)

            ActionService.complete_action(action_id, "failed", error_message="未知操作类型")
            return FeishuCommandResult(success=False, message=f"未知操作类型: {action_type}", command=FeishuCommandType.UNKNOWN)
        except Exception as e:
            logger.error("确认操作失败 | error=%s", e)
            return FeishuCommandResult(success=False, message=f"确认操作失败: {str(e)}", command=FeishuCommandType.UNKNOWN)

    async def _handle_cancel(self, args: list[str]) -> FeishuCommandResult:
        if not args:
            return FeishuCommandResult(success=False, message="请提供操作 ID，例如: /omka cancel 123", command=FeishuCommandType.UNKNOWN)
        try:
            action_id = int(args[0])
        except ValueError:
            return FeishuCommandResult(success=False, message="操作 ID 必须是数字", command=FeishuCommandType.UNKNOWN)

        pending = self._pending_confirmations.pop(action_id, None)
        if not pending:
            return FeishuCommandResult(success=False, message=f"未找到待取消操作: {action_id}", command=FeishuCommandType.UNKNOWN)

        from omka.app.services.action_service import ActionService
        ActionService.complete_action(action_id, "cancelled")
        return FeishuCommandResult(success=True, message=f"❌ 已取消操作 #{action_id}", command=FeishuCommandType.UNKNOWN)

    def _create_pending_confirmation(self, action_id: int, action_type: str, params: dict) -> str:
        self._pending_confirmations[action_id] = {
            "sender_id": self._current_sender_id,
            "action_type": action_type,
            "params": params,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return (
            f"⚠️ 这是一个高危操作，需要二次确认。\n\n"
            f"操作: {action_type}\n"
            f"操作 ID: {action_id}\n\n"
            f"请回复以下命令继续执行:\n"
            f"/omka confirm {action_id}\n\n"
            f"或回复以下命令取消:\n"
            f"/omka cancel {action_id}"
        )


def _build_digest_content(date_str: str, candidates) -> str:
    lines = [
        f"# 今日 GitHub 知识简报 | {date_str}",
        "",
        f"> 共 {len(candidates)} 条推荐内容",
        "",
        "---",
        "",
    ]
    for i, c in enumerate(candidates, 1):
        score = c.score or 0
        detail = c.score_detail or {}
        lines.append(f"## {i}. {c.title}")
        lines.append("")
        if c.summary:
            lines.append(c.summary)
            lines.append("")
        lines.append(f"**评分**: {score:.2f}")
        lines.append("")
        lines.append("> 评分详情:")
        for key, label in [
            ("interest_score", "兴趣匹配"),
            ("project_score", "项目相关"),
            ("freshness_score", "新鲜度"),
            ("popularity_score", "热度"),
            ("source_quality_score", "源头质量"),
        ]:
            val = detail.get(key, 0)
            lines.append(f"> - {label} {val:.2f}")
        lines.append("")
        lines.append(f"- **链接**: {c.url}")
        lines.append(f"- **类型**: {c.item_type}")
        if c.matched_interests:
            lines.append(f"- **相关兴趣**: {', '.join(c.matched_interests)}")
        if c.matched_projects:
            lines.append(f"- **相关项目**: {', '.join(c.matched_projects)}")
        if c.recommendation_reason:
            lines.append(f"- **推荐理由**: {c.recommendation_reason}")
        lines.append("")
    return "\n".join(lines)
