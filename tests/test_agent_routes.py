from __future__ import annotations

from typing import Any

import pytest

from omka.app.agents.base import AgentContext, AgentResponse
from omka.app.api import routes_agent


@pytest.mark.asyncio
async def test_agent_test_uses_runtime_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeContextBuilder:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def build(self, **kwargs: Any) -> AgentContext:
            return AgentContext(
                user_message=kwargs["user_message"],
                conversation_id=kwargs["conversation_id"],
                user_external_id=kwargs["user_external_id"],
            )

    class FakeRuntime:
        async def execute(self, **kwargs: Any) -> AgentResponse:
            return AgentResponse(
                answer=f"收到：{kwargs['user_message']}",
                used_context=[],
                suggested_actions=[],
                status="success",
                run_id=42,
            )

    monkeypatch.setattr(
        routes_agent,
        "get_setting",
        lambda key, default=None: True
        if key == "omka_agent_chat_enabled"
        else default,
    )
    monkeypatch.setattr(routes_agent, "ContextBuilder", FakeContextBuilder)
    monkeypatch.setattr(routes_agent, "KnowledgeAgentRuntime", FakeRuntime)

    response = await routes_agent.test_agent(
        routes_agent.AgentTestRequest(message="你好")
    )

    assert response.status == "success"
    assert response.answer == "收到：你好"
    assert response.run_id == 42


@pytest.mark.asyncio
async def test_agent_test_returns_disabled_when_runtime_setting_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes_agent,
        "get_setting",
        lambda key, default=None: False
        if key == "omka_agent_chat_enabled"
        else default,
    )

    response = await routes_agent.test_agent(
        routes_agent.AgentTestRequest(message="你好")
    )

    assert response.status == "disabled"
    assert response.answer == "Agent 对话能力未启用"
