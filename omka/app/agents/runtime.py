"""Bounded Agent runtime with typed tool execution and step persistence."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from omka.app.agents.base import AgentContext, AgentResponse, BaseAgent
from omka.app.agents.memory_extractor import ConversationMemoryExtractor
from omka.app.agents.prompts import SYSTEM_PROMPT, build_user_prompt
from omka.app.agents.tool_adapters import get_default_tool_registry
from omka.app.agents.task_understanding import (
    HeuristicTaskInterpreter,
    TaskBrief,
    TaskInterpreter,
)
from omka.app.agents.tools import ToolContext, ToolRegistry
from omka.app.agents.tracing import AgentRunTracer, format_exception
from omka.app.core.config import settings
from omka.app.core.logging import TraceContext, get_logger, trace
from omka.app.pipeline.summarizer import LLMClient
from omka.app.storage.db import AgentRun, get_session

logger = get_logger("agent")


class PlannerDecision(BaseModel):
    kind: Literal["final", "tool"]
    answer: str = ""
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    decision_summary: str = Field(
        default="",
        description="简短决策摘要，不包含隐藏推理过程",
    )


class AgentPlanner(Protocol):
    async def decide(
        self,
        *,
        context: AgentContext,
        observations: list[dict[str, Any]],
        tool_definitions: list[dict[str, Any]],
    ) -> PlannerDecision:
        ...


class LLMToolPlanner:
    """Model adapter that emits one validated decision per Agent step."""

    def __init__(self) -> None:
        self._llm = LLMClient(
            provider=settings.omka_agent_provider or settings.llm_provider,
            model=settings.omka_agent_model or settings.llm_model,
        )

    async def decide(
        self,
        *,
        context: AgentContext,
        observations: list[dict[str, Any]],
        tool_definitions: list[dict[str, Any]],
    ) -> PlannerDecision:
        tool_prompt = json.dumps(tool_definitions, ensure_ascii=False)
        observation_prompt = json.dumps(observations, ensure_ascii=False)
        user_prompt = build_user_prompt(
            user_message=context.user_message,
            task_brief=json.dumps(context.task_brief, ensure_ascii=False),
            interests=context.user_profile.get("interests", ""),
            projects=context.user_profile.get("projects", ""),
            profile_summary=context.user_profile.get("profile_summary", ""),
            preferences=context.user_profile.get("preferences", ""),
            avoidances=context.user_profile.get("avoidances", ""),
            digest_items=self._format_items(context.digest_items),
            knowledge_items=self._format_items(context.knowledge_items),
            candidate_items=self._format_items(context.candidate_items),
            memory_items=self._format_items(context.memory_items),
        )
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    f"{SYSTEM_PROMPT}\n\n"
                    "你现在运行在一个受控 Agent Runtime 中。每一步只能选择最终回答，"
                    "或调用一个列出的工具。不要编造工具名，不要把工具调用伪装成文字回答。"
                    "高风险工具会由系统要求用户确认。不要输出思维链，只输出简短决策摘要。\n\n"
                    "严格返回一个 JSON 对象：\n"
                    '{"kind":"final","answer":"...","decision_summary":"..."}\n'
                    "或\n"
                    '{"kind":"tool","tool_name":"...","arguments":{},'
                    '"decision_summary":"..."}'
                ),
            },
        ]
        messages.extend(context.recent_messages[-6:])
        messages.append(
            {
                "role": "user",
                "content": (
                    f"{user_prompt}\n\n"
                    f"可用工具：\n{tool_prompt}\n\n"
                    f"本轮已有工具观察：\n{observation_prompt}"
                ),
            }
        )
        response_text = await self._llm.chat(
            messages=messages,
            temperature=settings.omka_agent_temperature,
            max_tokens=1200,
        )
        return self._parse_decision(response_text)

    @staticmethod
    def _format_items(items: list[dict[str, str]]) -> str:
        if not items:
            return ""
        return json.dumps(items, ensure_ascii=False)

    @staticmethod
    def _parse_decision(response_text: str) -> PlannerDecision:
        text = response_text.strip()
        candidates = [text]
        candidates.extend(
            match.group(1).strip()
            for match in re.finditer(
                r"```(?:json)?\s*(\{.*?\})\s*```",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
        )
        decoder = json.JSONDecoder()
        for start in (index for index, character in enumerate(text) if character == "{"):
            try:
                data, _end = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                continue
            candidates.append(json.dumps(data, ensure_ascii=False))

        for candidate in candidates:
            cleaned = candidate.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            try:
                data = json.loads(cleaned.strip())
                decision = PlannerDecision.model_validate(data)
                if decision.kind == "tool" and not decision.tool_name:
                    raise ValueError("工具决策缺少 tool_name")
                if decision.kind == "final" and not decision.answer.strip():
                    raise ValueError("最终回答为空")
                return decision
            except (json.JSONDecodeError, ValidationError, ValueError):
                continue

        # Compatibility fallback for providers that genuinely return a direct answer.
        return PlannerDecision(
            kind="final",
            answer=response_text.strip(),
            decision_summary="模型直接返回了最终回答",
        )


class KnowledgeAgentRuntime(BaseAgent):
    """Owns one complete Agent turn from decision through tool observation."""

    def __init__(
        self,
        *,
        planner: AgentPlanner | None = None,
        tool_registry: ToolRegistry | None = None,
        memory_extractor: ConversationMemoryExtractor | None = None,
        task_interpreter: TaskInterpreter | None = None,
        enable_memory_extraction: bool = True,
        max_steps: int = 4,
    ) -> None:
        self._planner = planner or LLMToolPlanner()
        self._tools = tool_registry or get_default_tool_registry()
        self._memory_extractor = memory_extractor or ConversationMemoryExtractor()
        self._task_interpreter = task_interpreter or HeuristicTaskInterpreter()
        self._enable_memory_extraction = enable_memory_extraction
        self._max_steps = max(1, min(max_steps, 8))

    async def execute(
        self,
        *,
        user_message: str,
        conversation_id: str,
        user_external_id: str,
        channel: str = "agent",
        context_builder=None,
        run_id: int | None = None,
    ) -> AgentResponse:
        """Execute a full turn, including context collection, under one trace."""

        from omka.app.agents.context_builder import ContextBuilder

        run_started = time.perf_counter()
        run = (
            self._get_run(run_id)
            if run_id is not None
            else self.create_pending_run(
                user_message=user_message,
                conversation_id=conversation_id,
                user_external_id=user_external_id,
                channel=channel,
            )
        )
        tracer = AgentRunTracer(self._require_run_id(run))
        self._mark_running(run, context=None)
        builder = context_builder or ContextBuilder()
        understanding_span = tracer.start(
            step_type="understanding",
            stage_name="understanding.task",
            input_json={"message": user_message},
        )
        understanding_finished = False
        try:
            task_brief = self._task_interpreter.interpret(user_message)
            tracer.finish(
                understanding_span,
                output_json=task_brief.model_dump(mode="json"),
            )
            understanding_finished = True
            self._persist_task_brief(self._require_run_id(run), task_brief)
            if task_brief.needs_clarification:
                context = AgentContext(
                    user_message=user_message,
                    conversation_id=conversation_id,
                    user_external_id=user_external_id,
                    task_brief=task_brief.model_dump(mode="json"),
                )
                answer = task_brief.clarification_question or (
                    "请补充具体对象和期望结果，我再继续执行。"
                )
                return self._finish_success(
                    run,
                    context,
                    answer,
                    0,
                    tracer=tracer,
                    status="needs_clarification",
                    latency_ms=self._elapsed_ms(run_started),
                    suggested_actions=["补充任务对象", "说明期望结果"],
                )
            context = await builder.build(
                user_message=user_message,
                conversation_id=conversation_id,
                user_external_id=user_external_id,
                tracer=tracer,
                task_brief=task_brief.model_dump(mode="json"),
            )
        except Exception as exc:
            if not understanding_finished:
                tracer.finish(
                    understanding_span,
                    status="failed",
                    error_message=format_exception(exc),
                )
            error_message = format_exception(exc)
            logger.error(
                "Agent 上下文构建失败 | run_id=%s | error=%s",
                run.id,
                error_message,
            )
            return self._fail_response(
                run,
                tracer,
                error_message,
                latency_ms=self._elapsed_ms(run_started),
            )

        return await self.answer(
            context,
            run_id=self._require_run_id(run),
            tracer=tracer,
            run_started=run_started,
        )

    @trace("agent")
    async def answer(
        self,
        context: AgentContext,
        *,
        run_id: int | None = None,
        tracer: AgentRunTracer | None = None,
        run_started: float | None = None,
    ) -> AgentResponse:
        run_started = run_started or time.perf_counter()
        run = self._get_run(run_id) if run_id is not None else self._create_run(context)
        run_id_value = self._require_run_id(run)
        tracer = tracer or AgentRunTracer(run_id_value)
        self._mark_running(run, context=context)
        observations: list[dict[str, Any]] = []

        try:
            if not context.task_brief:
                task_brief = self._task_interpreter.interpret(context.user_message)
                context.task_brief = task_brief.model_dump(mode="json")
                tracer.record(
                    step_type="understanding",
                    stage_name="understanding.task",
                    input_json={"message": context.user_message},
                    output_json=context.task_brief,
                )
                self._persist_task_brief(run_id_value, task_brief)
            for iteration in range(self._max_steps):
                tool_definitions = self._tools.definitions()
                decision_span = tracer.start(
                    step_type="decision",
                    stage_name="planner.decide",
                    input_json={
                        "iteration": iteration + 1,
                        "observation_count": len(observations),
                        "available_tools": [
                            definition.get("name", "")
                            for definition in tool_definitions
                        ],
                    },
                )
                try:
                    decision = await self._planner.decide(
                        context=context,
                        observations=observations,
                        tool_definitions=tool_definitions,
                    )
                except Exception as exc:
                    tracer.finish(
                        decision_span,
                        status="failed",
                        error_message=format_exception(exc),
                    )
                    raise
                tracer.finish(
                    decision_span,
                    output_json=decision.model_dump(mode="json"),
                )

                if decision.kind == "final":
                    await self._extract_memories(
                        context,
                        decision.answer,
                        tracer,
                    )
                    return self._finish_success(
                        run,
                        context,
                        decision.answer,
                        iteration + 1,
                        tracer=tracer,
                        latency_ms=self._elapsed_ms(run_started),
                    )

                tool_context = ToolContext(
                    actor_channel=run.channel,
                    actor_external_id=context.user_external_id,
                    conversation_id=context.conversation_id,
                )
                tool_span = tracer.start(
                    step_type="tool",
                    stage_name=decision.tool_name or "tool.unknown",
                    input_json={
                        "arguments": decision.arguments,
                        "decision_summary": decision.decision_summary,
                    },
                )
                try:
                    result = await self._tools.execute(
                        decision.tool_name or "",
                        decision.arguments,
                        tool_context,
                    )
                except Exception as exc:
                    tracer.finish(
                        tool_span,
                        status="failed",
                        error_message=format_exception(exc),
                    )
                    raise

                result_json = result.model_dump(mode="json")
                tracer.finish(
                    tool_span,
                    output_json=result_json,
                    status=result.status,
                    error_message=result.error_message,
                )

                if result.status == "needs_confirm":
                    return self._finish_success(
                        run,
                        context,
                        result.content,
                        iteration + 1,
                        tracer=tracer,
                        status="needs_confirm",
                        latency_ms=self._elapsed_ms(run_started),
                        suggested_actions=[
                            f"/omka confirm {result.confirmation_id}",
                            f"/omka cancel {result.confirmation_id}",
                        ],
                    )

                observations.append(result_json)

            fallback = (
                "我已达到本轮最大执行步数，暂时没有安全地完成请求。"
                "你可以缩小问题范围，或使用 /omka help 查看确定性命令。"
            )
            return self._finish_success(
                run,
                context,
                fallback,
                self._max_steps,
                tracer=tracer,
                status="step_limit",
                latency_ms=self._elapsed_ms(run_started),
            )
        except Exception as exc:
            error_message = format_exception(exc)
            logger.error(
                "Agent Runtime 运行失败 | run_id=%s | error=%s",
                run.id,
                error_message,
            )
            if observations:
                degraded_answer = self._degraded_answer(
                    observations,
                    error_message,
                )
                return self._finish_success(
                    run,
                    context,
                    degraded_answer,
                    len(observations),
                    tracer=tracer,
                    status="degraded",
                    latency_ms=self._elapsed_ms(run_started),
                    suggested_actions=["稍后重试模型规划", "/omka help"],
                )
            if self._has_local_context(context):
                degraded_answer = self._context_degraded_answer(
                    context,
                    error_message,
                )
                return self._finish_success(
                    run,
                    context,
                    degraded_answer,
                    0,
                    tracer=tracer,
                    status="degraded",
                    latency_ms=self._elapsed_ms(run_started),
                    suggested_actions=["网络恢复后重试完整分析", "查看本地知识来源"],
                )
            return self._fail_response(
                run,
                tracer,
                error_message,
                latency_ms=self._elapsed_ms(run_started),
            )

    async def _extract_memories(
        self,
        context: AgentContext,
        answer: str,
        tracer: AgentRunTracer,
    ) -> None:
        if not self._enable_memory_extraction:
            return
        span = tracer.start(
            step_type="observation",
            stage_name="memory.extract",
            input_json={"answer_chars": len(answer)},
        )
        try:
            created_ids = await self._memory_extractor.extract(
                user_message=context.user_message,
                assistant_answer=answer,
                user_external_id=context.user_external_id,
                conversation_id=context.conversation_id,
            )
        except Exception as exc:
            error_message = format_exception(exc)
            tracer.finish(
                span,
                status="failed",
                error_message=error_message,
            )
            logger.warning(
                "Agent 回答成功但记忆抽取失败 | error=%s",
                error_message,
            )
            return
        tracer.finish(
            span,
            output_json={
                "created_count": len(created_ids),
                "candidate_memory_ids": created_ids,
            },
        )

    @staticmethod
    def create_pending_run(
        *,
        user_message: str,
        conversation_id: str,
        user_external_id: str,
        channel: str = "agent",
    ) -> AgentRun:
        with get_session() as session:
            run = AgentRun(
                conversation_id=conversation_id,
                user_external_id=user_external_id,
                channel=channel,
                user_message=user_message,
                model=settings.omka_agent_model or settings.llm_model,
                status="pending",
                used_context_json={
                    "trace_id": TraceContext.current_id(),
                    "available": [],
                },
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def _create_run(self, context: AgentContext) -> AgentRun:
        return self.create_pending_run(
            user_message=context.user_message,
            conversation_id=context.conversation_id,
            user_external_id=context.user_external_id,
        )

    @staticmethod
    def _get_run(run_id: int | None) -> AgentRun:
        if run_id is None:
            raise ValueError("Agent run_id is required")
        with get_session() as session:
            run = session.get(AgentRun, run_id)
            if not run:
                raise ValueError(f"Agent run {run_id} not found")
            return run

    def _mark_running(
        self,
        run: AgentRun,
        *,
        context: AgentContext | None,
    ) -> None:
        with get_session() as session:
            stored = session.get(AgentRun, run.id)
            if not stored:
                return
            stored.status = "running"
            if context is not None:
                stored.used_context_json = {
                    **stored.used_context_json,
                    "available": self._used_context(context),
                }
            session.add(stored)
            session.commit()

    @staticmethod
    def _persist_task_brief(run_id: int, task_brief: TaskBrief) -> None:
        with get_session() as session:
            stored = session.get(AgentRun, run_id)
            if not stored:
                return
            stored.used_context_json = {
                **stored.used_context_json,
                "task_brief": task_brief.model_dump(mode="json"),
            }
            session.add(stored)
            session.commit()

    def _finish_success(
        self,
        run: AgentRun,
        context: AgentContext,
        answer: str,
        step_count: int,
        *,
        tracer: AgentRunTracer,
        status: str = "success",
        latency_ms: int = 0,
        suggested_actions: list[str] | None = None,
    ) -> AgentResponse:
        with get_session() as session:
            stored = session.get(AgentRun, run.id)
            if stored:
                stored.status = status
                stored.answer_preview = answer[:200]
                stored.latency_ms = latency_ms
                stored.used_context_json = {
                    **stored.used_context_json,
                    "step_count": step_count,
                    "used": self._used_context(context),
                }
                session.add(stored)
                session.commit()
        tracer.record(
            step_type="final",
            stage_name="response.final",
            input_json={},
            output_json={
                "answer": answer,
                "status": status,
            },
            status=(
                status
                if status in {"needs_confirm", "degraded", "step_limit"}
                else "success"
            ),
        )
        return AgentResponse(
            answer=answer,
            used_context=self._used_context(context),
            suggested_actions=suggested_actions or self._suggest_actions(context),
            run_id=run.id,
            status=status,
        )

    @staticmethod
    def _finish_failed(
        run: AgentRun,
        error_message: str,
        *,
        latency_ms: int = 0,
    ) -> None:
        with get_session() as session:
            stored = session.get(AgentRun, run.id)
            if stored:
                stored.status = "failed"
                stored.error_message = error_message[:1000]
                stored.latency_ms = latency_ms
                session.add(stored)
                session.commit()

    def _fail_response(
        self,
        run: AgentRun,
        tracer: AgentRunTracer,
        error_message: str,
        *,
        latency_ms: int,
    ) -> AgentResponse:
        answer = "处理请求时发生错误。你可以稍后重试，或使用 /omka help。"
        self._finish_failed(
            run,
            error_message,
            latency_ms=latency_ms,
        )
        tracer.record(
            step_type="final",
            stage_name="response.failed",
            output_json={
                "answer": answer,
                "status": "failed",
                "error": error_message,
            },
            status="failed",
            error_message=error_message,
        )
        return AgentResponse(
            answer=answer,
            used_context=[],
            suggested_actions=["/omka help"],
            run_id=run.id,
            status="failed",
        )

    @staticmethod
    def _require_run_id(run: AgentRun) -> int:
        if run.id is None:
            raise RuntimeError("Agent run was not assigned an ID")
        return run.id

    @staticmethod
    def _degraded_answer(
        observations: list[dict[str, Any]],
        error_message: str,
    ) -> str:
        lines = [
            "模型在后续规划时暂时断开，但此前工具调用已经完成。"
            "以下是可追溯的已取得结果："
        ]
        for observation in observations:
            tool_name = str(observation.get("tool_name") or "未知工具")
            content = str(
                observation.get("content")
                or observation.get("error_message")
                or "工具已完成，但没有文本摘要"
            )
            lines.append(f"- {tool_name}：{content}")
            data = observation.get("data")
            if isinstance(data, dict) and data:
                data_text = json.dumps(data, ensure_ascii=False)
                if len(data_text) > 600:
                    data_text = data_text[:600] + "…"
                lines.append(f"  结构化结果：{data_text}")
        lines.append(f"\n降级原因：{error_message}。你可以稍后重试以获得完整模型回答。")
        return "\n".join(lines)

    @staticmethod
    def _has_local_context(context: AgentContext) -> bool:
        return any(
            (
                context.digest_items,
                context.knowledge_items,
                context.candidate_items,
                context.memory_items,
            )
        )

    @staticmethod
    def _context_degraded_answer(
        context: AgentContext,
        error_message: str,
    ) -> str:
        lines = [
            "模型连接暂时不可用，但任务理解和本地知识检索已经完成。",
            "下面先给出可以直接核验的本地结果：",
        ]
        added = 0
        for source, items in (
            ("knowledge", context.knowledge_items),
            ("candidate", context.candidate_items),
            ("digest", context.digest_items),
            ("memory", context.memory_items),
        ):
            for item in items:
                if added >= 5:
                    break
                title = str(
                    item.get("title")
                    or item.get("content")
                    or item.get("summary")
                    or "未命名条目"
                )
                summary = str(item.get("summary") or "")
                item_id = str(item.get("id") or "")
                citation = (
                    f" [{source}:{item_id}]"
                    if source in {"knowledge", "candidate", "memory"} and item_id
                    else ""
                )
                detail = f" — {summary}" if summary and summary != title else ""
                lines.append(f"- {title[:120]}{detail[:220]}{citation}")
                added += 1
            if added >= 5:
                break
        lines.append(
            f"\n降级原因：{error_message}。网络恢复后可重试，获得完整排序与解释。"
        )
        return "\n".join(lines)

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

    @staticmethod
    def _used_context(context: AgentContext) -> list[dict[str, str]]:
        used: list[dict[str, str]] = []
        for name, items in (
            ("memory", context.memory_items),
            ("digest", context.digest_items),
            ("knowledge", context.knowledge_items),
            ("candidate", context.candidate_items),
        ):
            if items:
                used.append({"type": name, "count": str(len(items))})
        return used

    @staticmethod
    def _suggest_actions(context: AgentContext) -> list[str]:
        actions: list[str] = []
        if context.digest_items:
            actions.append("/omka latest")
        if context.candidate_items:
            actions.append("查看候选内容")
        return actions or ["/omka help"]
