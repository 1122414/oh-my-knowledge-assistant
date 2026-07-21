"""Persistent, live-updating trace spans for Agent runs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlmodel import col, select

from omka.app.storage.db import AgentStep, get_session


def format_exception(exc: BaseException) -> str:
    """Always return a useful error string, even for empty exception messages."""

    detail = str(exc).strip()
    if not detail:
        cause = exc.__cause__ or exc.__context__
        if cause is not None:
            cause_detail = str(cause).strip()
            detail = (
                f"{type(cause).__name__}: {cause_detail}"
                if cause_detail
                else type(cause).__name__
            )
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


@dataclass(frozen=True)
class AgentTraceSpan:
    step_id: int
    step_index: int
    started_at: float


class AgentRunTracer:
    """Writes a stage before it starts and updates it when it finishes."""

    def __init__(self, run_id: int) -> None:
        self.run_id = run_id
        with get_session() as session:
            latest = session.exec(
                select(AgentStep)
                .where(AgentStep.run_id == run_id)
                .order_by(
                    col(AgentStep.step_index).desc(),
                    col(AgentStep.id).desc(),
                )
                .limit(1)
            ).first()
        self._next_index = (latest.step_index + 1) if latest else 0

    def start(
        self,
        *,
        step_type: str,
        stage_name: str,
        input_json: dict[str, Any] | None = None,
    ) -> AgentTraceSpan:
        step_index = self._next_index
        self._next_index += 1
        with get_session() as session:
            step = AgentStep(
                run_id=self.run_id,
                step_index=step_index,
                step_type=step_type,
                tool_name=stage_name,
                input_json=input_json or {},
                output_json={},
                status="running",
            )
            session.add(step)
            session.commit()
            session.refresh(step)
            if step.id is None:
                raise RuntimeError("Agent trace step was not assigned an ID")
            return AgentTraceSpan(
                step_id=step.id,
                step_index=step_index,
                started_at=time.perf_counter(),
            )

    def finish(
        self,
        span: AgentTraceSpan,
        *,
        output_json: dict[str, Any] | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        with get_session() as session:
            step = session.get(AgentStep, span.step_id)
            if not step:
                return
            step.output_json = output_json or {}
            step.status = status
            step.latency_ms = int((time.perf_counter() - span.started_at) * 1000)
            step.error_message = error_message
            session.add(step)
            session.commit()

    def record(
        self,
        *,
        step_type: str,
        stage_name: str,
        input_json: dict[str, Any] | None = None,
        output_json: dict[str, Any] | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        span = self.start(
            step_type=step_type,
            stage_name=stage_name,
            input_json=input_json,
        )
        self.finish(
            span,
            output_json=output_json,
            status=status,
            error_message=error_message,
        )
