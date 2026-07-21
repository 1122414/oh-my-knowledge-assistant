"""Deterministic task understanding for the Agent runtime.

The module deliberately exposes a small interface so a model-backed interpreter can
replace or refine the heuristic implementation later without changing the runtime.
"""

from __future__ import annotations

import re
from typing import Literal, Protocol

from pydantic import BaseModel, Field

TaskIntent = Literal[
    "retrieve",
    "compare",
    "summarize",
    "organize",
    "monitor",
    "act",
    "configure",
    "converse",
]
ContextSource = Literal[
    "conversation",
    "digest",
    "knowledge",
    "candidate",
    "memory",
    "profile",
]
RiskLevel = Literal["safe", "sensitive", "destructive"]
OutputShape = Literal[
    "answer",
    "list",
    "summary",
    "comparison",
    "action_result",
]


class TaskBrief(BaseModel):
    """A user-visible contract describing what the Agent believes the task is."""

    intent: TaskIntent
    goal: str = Field(min_length=1, max_length=500)
    entities: list[str] = Field(default_factory=list, max_length=8)
    constraints: list[str] = Field(default_factory=list, max_length=8)
    required_context: list[ContextSource] = Field(default_factory=list)
    expected_output: OutputShape = "answer"
    risk: RiskLevel = "safe"
    confidence: float = Field(ge=0, le=1)
    needs_clarification: bool = False
    clarification_question: str | None = None
    success_criteria: list[str] = Field(default_factory=list, max_length=6)

    def to_prompt(self) -> str:
        return self.model_dump_json(exclude_none=True)


class TaskInterpreter(Protocol):
    """Seam used by the runtime and the offline Harness."""

    def interpret(self, message: str) -> TaskBrief:
        ...


class HeuristicTaskInterpreter:
    """Fast, auditable baseline for task intent and execution constraints."""

    _INTENT_SIGNALS: tuple[tuple[TaskIntent, tuple[str, ...]], ...] = (
        (
            "configure",
            ("设置", "配置", "启用", "关闭", "开关", "改成", "以后回答", "记住"),
        ),
        ("monitor", ("持续", "每天", "每日", "定时", "跟踪", "监控", "长期关注")),
        ("compare", ("对比", "比较", "区别", "差异", "选哪个", "更适合")),
        ("summarize", ("总结", "摘要", "概括", "简报", "提炼", "归纳")),
        ("organize", ("整理", "分类", "归档", "去重", "建立目录")),
        (
            "act",
            (
                "创建",
                "新增",
                "删除",
                "确认",
                "拒绝",
                "推送",
                "发送",
                "执行",
                "运行",
                "收藏",
                "导入",
                "更新",
            ),
        ),
        (
            "retrieve",
            (
                "查找",
                "查一下",
                "查看",
                "说明",
                "列出",
                "多少",
                "搜索",
                "找出",
                "找一下",
                "帮我找",
                "推荐",
                "有哪些",
                "是什么",
                "收藏过",
                "值得",
                "今天",
                "最新",
            ),
        ),
    )
    _DESTRUCTIVE = ("删除", "清空", "移除", "拒绝", "停用", "取消订阅", "覆盖")
    _SENSITIVE = (
        "创建",
        "新增",
        "修改",
        "更新",
        "发送",
        "推送",
        "确认",
        "执行",
        "运行",
        "导入",
        "启用",
        "关闭",
        "配置",
        "每天",
        "每日",
        "定时",
        "持续",
    )
    _VAGUE_ACTIONS = (
        "帮我处理",
        "处理一下",
        "弄一下",
        "搞一下",
        "执行一下",
        "删除一下",
        "改一下",
    )

    def interpret(self, message: str) -> TaskBrief:
        text = " ".join(message.strip().split())
        lowered = text.lower()
        intent, signal_count = self._detect_intent(lowered)
        required_context = self._required_context(lowered, intent)
        expected_output = self._expected_output(lowered, intent)
        risk = self._risk(lowered)
        entities = self._entities(text)
        constraints = self._constraints(text)
        needs_clarification = self._needs_clarification(
            text=text,
            intent=intent,
            risk=risk,
            entities=entities,
        )
        confidence = self._confidence(
            text=text,
            signal_count=signal_count,
            required_context=required_context,
            needs_clarification=needs_clarification,
        )
        return TaskBrief(
            intent=intent,
            goal=self._goal(text),
            entities=entities,
            constraints=constraints,
            required_context=required_context,
            expected_output=expected_output,
            risk=risk,
            confidence=confidence,
            needs_clarification=needs_clarification,
            clarification_question=(
                self._clarification_question(intent, risk)
                if needs_clarification
                else None
            ),
            success_criteria=self._success_criteria(
                intent=intent,
                expected_output=expected_output,
                required_context=required_context,
                risk=risk,
            ),
        )

    @classmethod
    def _detect_intent(cls, text: str) -> tuple[TaskIntent, int]:
        if text in {"你好", "嗨", "hello", "hi", "在吗"}:
            return "converse", 1
        if any(signal in text for signal in ("收藏过", "我收藏的", "保存过")):
            return "retrieve", 1
        for intent, signals in cls._INTENT_SIGNALS:
            matches = sum(1 for signal in signals if signal in text)
            if matches:
                return intent, matches
        return "converse", 0

    @staticmethod
    def _required_context(text: str, intent: TaskIntent) -> list[ContextSource]:
        sources: list[ContextSource] = []

        def add(source: ContextSource) -> None:
            if source not in sources:
                sources.append(source)

        if any(term in text for term in ("今天", "最新", "简报", "日报", "本周")):
            add("digest")
        if any(term in text for term in ("知识库", "知识", "收藏", "保存过")):
            add("knowledge")
        if any(term in text for term in ("候选", "推荐", "值得", "项目", "仓库")):
            add("candidate")
        if any(
            term in text
            for term in ("查找", "查一下", "搜索", "找出", "找一下", "帮我找")
        ):
            add("knowledge")
            add("candidate")
        if any(
            term in text
            for term in (
                "记忆",
                "记得",
                "记住",
                "偏好",
                "兴趣",
                "喜欢",
                "不喜欢",
                "适合我",
            )
        ):
            add("memory")
            add("profile")
        if any(term in text for term in ("刚才", "上次", "继续", "这个", "那个")):
            add("conversation")

        if not sources:
            if intent in {"retrieve", "compare", "summarize", "organize"}:
                sources.extend(["knowledge", "candidate", "digest"])
            elif intent in {"act", "configure", "monitor"}:
                sources.extend(["conversation", "profile"])
            else:
                sources.extend(["conversation", "memory", "profile"])
        return sources

    @staticmethod
    def _expected_output(text: str, intent: TaskIntent) -> OutputShape:
        if intent == "compare":
            return "comparison"
        if intent == "summarize":
            return "summary"
        if intent in {"act", "configure", "monitor", "organize"}:
            return "action_result"
        if any(term in text for term in ("几个", "哪些", "列表", "推荐", "三个", "五个")):
            return "list"
        return "answer"

    @classmethod
    def _risk(cls, text: str) -> RiskLevel:
        if any(signal in text for signal in cls._DESTRUCTIVE):
            return "destructive"
        if any(signal in text for signal in cls._SENSITIVE):
            return "sensitive"
        return "safe"

    @staticmethod
    def _entities(text: str) -> list[str]:
        entities: list[str] = []
        for match in re.findall(r"[“\"《](.*?)[”\"》]", text):
            value = match.strip()
            if value and value not in entities:
                entities.append(value)
        for match in re.findall(
            r"(?i)\b(?:github|python|react|fastapi|rust|go|llm|rag|agent|omka)\b",
            text,
        ):
            value = match.strip()
            if value and value.lower() not in {item.lower() for item in entities}:
                entities.append(value)
        for match in re.findall(r"(?:关于|针对|查找|搜索|关注)([^，。！？,!?]{2,24})", text):
            value = re.split(r"(?:的|并|然后|，|。)", match.strip())[0].strip()
            if value and value not in entities:
                entities.append(value)
        return entities[:8]

    @staticmethod
    def _constraints(text: str) -> list[str]:
        constraints: list[str] = []
        patterns = (
            r"(?:前|最近)?[一二三四五六七八九十\d]+(?:个|条|项|篇|天|周)",
            r"(?:今天|明天|本周|本月|每天|每日|定时)",
            r"(?:不要|只要|必须|仅|优先)[^，。！？,!?]{1,30}",
        )
        for pattern in patterns:
            for match in re.findall(pattern, text):
                value = match.strip()
                if value and value not in constraints:
                    constraints.append(value)
        return constraints[:8]

    @classmethod
    def _needs_clarification(
        cls,
        *,
        text: str,
        intent: TaskIntent,
        risk: RiskLevel,
        entities: list[str],
    ) -> bool:
        if not text:
            return True
        if intent == "converse":
            return len(text) > 2 and any(phrase in text for phrase in cls._VAGUE_ACTIONS)
        if any(phrase in text for phrase in cls._VAGUE_ACTIONS) and len(text) < 16:
            return True
        if risk == "destructive" and not entities and len(text) < 12:
            return True
        return False

    @staticmethod
    def _confidence(
        *,
        text: str,
        signal_count: int,
        required_context: list[ContextSource],
        needs_clarification: bool,
    ) -> float:
        score = 0.54
        if signal_count:
            score += min(0.2, signal_count * 0.08)
        if required_context:
            score += 0.08
        if len(text) >= 10:
            score += 0.08
        if needs_clarification:
            score -= 0.28
        return round(max(0.15, min(score, 0.96)), 2)

    @staticmethod
    def _goal(text: str) -> str:
        return text.rstrip("。！？!?") or "明确用户希望完成的任务"

    @staticmethod
    def _clarification_question(
        intent: TaskIntent,
        risk: RiskLevel,
    ) -> str:
        if risk == "destructive":
            return "请明确要操作的对象和范围；我会在执行不可逆操作前再次请求确认。"
        if intent in {"act", "configure", "organize"}:
            return "你希望我具体处理什么对象，以及完成后要得到什么结果？"
        return "你希望我解决的具体问题和期望结果是什么？"

    @staticmethod
    def _success_criteria(
        *,
        intent: TaskIntent,
        expected_output: OutputShape,
        required_context: list[ContextSource],
        risk: RiskLevel,
    ) -> list[str]:
        criteria = ["回答直接对应用户目标，不补造事实"]
        if required_context:
            criteria.append("优先使用指定知识来源，并保留可追溯依据")
        if expected_output == "list":
            criteria.append("结果按相关性排序并说明选择理由")
        elif expected_output == "comparison":
            criteria.append("使用一致维度比较，并明确适用条件")
        elif expected_output == "summary":
            criteria.append("保留关键结论、变化和下一步")
        elif expected_output == "action_result":
            criteria.append("明确说明已执行、待确认或未执行的动作")
        if intent == "monitor":
            criteria.append("说明触发条件、频率和交付方式")
        if risk != "safe":
            criteria.append("任何有副作用的动作都受权限与确认策略约束")
        return criteria[:6]
