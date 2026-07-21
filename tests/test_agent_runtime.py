from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from omka.app.agents.base import AgentContext, AgentResponse
from omka.app.agents.runtime import (
    KnowledgeAgentRuntime,
    LLMToolPlanner,
    PlannerDecision,
)
from omka.app.agents.tools import AgentTool, ToolContext, ToolRegistry
from omka.app.storage.db import AgentRun, AgentStep


class EmptyArgs(BaseModel):
    pass


class FakePlanner:
    def __init__(self, decisions: list[PlannerDecision]) -> None:
        self._decisions: Iterator[PlannerDecision] = iter(decisions)

    async def decide(self, **_kwargs: Any) -> PlannerDecision:
        return next(self._decisions)


@pytest.fixture()
def isolated_sessions(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session() -> Session:
        return Session(engine)

    import omka.app.agents.runtime as runtime_module
    import omka.app.agents.tracing as tracing_module
    import omka.app.agents.context_builder as context_module
    import omka.app.agents.tools as tools_module
    import omka.app.agents.evaluation as evaluation_module
    import omka.app.agents.harness as harness_module
    import omka.app.services.action_service as action_module
    import omka.app.services.agent_goal_service as goal_module
    import omka.app.services.memory_service as memory_module
    import omka.app.services.recommendation_service as recommendation_module
    import omka.app.services.user_profile_service as profile_module

    monkeypatch.setattr(runtime_module, "get_session", get_test_session)
    monkeypatch.setattr(tracing_module, "get_session", get_test_session)
    monkeypatch.setattr(context_module, "get_session", get_test_session)
    monkeypatch.setattr(tools_module, "get_session", get_test_session)
    monkeypatch.setattr(evaluation_module, "get_session", get_test_session)
    monkeypatch.setattr(harness_module, "get_session", get_test_session)
    monkeypatch.setattr(action_module, "get_session", get_test_session)
    monkeypatch.setattr(goal_module, "get_session", get_test_session)
    monkeypatch.setattr(memory_module, "get_session", get_test_session)
    monkeypatch.setattr(recommendation_module, "get_session", get_test_session)
    monkeypatch.setattr(profile_module, "get_session", get_test_session)
    monkeypatch.setattr(
        tools_module.PermissionService,
        "check_permission",
        staticmethod(lambda _actor, _level: True),
    )
    return get_test_session


@pytest.mark.asyncio
async def test_runtime_executes_tool_then_finishes(isolated_sessions) -> None:
    registry = ToolRegistry()
    registry.register(
        AgentTool(
            name="test.lookup",
            description="测试读取工具",
            args_model=EmptyArgs,
            handler=lambda _args, _context: {
                "message": "lookup complete",
                "value": 42,
            },
        )
    )
    planner = FakePlanner(
        [
            PlannerDecision(kind="tool", tool_name="test.lookup", arguments={}),
            PlannerDecision(kind="final", answer="答案是 42"),
        ]
    )
    runtime = KnowledgeAgentRuntime(
        planner=planner,
        tool_registry=registry,
        enable_memory_extraction=False,
    )
    context = AgentContext(
        user_message="查一下测试值",
        conversation_id="conv-a",
        user_external_id="user-a",
    )

    response = await runtime.answer(context)

    assert response.answer == "答案是 42"
    assert response.status == "success"
    assert response.run_id is not None
    with isolated_sessions() as session:
        run = session.get(AgentRun, response.run_id)
        steps = session.exec(
            select(AgentStep)
            .where(AgentStep.run_id == response.run_id)
            .order_by(AgentStep.id)
        ).all()
    assert run is not None
    assert run.status == "success"
    assert [step.step_type for step in steps] == [
        "understanding",
        "decision",
        "tool",
        "decision",
        "final",
    ]
    assert steps[2].tool_name == "test.lookup"

    from omka.app.agents.evaluation import AgentEvaluator

    evaluation = AgentEvaluator(registry=registry).evaluate_run(response.run_id)
    assert evaluation is not None
    assert evaluation.passed
    assert evaluation.tool_call_count == 1


@pytest.mark.asyncio
async def test_execute_traces_context_collection_before_planning(
    isolated_sessions,
) -> None:
    from omka.app.agents.context_builder import ContextBuilder

    runtime = KnowledgeAgentRuntime(
        planner=FakePlanner(
            [PlannerDecision(kind="final", answer="上下文检查完成")]
        ),
        tool_registry=ToolRegistry(),
        enable_memory_extraction=False,
    )

    response = await runtime.execute(
        user_message="检查上下文",
        conversation_id="trace-context",
        user_external_id="trace-owner",
        context_builder=ContextBuilder(
            max_recent_messages=2,
            max_digest_items=2,
            max_knowledge_items=2,
            max_candidate_items=2,
            max_memory_items=2,
        ),
    )

    with isolated_sessions() as session:
        steps = session.exec(
            select(AgentStep)
            .where(AgentStep.run_id == response.run_id)
            .order_by(AgentStep.step_index)
        ).all()

    assert [step.tool_name for step in steps[:8]] == [
        "understanding.task",
        "context.recent_messages",
        "context.daily_digest",
        "context.knowledge",
        "context.candidates",
        "context.memory",
        "context.profile",
        "context.assemble",
    ]
    assert [step.status for step in steps] == ["success"] * len(steps)
    assert steps[8].tool_name == "planner.decide"
    assert steps[-1].tool_name == "response.final"


@pytest.mark.asyncio
async def test_runtime_degrades_to_completed_tool_results_when_planner_disconnects(
    isolated_sessions,
) -> None:
    registry = ToolRegistry()
    registry.register(
        AgentTool(
            name="test.status",
            description="返回测试状态",
            args_model=EmptyArgs,
            handler=lambda _args, _context: {
                "message": "已取得状态",
                "count": 3,
            },
        )
    )

    class DisconnectingPlanner:
        def __init__(self) -> None:
            self.calls = 0

        async def decide(self, **_kwargs: Any) -> PlannerDecision:
            self.calls += 1
            if self.calls == 1:
                return PlannerDecision(
                    kind="tool",
                    tool_name="test.status",
                    arguments={},
                )
            raise ConnectionError("model disconnected")

    runtime = KnowledgeAgentRuntime(
        planner=DisconnectingPlanner(),
        tool_registry=registry,
        enable_memory_extraction=False,
    )
    response = await runtime.answer(
        AgentContext(
            user_message="查看状态",
            conversation_id="degraded-conversation",
            user_external_id="owner",
        )
    )

    assert response.status == "degraded"
    assert "test.status" in response.answer
    assert "已取得状态" in response.answer
    with isolated_sessions() as session:
        run = session.get(AgentRun, response.run_id)
        steps = session.exec(
            select(AgentStep)
            .where(AgentStep.run_id == response.run_id)
            .order_by(AgentStep.step_index)
        ).all()
    assert run is not None
    assert run.status == "degraded"
    assert [step.status for step in steps] == [
        "success",
        "success",
        "success",
        "failed",
        "degraded",
    ]


@pytest.mark.asyncio
async def test_runtime_returns_grounded_local_context_when_model_is_unavailable(
    isolated_sessions,
) -> None:
    class OfflinePlanner:
        async def decide(self, **_kwargs: Any) -> PlannerDecision:
            raise ConnectionError("provider unavailable")

    runtime = KnowledgeAgentRuntime(
        planner=OfflinePlanner(),
        tool_registry=ToolRegistry(),
        enable_memory_extraction=False,
    )
    response = await runtime.answer(
        AgentContext(
            user_message="推荐本地候选",
            conversation_id="offline-context",
            user_external_id="owner",
            candidate_items=[
                {
                    "id": "candidate-1",
                    "title": "Local Agent",
                    "summary": "可离线核验的候选条目",
                }
            ],
        )
    )

    assert response.status == "degraded"
    assert "Local Agent" in response.answer
    assert "[candidate:candidate-1]" in response.answer


@pytest.mark.asyncio
async def test_confirmation_survives_registry_round_trip(isolated_sessions) -> None:
    registry = ToolRegistry()
    executed: list[str] = []

    def destructive_handler(_args: EmptyArgs, context: ToolContext) -> dict[str, Any]:
        executed.append(context.actor_external_id)
        return {"message": "confirmed"}

    registry.register(
        AgentTool(
            name="test.destructive",
            description="测试高风险工具",
            args_model=EmptyArgs,
            handler=destructive_handler,
            risk="destructive",
            requires_confirmation=True,
        )
    )
    context = ToolContext(
        actor_channel="test",
        actor_external_id="owner",
        conversation_id="conv",
    )

    pending = await registry.execute("test.destructive", {}, context)
    assert pending.status == "needs_confirm"
    assert pending.confirmation_id is not None
    assert executed == []

    confirmed = await registry.execute_pending(pending.confirmation_id, context)
    assert confirmed is not None
    assert confirmed.status == "success"
    assert executed == ["owner"]
    assert await registry.execute_pending(pending.confirmation_id, context) is None
    assert executed == ["owner"]


def test_memory_context_is_scoped_per_user(isolated_sessions) -> None:
    from omka.app.services.memory_service import MemoryService

    MemoryService.create_memory(
        memory_type="user",
        subject="preference",
        content="用户 A 喜欢 Rust",
        scope="user",
        owner_external_id="user-a",
        conversation_id="conv-a",
    )
    MemoryService.create_memory(
        memory_type="user",
        subject="preference",
        content="用户 B 喜欢 Go",
        scope="user",
        owner_external_id="user-b",
    )

    visible = MemoryService.get_active_memories_for_context(
        owner_external_id="user-a",
        conversation_id="conv-b",
        query_text="喜欢",
        max_items=10,
    )

    assert [memory.content for memory in visible] == ["用户 A 喜欢 Rust"]

    MemoryService.create_memory(
        memory_type="conversation",
        subject="task",
        content="只属于 conv-a 的临时任务",
        scope="conversation",
        owner_external_id="user-a",
        conversation_id="conv-a",
    )
    other_conversation = MemoryService.get_active_memories_for_context(
        owner_external_id="user-a",
        conversation_id="conv-b",
        max_items=10,
    )
    assert "只属于 conv-a 的临时任务" not in {
        memory.content for memory in other_conversation
    }


@pytest.mark.asyncio
async def test_runtime_marks_confirmation_as_pending(isolated_sessions) -> None:
    registry = ToolRegistry()
    registry.register(
        AgentTool(
            name="test.confirmed_write",
            description="需要确认的测试工具",
            args_model=EmptyArgs,
            handler=lambda _args, _context: {"message": "done"},
            risk="destructive",
            requires_confirmation=True,
        )
    )
    runtime = KnowledgeAgentRuntime(
        planner=FakePlanner(
            [
                PlannerDecision(
                    kind="tool",
                    tool_name="test.confirmed_write",
                    arguments={},
                )
            ]
        ),
        tool_registry=registry,
        enable_memory_extraction=False,
    )
    response = await runtime.answer(
        AgentContext(
            user_message="执行测试写操作",
            conversation_id="confirm-conversation",
            user_external_id="owner",
        )
    )

    assert response.status == "needs_confirm"
    assert response.run_id is not None
    with isolated_sessions() as session:
        run = session.get(AgentRun, response.run_id)
    assert run is not None
    assert run.status == "needs_confirm"


@pytest.mark.asyncio
async def test_agent_goal_lifecycle_persists_result(
    isolated_sessions,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omka.app.services.agent_goal_service as goal_module
    from omka.app.services.agent_goal_service import AgentGoalService
    from omka.app.storage.db import ConversationMessage

    class FakeRuntime:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        @staticmethod
        def create_pending_run(**kwargs: Any) -> AgentRun:
            run = AgentRun(
                id=77,
                conversation_id=kwargs["conversation_id"],
                user_external_id=kwargs["user_external_id"],
                channel=kwargs["channel"],
                user_message=kwargs["user_message"],
                status="pending",
            )
            with isolated_sessions() as session:
                session.add(run)
                session.commit()
                session.refresh(run)
            return run

        async def execute(self, **kwargs: Any) -> AgentResponse:
            return AgentResponse(
                answer="已完成目标并生成摘要",
                used_context=[],
                suggested_actions=[],
                status="success",
                run_id=kwargs["run_id"],
            )

    async def build_context(_self: Any, **_kwargs: Any) -> AgentContext:
        return AgentContext(
            user_message="跟踪知识更新",
            conversation_id="goal-conversation",
            user_external_id="goal-owner",
        )

    monkeypatch.setattr(goal_module, "KnowledgeAgentRuntime", FakeRuntime)
    monkeypatch.setattr(goal_module.ContextBuilder, "build", build_context)

    goal = AgentGoalService.create_goal(
        owner_external_id="goal-owner",
        conversation_id="goal-conversation",
        objective="跟踪知识更新",
        max_steps=3,
    )
    assert goal.status == "active"

    completed = await AgentGoalService.run_goal(goal.id)

    assert completed.status == "completed"
    assert completed.last_run_id == 77
    assert completed.last_result_preview == "已完成目标并生成摘要"
    with isolated_sessions() as session:
        messages = session.exec(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == "goal-conversation"
            )
        ).all()
    assert [message.content for message in messages] == ["已完成目标并生成摘要"]


def test_feedback_memory_is_local_and_deduplicated(isolated_sessions) -> None:
    from omka.app.services.recommendation_service import RecommendationService
    from omka.app.storage.db import MemoryItem

    RecommendationService.record_feedback("candidate-missing", "confirm")
    RecommendationService.record_feedback("candidate-missing", "dislike")

    with isolated_sessions() as session:
        memories = session.exec(
            select(MemoryItem).where(MemoryItem.source_ref == "candidate-missing")
        ).all()
    assert len(memories) == 1
    assert memories[0].owner_external_id == "local"
    assert memories[0].metadata_json["feedback_type"] == "dislike"


def test_task_understanding_regression_scenarios_pass() -> None:
    from omka.app.agents.harness import AgentHarness

    results = AgentHarness()._run_scenarios()

    assert results
    assert all(result.passed for result in results), [
        result.model_dump() for result in results if not result.passed
    ]


def test_planner_extracts_json_decision_from_mixed_model_output() -> None:
    response = """我先检索知识库，再给出最终排序。

```json
{"kind":"tool","tool_name":"knowledge.search","arguments":{"query":"RAG"},
"decision_summary":"补充检索本地知识"}
```"""

    decision = LLMToolPlanner._parse_decision(response)

    assert decision.kind == "tool"
    assert decision.tool_name == "knowledge.search"
    assert decision.arguments == {"query": "RAG"}


@pytest.mark.asyncio
async def test_ambiguous_destructive_task_stops_for_clarification(
    isolated_sessions,
) -> None:
    runtime = KnowledgeAgentRuntime(
        planner=FakePlanner([]),
        tool_registry=ToolRegistry(),
        enable_memory_extraction=False,
    )

    response = await runtime.execute(
        user_message="删除一下",
        conversation_id="clarify-conversation",
        user_external_id="owner",
    )

    assert response.status == "needs_clarification"
    assert "对象和范围" in response.answer
    with isolated_sessions() as session:
        run = session.get(AgentRun, response.run_id)
        steps = session.exec(
            select(AgentStep)
            .where(AgentStep.run_id == response.run_id)
            .order_by(AgentStep.step_index)
        ).all()
    assert run is not None
    assert run.used_context_json["task_brief"]["risk"] == "destructive"
    assert [step.tool_name for step in steps] == [
        "understanding.task",
        "response.final",
    ]


def test_profile_snapshot_exposes_evidence_and_confirmation(
    isolated_sessions,
) -> None:
    from omka.app.services.memory_service import MemoryService
    from omka.app.services.user_profile_service import UserProfileService

    memory = MemoryService.create_memory(
        memory_type="conversation",
        subject="preference",
        content="回答时先给结论，再给三条依据",
        scope="user",
        owner_external_id="profile-owner",
        source_type="conversation",
        confidence=0.88,
        status="candidate",
    )
    candidate_snapshot = UserProfileService.build_snapshot("profile-owner")
    facet = next(
        item
        for item in candidate_snapshot.facets
        if item.memory_id == memory.id
    )
    assert facet.state == "review"
    assert facet.evidence[0].source_type == "conversation"

    MemoryService.confirm_memory(memory.id, actor_id="profile-owner")
    confirmed_snapshot = UserProfileService.build_snapshot("profile-owner")
    confirmed = next(
        item
        for item in confirmed_snapshot.facets
        if item.memory_id == memory.id
    )
    assert confirmed.state == "verified"
    assert confirmed.confidence >= 0.92


def test_harness_reports_understanding_and_trace_coverage(
    isolated_sessions,
) -> None:
    from omka.app.agents.harness import AgentHarness
    from omka.app.agents.task_understanding import HeuristicTaskInterpreter

    brief = HeuristicTaskInterpreter().interpret("查找我收藏过的 RAG 知识")
    with isolated_sessions() as session:
        run = AgentRun(
            conversation_id="harness",
            user_external_id="owner",
            channel="test",
            user_message="查找我收藏过的 RAG 知识",
            answer_preview="找到一条 [knowledge:item-1]",
            status="success",
            latency_ms=120,
            used_context_json={
                "task_brief": brief.model_dump(mode="json"),
                "used": [{"type": "knowledge", "count": "1"}],
            },
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.id is not None
        for index, (step_type, stage) in enumerate(
            (
                ("understanding", "understanding.task"),
                ("context", "context.assemble"),
                ("decision", "planner.decide"),
                ("final", "response.final"),
            )
        ):
            session.add(
                AgentStep(
                    run_id=run.id,
                    step_index=index,
                    step_type=step_type,
                    tool_name=stage,
                    output_json=(
                        {"answer": "找到一条 [knowledge:item-1]"}
                        if step_type == "final"
                        else {}
                    ),
                )
            )
        session.commit()

    summary = AgentHarness().summarize()

    assert summary.scenario_pass_rate == 1
    assert summary.understanding_coverage == 1
    assert summary.trace_coverage == 1
    assert summary.grounding_rate == 1
