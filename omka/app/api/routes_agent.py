from fastapi import APIRouter
from pydantic import BaseModel

from omka.app.agents.context_builder import ContextBuilder
from omka.app.agents.simple_knowledge_agent import SimpleKnowledgeAgent
from omka.app.core.config import settings
from omka.app.core.logging import logger

router = APIRouter()


class AgentTestRequest(BaseModel):
    message: str


class AgentTestResponse(BaseModel):
    answer: str
    used_context: list[dict]
    suggested_actions: list[str]
    status: str


@router.post("/test", response_model=AgentTestResponse)
async def test_agent(request: AgentTestRequest):
    if not settings.omka_agent_chat_enabled:
        return AgentTestResponse(
            answer="Agent 对话能力未启用",
            used_context=[],
            suggested_actions=[],
            status="disabled",
        )

    try:
        context_builder = ContextBuilder(
            max_recent_messages=settings.omka_agent_max_recent_messages,
            max_digest_items=settings.omka_agent_max_digest_items,
            max_knowledge_items=settings.omka_agent_max_knowledge_items,
            max_candidate_items=settings.omka_agent_max_candidate_items,
            max_context_chars=settings.omka_agent_max_context_chars,
        )

        context = await context_builder.build(
            user_message=request.message,
            conversation_id="test",
            user_external_id="test",
        )

        agent = SimpleKnowledgeAgent()
        response = await agent.answer(context)

        return AgentTestResponse(
            answer=response.answer,
            used_context=response.used_context,
            suggested_actions=response.suggested_actions,
            status="success",
        )
    except Exception as e:
        logger.error("Agent 测试失败 | error=%s", e)
        return AgentTestResponse(
            answer=f"Agent 测试失败: {str(e)}",
            used_context=[],
            suggested_actions=[],
            status="error",
        )
