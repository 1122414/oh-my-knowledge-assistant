from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from sqlmodel import col, select

from omka.app.agents.context_builder import ContextBuilder
from omka.app.agents.evaluation import AgentEvaluator, AgentRunEvaluation
from omka.app.agents.harness import AgentHarness, AgentHarnessSummary
from omka.app.agents.runtime import KnowledgeAgentRuntime
from omka.app.agents.task_understanding import (
    HeuristicTaskInterpreter,
    TaskBrief,
)
from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.core.settings_service import get_setting
from omka.app.storage.db import (
    AgentRun,
    AgentStep,
    ConversationMessage,
    get_session,
)

router = APIRouter()


class AgentTestRequest(BaseModel):
    message: str


class AgentTestResponse(BaseModel):
    answer: str
    used_context: list[dict[str, Any]]
    suggested_actions: list[str]
    status: str
    run_id: int | None = None


class AgentRunStartRequest(BaseModel):
    message: str
    conversation_id: str = "web-agent-console"
    user_external_id: str = "web-console"


class AgentRunStartResponse(BaseModel):
    run_id: int
    status: str


class AgentRunSummary(BaseModel):
    id: int
    conversation_id: str
    user_external_id: str
    channel: str
    user_message: str
    answer_preview: str
    model: str
    status: str
    latency_ms: int
    created_at: datetime


class AgentStepResponse(BaseModel):
    id: int
    step_index: int
    step_type: str
    tool_name: str | None
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    status: str
    latency_ms: int
    error_message: str | None
    created_at: datetime


class AgentRunDetail(AgentRunSummary):
    answer: str
    used_context_json: dict[str, Any]
    error_message: str | None
    steps: list[AgentStepResponse]


class AgentUnderstandRequest(BaseModel):
    message: str


@router.post("/understand", response_model=TaskBrief)
async def understand_agent_task(request: AgentUnderstandRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="任务不能为空",
        )
    return HeuristicTaskInterpreter().interpret(message)


@router.get("/harness/summary", response_model=AgentHarnessSummary)
async def get_agent_harness_summary(limit: int = 50):
    return AgentHarness().summarize(limit=limit)


@router.get("/runs", response_model=list[AgentRunSummary])
async def list_agent_runs(limit: int = 50):
    safe_limit = min(max(limit, 1), 200)
    with get_session() as session:
        runs = session.exec(
            select(AgentRun)
            .order_by(col(AgentRun.created_at).desc())
            .limit(safe_limit)
        ).all()
    return [AgentRunSummary.model_validate(run, from_attributes=True) for run in runs]


@router.post(
    "/runs",
    response_model=AgentRunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_agent_run(
    request: AgentRunStartRequest,
    background_tasks: BackgroundTasks,
):
    if not _agent_chat_enabled():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent 对话能力未启用",
        )

    message = request.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Agent 任务不能为空",
        )

    run = KnowledgeAgentRuntime.create_pending_run(
        user_message=message,
        conversation_id=request.conversation_id,
        user_external_id=request.user_external_id,
        channel="web",
    )
    if run.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent Run 创建失败",
        )
    background_tasks.add_task(
        _execute_web_run,
        run.id,
        message,
        request.conversation_id,
        request.user_external_id,
    )
    return AgentRunStartResponse(run_id=run.id, status=run.status)


@router.get("/runs/{run_id}", response_model=AgentRunDetail)
async def get_agent_run(run_id: int):
    with get_session() as session:
        run = session.get(AgentRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Agent run not found")
        steps = session.exec(
            select(AgentStep)
            .where(AgentStep.run_id == run_id)
            .order_by(col(AgentStep.step_index), col(AgentStep.id))
        ).all()
    payload = AgentRunSummary.model_validate(run, from_attributes=True).model_dump()
    return AgentRunDetail(
        **payload,
        answer=_full_answer(steps, run.answer_preview),
        used_context_json=run.used_context_json,
        error_message=run.error_message,
        steps=[
            AgentStepResponse.model_validate(step, from_attributes=True)
            for step in steps
        ],
    )


@router.post(
    "/runs/{run_id}/replay",
    response_model=AgentRunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def replay_agent_run(run_id: int, background_tasks: BackgroundTasks):
    with get_session() as session:
        original = session.get(AgentRun, run_id)
        if not original:
            raise HTTPException(status_code=404, detail="Agent run not found")
        message = original.user_message
        conversation_id = original.conversation_id
        user_external_id = original.user_external_id

    replay = KnowledgeAgentRuntime.create_pending_run(
        user_message=message,
        conversation_id=conversation_id,
        user_external_id=user_external_id,
        channel="replay",
    )
    if replay.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Replay Run 创建失败",
        )
    background_tasks.add_task(
        _execute_replay_run,
        replay.id,
        message,
        conversation_id,
        user_external_id,
    )
    return AgentRunStartResponse(run_id=replay.id, status=replay.status)


@router.get("/runs/{run_id}/evaluation", response_model=AgentRunEvaluation)
async def evaluate_agent_run(run_id: int):
    evaluation = AgentEvaluator().evaluate_run(run_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return evaluation


@router.post("/test", response_model=AgentTestResponse)
async def test_agent(request: AgentTestRequest):
    if not _agent_chat_enabled():
        return AgentTestResponse(
            answer="Agent 对话能力未启用",
            used_context=[],
            suggested_actions=[],
            status="disabled",
        )

    try:
        response = await KnowledgeAgentRuntime().execute(
            user_message=request.message,
            conversation_id="test",
            user_external_id="test",
            channel="test",
            context_builder=_context_builder(),
        )

        return AgentTestResponse(
            answer=response.answer,
            used_context=response.used_context,
            suggested_actions=response.suggested_actions,
            status=response.status,
            run_id=response.run_id,
        )
    except Exception as e:
        logger.error("Agent 测试失败 | error=%s", e)
        return AgentTestResponse(
            answer=f"Agent 测试失败: {str(e)}",
            used_context=[],
            suggested_actions=[],
            status="error",
        )


def _agent_chat_enabled() -> bool:
    return bool(
        get_setting(
            "omka_agent_chat_enabled",
            settings.omka_agent_chat_enabled,
        )
    )


def _context_builder() -> ContextBuilder:
    return ContextBuilder(
        max_recent_messages=int(
            get_setting(
                "omka_agent_max_recent_messages",
                settings.omka_agent_max_recent_messages,
            )
        ),
        max_digest_items=int(
            get_setting(
                "omka_agent_max_digest_items",
                settings.omka_agent_max_digest_items,
            )
        ),
        max_knowledge_items=int(
            get_setting(
                "omka_agent_max_knowledge_items",
                settings.omka_agent_max_knowledge_items,
            )
        ),
        max_candidate_items=int(
            get_setting(
                "omka_agent_max_candidate_items",
                settings.omka_agent_max_candidate_items,
            )
        ),
        max_memory_items=int(
            get_setting("memory_max_active_items", settings.memory_max_active_items)
        ),
        max_context_chars=int(
            get_setting(
                "omka_agent_max_context_chars",
                settings.omka_agent_max_context_chars,
            )
        ),
    )


async def _execute_web_run(
    run_id: int,
    message: str,
    conversation_id: str,
    user_external_id: str,
) -> None:
    response = await KnowledgeAgentRuntime().execute(
        user_message=message,
        conversation_id=conversation_id,
        user_external_id=user_external_id,
        channel="web",
        context_builder=_context_builder(),
        run_id=run_id,
    )
    try:
        with get_session() as session:
            session.add(
                ConversationMessage(
                    channel="web",
                    conversation_id=conversation_id,
                    user_external_id=user_external_id,
                    role="user",
                    content=message,
                )
            )
            session.add(
                ConversationMessage(
                    channel="web",
                    conversation_id=conversation_id,
                    user_external_id=user_external_id,
                    role="assistant",
                    content=response.answer,
                )
            )
            session.commit()
    except Exception as exc:
        logger.warning(
            "保存网页 Agent 对话失败 | run_id=%s | error=%s",
            run_id,
            exc,
        )


async def _execute_replay_run(
    run_id: int,
    message: str,
    conversation_id: str,
    user_external_id: str,
) -> None:
    await KnowledgeAgentRuntime().execute(
        user_message=message,
        conversation_id=conversation_id,
        user_external_id=user_external_id,
        channel="replay",
        context_builder=_context_builder(),
        run_id=run_id,
    )


def _full_answer(steps: list[AgentStep], fallback: str) -> str:
    for step in reversed(steps):
        if step.step_type != "final":
            continue
        answer = step.output_json.get("answer")
        if isinstance(answer, str):
            return answer
    return fallback
