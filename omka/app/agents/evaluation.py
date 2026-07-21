"""Deterministic evaluation of persisted Agent runs."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field
from sqlmodel import col, select

from omka.app.agents.tool_adapters import get_default_tool_registry
from omka.app.agents.tools import ToolRegistry
from omka.app.storage.db import AgentRun, AgentStep, get_session

_CITATION_PATTERN = re.compile(r"\[(knowledge|candidate|memory):[^\]]+\]")


class AgentRunEvaluation(BaseModel):
    run_id: int
    passed: bool
    score: float = Field(ge=0, le=1)
    step_count: int
    tool_call_count: int
    failed_tool_count: int
    denied_tool_count: int
    has_grounding_citation: bool
    has_task_brief: bool
    trace_complete: bool
    findings: list[str]


class AgentEvaluator:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or get_default_tool_registry()

    def evaluate_run(self, run_id: int) -> AgentRunEvaluation | None:
        with get_session() as session:
            run = session.get(AgentRun, run_id)
            if not run:
                return None
            steps = list(
                session.exec(
                    select(AgentStep)
                    .where(AgentStep.run_id == run_id)
                    .order_by(col(AgentStep.id))
                ).all()
            )

        tool_steps = [step for step in steps if step.step_type == "tool"]
        failed = [step for step in tool_steps if step.status == "failed"]
        denied = [step for step in tool_steps if step.status == "denied"]
        findings: list[str] = []
        deductions = 0.0

        accepted_statuses = {
            "success",
            "completed",
            "step_limit",
            "degraded",
            "needs_confirm",
            "needs_clarification",
        }
        if run.status not in accepted_statuses:
            findings.append(f"运行状态为 {run.status}")
            deductions += 0.35
        if failed:
            findings.append(f"{len(failed)} 个工具调用失败")
            deductions += min(0.3, len(failed) * 0.1)
        if denied:
            findings.append(f"{len(denied)} 个工具调用被权限策略拒绝")
            deductions += min(0.2, len(denied) * 0.08)
        unknown_tools = [
            step.tool_name
            for step in tool_steps
            if step.tool_name and self._registry.get(step.tool_name) is None
        ]
        if unknown_tools:
            findings.append(f"存在未注册工具: {', '.join(unknown_tools)}")
            deductions += 0.25

        used_context = run.used_context_json.get("used", [])
        final_answer = self._final_answer(steps, run.answer_preview)
        has_citation = bool(_CITATION_PATTERN.search(final_answer))
        if used_context and not has_citation:
            findings.append("使用了知识上下文，但回答预览中没有可追溯引用")
            deductions += 0.12

        has_task_brief = bool(run.used_context_json.get("task_brief"))
        if not has_task_brief:
            findings.append("运行缺少结构化任务契约，无法验证意图与成功标准")
            deductions += 0.12

        stages = {step.tool_name for step in steps}
        required_stages = {"understanding.task", "response.final"}
        if run.status != "needs_clarification":
            required_stages.update({"context.assemble", "planner.decide"})
        trace_complete = required_stages.issubset(stages)
        if not trace_complete:
            findings.append("运行轨迹缺少理解、上下文、规划或最终响应阶段")
            deductions += 0.12

        if not steps:
            findings.append("运行没有持久化步骤，无法回放")
            deductions += 0.4
        if not findings:
            findings.append("运行步骤、工具策略和可追溯性检查通过")

        score = round(max(0.0, 1.0 - deductions), 4)
        return AgentRunEvaluation(
            run_id=run_id,
            passed=score >= 0.75 and not failed and not unknown_tools,
            score=score,
            step_count=len(steps),
            tool_call_count=len(tool_steps),
            failed_tool_count=len(failed),
            denied_tool_count=len(denied),
            has_grounding_citation=has_citation,
            has_task_brief=has_task_brief,
            trace_complete=trace_complete,
            findings=findings,
        )

    @staticmethod
    def _final_answer(steps: list[AgentStep], fallback: str) -> str:
        for step in reversed(steps):
            if step.step_type != "final":
                continue
            answer = step.output_json.get("answer")
            if isinstance(answer, str):
                return answer
        return fallback
