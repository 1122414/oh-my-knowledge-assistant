"""Natural language understanding service."""

import json
from typing import Any

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.pipeline.summarizer import LLMClient


# 可用命令定义，用于 few-shot prompt
AVAILABLE_COMMANDS = """
可用命令列表：

基础命令：
- help — 显示帮助信息
- bind — 绑定当前会话
- status — 查看系统状态
- latest — 获取最新简报
- run — 手动触发更新

信息源管理：
- source.list — 查看所有信息源
- source.add.repo <owner/repo> — 添加仓库源
- source.add.search <关键词> [limit <数量>] — 添加搜索源
- source.delete <source_id> — 删除信息源
- source.disable <source_id> — 停用信息源
- source.enable <source_id> — 启用信息源
- source.run <source_id> — 立即运行信息源

候选池管理：
 - candidate.list — 查看候选列表
 - candidate.save <candidate_id> — 确认入库
 - candidate.ignore <candidate_id> — 忽略候选
 - candidate.ignore_all — 忽略所有待处理候选
 - candidate.later <candidate_id> — 稍后阅读

知识库管理：
- knowledge.list — 查看知识库
- knowledge.search <关键词> — 搜索知识库
- knowledge.delete <knowledge_id> — 删除知识条目

配置管理：
- config.list — 查看配置列表
- config.get <key> — 获取配置值
- config.set <key> <value> — 设置配置值

推送管理：
 - push.status — 查看推送状态
 - push.pause — 暂停推送
 - push.resume — 恢复推送

定时任务管理：
 - schedule.get — 查看定时任务
 - schedule.set <schedule_text> — 设置定时任务

记忆管理：
- memory.list — 查看记忆列表
- memory.profile — 查看记忆统计
- memory.add <内容> — 添加用户记忆
- memory.confirm <记忆ID> — 确认候选记忆
- memory.reject <记忆ID> — 拒绝候选记忆
- memory.delete <记忆ID> — 删除记忆

飞书云文档：
- doc.create <标题> [内容] — 创建飞书云文档
- doc.digest — 将最新简报保存为飞书文档

飞书多维表格：
- base.import — 将知识库导入多维表格
- base.create <名称> — 创建多维表格

飞书电子表格：
- sheet.export.candidates — 候选池导出为表格
- sheet.export.knowledge — 知识库导出为表格

飞书日历：
- calendar.list — 查看日历列表
- calendar.review <时间> — 创建知识回顾日历事件

飞书任务：
- task.add <内容> — 添加飞书任务
"""

FEW_SHOT_EXAMPLES = """
示例：

用户：帮我看一下系统状态
输出：{"command": "status", "args": [], "confidence": 0.98}

用户：添加一个来源搜索 langchain
输出：{"command": "source.add.search", "args": ["langchain"], "confidence": 0.97}

用户：把候选池里第一个入库
输出：{"command": "candidate.save", "args": ["first"], "confidence": 0.85}

用户：查看所有信息源
输出：{"command": "source.list", "args": [], "confidence": 0.99}

用户：暂停每日推送
输出：{"command": "push.pause", "args": [], "confidence": 0.96}

用户：搜索一下 knowledge base 里的 agent 相关内容
输出：{"command": "knowledge.search", "args": ["agent"], "confidence": 0.94}

用户：帮我添加一个仓库 facebook/react
输出：{"command": "source.add.repo", "args": ["facebook/react"], "confidence": 0.97}

用户：查看记忆统计
输出：{"command": "memory.profile", "args": [], "confidence": 0.98}

用户：我不感兴趣第三个候选
输出：{"command": "candidate.ignore", "args": ["3"], "confidence": 0.88}

用户：删除所有候选内容
输出：{"command": "candidate.ignore_all", "args": [], "confidence": 0.95}

用户：把所有候选都忽略掉
输出：{"command": "candidate.ignore_all", "args": [], "confidence": 0.96}

用户：以后每天早上9点自动跑
输出：{"command": "schedule.set", "args": ["每天9点"], "confidence": 0.96}

用户：把知识抓取改成每周一 18:00
输出：{"command": "schedule.set", "args": ["每周一 18:00"], "confidence": 0.94}

用户：现在定时任务是什么时候
输出：{"command": "schedule.get", "args": [], "confidence": 0.95}

用户：把最新简报保存为飞书文档
输出：{"command": "doc.digest", "args": [], "confidence": 0.95}

用户：创建一个云文档叫今日知识回顾
输出：{"command": "doc.create", "args": ["今日知识回顾"], "confidence": 0.94}

用户：把知识库导入飞书多维表格
输出：{"command": "base.import", "args": [], "confidence": 0.97}

用户：把候选池导出为电子表格
输出：{"command": "sheet.export.candidates", "args": [], "confidence": 0.96}

用户：查看飞书日历
输出：{"command": "calendar.list", "args": [], "confidence": 0.98}

用户：创建一个明天9点的知识回顾日历
输出：{"command": "calendar.review", "args": ["9:00"], "confidence": 0.94}

用户：添加一个飞书任务阅读 LangGraph 文档
输出：{"command": "task.add", "args": ["阅读 LangGraph 文档"], "confidence": 0.95}
"""


class NLUService:
    """自然语言理解服务：将自然语言转化为结构化命令"""

    def __init__(self) -> None:
        self._llm = LLMClient()

    async def parse(self, text: str) -> dict[str, Any] | None:
        """解析自然语言，返回结构化命令

        Returns:
            {"command": "source.add.search", "args": ["remotion"], "confidence": 0.95}
            或 None（如果无法理解）
        """
        if not text or len(text.strip()) < 2:
            return None

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是一个命令解析助手。将用户的自然语言转化为结构化的系统命令。\n\n"
                        f"{AVAILABLE_COMMANDS}\n\n"
                        f"{FEW_SHOT_EXAMPLES}\n\n"
                        "规则：\n"
                        "1. 只输出 JSON 格式，不要有任何其他文字\n"
                        "2. command 必须是可用命令之一，使用点号分隔（如 source.add.search）\n"
                        "3. args 是命令参数列表，可以是空列表\n"
                        "4. confidence 是置信度（0-1），低于 0.7 的命令不可信\n"
                        "5. 如果无法匹配任何命令，输出 null\n"
                        "6. 不要假设参数，如果用户没有提供，args 为空"
                    ),
                },
                {
                    "role": "user",
                    "content": f"用户：{text.strip()}",
                },
            ]

            response = await self._llm.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=256,
            )

            result = self._parse_response(response)
            if result and result.get("confidence", 0) >= 0.7:
                logger.info(
                    "NLU 解析成功 | text=%s | command=%s | confidence=%.2f",
                    text[:50],
                    result["command"],
                    result["confidence"],
                )
                return result
            else:
                logger.debug(
                    "NLU 解析置信度不足 | text=%s | result=%s",
                    text[:50],
                    result,
                )
                return None

        except Exception as e:
            logger.error("NLU 解析失败 | text=%s | error=%s", text[:50], e)
            return None

    def _parse_response(self, response: str) -> dict[str, Any] | None:
        """解析 LLM 返回的 JSON"""
        try:
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            if text.lower() in ("null", "none", ""):
                return None

            data = json.loads(text)
            if not isinstance(data, dict):
                return None

            command = data.get("command", "")
            if not command or not isinstance(command, str):
                return None

            args = data.get("args", [])
            if not isinstance(args, list):
                args = [str(args)]

            confidence = float(data.get("confidence", 0))

            return {
                "command": command,
                "args": [str(a) for a in args],
                "confidence": min(max(confidence, 0.0), 1.0),
            }
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.debug("NLU 响应解析失败 | response=%s | error=%s", response[:100], e)
            return None
