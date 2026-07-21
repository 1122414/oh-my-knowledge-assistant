"""Offline regression scenarios and recent-run quality metrics for the Agent."""

from __future__ import annotations

import math
import re
from datetime import datetime

from pydantic import BaseModel, Field
from sqlmodel import col, select

from omka.app.agents.task_understanding import HeuristicTaskInterpreter
from omka.app.storage.db import AgentRun, AgentStep, get_session

_CITATION_PATTERN = re.compile(r"\[(knowledge|candidate|memory):[^\]]+\]")


class HarnessScenarioResult(BaseModel):
    name: str
    passed: bool
    findings: list[str] = Field(default_factory=list)


class AgentHarnessSummary(BaseModel):
    health_score: float = Field(ge=0, le=1)
    sample_size: int
    scenario_count: int
    scenario_pass_rate: float = Field(ge=0, le=1)
    completion_rate: float = Field(ge=0, le=1)
    trace_coverage: float = Field(ge=0, le=1)
    understanding_coverage: float = Field(ge=0, le=1)
    grounding_rate: float = Field(ge=0, le=1)
    degraded_rate: float = Field(ge=0, le=1)
    p50_latency_ms: int
    p95_latency_ms: int
    findings: list[str]
    scenario_results: list[HarnessScenarioResult]
    generated_at: datetime


class AgentHarness:
    """Quality Harness covering both deterministic intent and persisted runs."""

    SCENARIOS = (
        {
            "name": "latest_digest",
            "message": "总结今天最值得关注的三个项目",
            "intent": "summarize",
            "context": {"digest", "candidate"},
            "output": "summary",
            "risk": "safe",
        },
        {
            "name": "knowledge_recall",
            "message": "查找我收藏过的 RAG 知识",
            "intent": "retrieve",
            "context": {"knowledge"},
            "risk": "safe",
        },
        {
            "name": "profile_aware_recommendation",
            "message": "根据我的兴趣推荐五个候选项目",
            "intent": "retrieve",
            "context": {"candidate", "memory", "profile"},
            "output": "list",
        },
        {
            "name": "safe_comparison",
            "message": "比较 FastAPI 和 Go 在这个项目里的适用场景",
            "intent": "compare",
            "context": {"conversation"},
            "output": "comparison",
        },
        {
            "name": "destructive_clarification",
            "message": "删除一下",
            "intent": "act",
            "risk": "destructive",
            "clarify": True,
        },
        {
            "name": "scheduled_monitor",
            "message": "每天跟踪 Agent 领域的新项目并生成简报",
            "intent": "monitor",
            "context": {"digest", "candidate"},
            "risk": "sensitive",
        },
        {
            "name": "current_inventory",
            "message": "说明当前知识库、候选内容和记忆分别有多少条信息",
            "intent": "retrieve",
            "context": {"knowledge", "candidate", "memory"},
            "risk": "safe",
        },
        {
            "name": "explicit_push_action",
            "message": "找出今天关于 Browser Agent 的信息并推送到飞书",
            "intent": "act",
            "context": {"digest", "candidate"},
            "output": "action_result",
            "risk": "sensitive",
        },
        {
            "name": "preference_update",
            "message": "记住以后回答先给结论，再给三条依据",
            "intent": "configure",
            "context": {"memory", "profile"},
            "risk": "safe",
        },
        {
            "name": "small_talk",
            "message": "你好",
            "intent": "converse",
            "clarify": False,
        },
    )

    def __init__(self) -> None:
        self._interpreter = HeuristicTaskInterpreter()

    def summarize(self, limit: int = 50) -> AgentHarnessSummary:
        scenarios = self._run_scenarios()
        with get_session() as session:
            runs = list(
                session.exec(
                    select(AgentRun)
                    .order_by(col(AgentRun.created_at).desc())
                    .limit(min(max(limit, 1), 200))
                ).all()
            )
            run_ids = [run.id for run in runs if run.id is not None]
            steps = (
                list(
                    session.exec(
                        select(AgentStep)
                        .where(AgentStep.run_id.in_(run_ids))
                        .order_by(col(AgentStep.run_id), col(AgentStep.step_index))
                    ).all()
                )
                if run_ids
                else []
            )

        by_run: dict[int, list[AgentStep]] = {}
        for step in steps:
            by_run.setdefault(step.run_id, []).append(step)

        sample_size = len(runs)
        completion_rate = self._ratio(
            sum(run.status in {"success", "completed", "needs_confirm"} for run in runs),
            sample_size,
        )
        degraded_rate = self._ratio(
            sum(run.status in {"degraded", "step_limit", "failed", "error"} for run in runs),
            sample_size,
        )
        understanding_coverage = self._ratio(
            sum(bool(run.used_context_json.get("task_brief")) for run in runs),
            sample_size,
        )
        traced = 0
        grounded_eligible = 0
        grounded = 0
        for run in runs:
            run_steps = by_run.get(run.id or -1, [])
            stages = {step.tool_name for step in run_steps}
            has_final = any(step.step_type == "final" for step in run_steps)
            if {"understanding.task", "context.assemble", "planner.decide"}.issubset(
                stages
            ) and has_final:
                traced += 1
            if run.used_context_json.get("used"):
                grounded_eligible += 1
                answer = self._final_answer(run_steps, run.answer_preview)
                if _CITATION_PATTERN.search(answer):
                    grounded += 1

        trace_coverage = self._ratio(traced, sample_size)
        grounding_rate = self._ratio(grounded, grounded_eligible)
        scenario_pass_rate = self._ratio(
            sum(result.passed for result in scenarios),
            len(scenarios),
        )
        latencies = sorted(run.latency_ms for run in runs if run.latency_ms >= 0)
        p50 = self._percentile(latencies, 0.5)
        p95 = self._percentile(latencies, 0.95)
        health_score = round(
            scenario_pass_rate * 0.30
            + completion_rate * 0.25
            + trace_coverage * 0.20
            + understanding_coverage * 0.15
            + grounding_rate * 0.10,
            3,
        )
        findings = self._findings(
            sample_size=sample_size,
            scenario_pass_rate=scenario_pass_rate,
            completion_rate=completion_rate,
            trace_coverage=trace_coverage,
            understanding_coverage=understanding_coverage,
            grounding_rate=grounding_rate,
            degraded_rate=degraded_rate,
            p95=p95,
        )
        return AgentHarnessSummary(
            health_score=health_score,
            sample_size=sample_size,
            scenario_count=len(scenarios),
            scenario_pass_rate=scenario_pass_rate,
            completion_rate=completion_rate,
            trace_coverage=trace_coverage,
            understanding_coverage=understanding_coverage,
            grounding_rate=grounding_rate,
            degraded_rate=degraded_rate,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            findings=findings,
            scenario_results=scenarios,
            generated_at=datetime.utcnow(),
        )

    def _run_scenarios(self) -> list[HarnessScenarioResult]:
        results: list[HarnessScenarioResult] = []
        for scenario in self.SCENARIOS:
            brief = self._interpreter.interpret(str(scenario["message"]))
            findings: list[str] = []
            if brief.intent != scenario["intent"]:
                findings.append(
                    f"intent: expected {scenario['intent']}, got {brief.intent}"
                )
            expected_context = scenario.get("context")
            if isinstance(expected_context, set):
                missing = expected_context - set(brief.required_context)
                if missing:
                    findings.append(f"context missing: {', '.join(sorted(missing))}")
            for field in ("output", "risk"):
                expected = scenario.get(field)
                actual = (
                    brief.expected_output if field == "output" else brief.risk
                )
                if expected is not None and actual != expected:
                    findings.append(f"{field}: expected {expected}, got {actual}")
            expected_clarify = scenario.get("clarify")
            if (
                expected_clarify is not None
                and brief.needs_clarification is not expected_clarify
            ):
                findings.append(
                    "clarify: expected "
                    f"{expected_clarify}, got {brief.needs_clarification}"
                )
            results.append(
                HarnessScenarioResult(
                    name=str(scenario["name"]),
                    passed=not findings,
                    findings=findings,
                )
            )
        return results

    @staticmethod
    def _final_answer(steps: list[AgentStep], fallback: str) -> str:
        for step in reversed(steps):
            if step.step_type == "final":
                answer = step.output_json.get("answer")
                if isinstance(answer, str):
                    return answer
        return fallback

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float:
        if denominator == 0:
            return 1.0
        return round(numerator / denominator, 3)

    @staticmethod
    def _percentile(values: list[int], percentile: float) -> int:
        if not values:
            return 0
        index = max(0, math.ceil(len(values) * percentile) - 1)
        return values[index]

    @staticmethod
    def _findings(
        *,
        sample_size: int,
        scenario_pass_rate: float,
        completion_rate: float,
        trace_coverage: float,
        understanding_coverage: float,
        grounding_rate: float,
        degraded_rate: float,
        p95: int,
    ) -> list[str]:
        findings: list[str] = []
        if scenario_pass_rate < 1:
            findings.append("任务理解回归场景存在失败，需要先修复意图或来源识别。")
        if sample_size == 0:
            findings.append("暂无真实运行样本；先完成几次代表性任务以建立运行基线。")
        if completion_rate < 0.85:
            findings.append("近期完整完成率低于 85%，优先检查模型连接与工具失败。")
        if trace_coverage < 0.9:
            findings.append("部分运行缺少完整理解、上下文、规划或最终响应轨迹。")
        if understanding_coverage < 0.9:
            findings.append("历史运行尚未全部使用结构化任务契约。")
        if grounding_rate < 0.8:
            findings.append("使用知识上下文的回答中，可追溯引用覆盖仍需提高。")
        if degraded_rate > 0.15:
            findings.append("降级或失败运行超过 15%，需要增强恢复策略。")
        if p95 > 20_000:
            findings.append("P95 响应耗时超过 20 秒，可减少无关上下文或模型往返。")
        if not findings:
            findings.append("任务理解回归、运行完成率、轨迹与引用指标均在健康区间。")
        return findings
