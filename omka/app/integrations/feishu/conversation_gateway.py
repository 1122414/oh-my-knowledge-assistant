import asyncio
from abc import ABC, abstractmethod
from datetime import datetime

from omka.app.agents.base import AgentContext
from omka.app.agents.context_builder import ContextBuilder
from omka.app.agents.simple_knowledge_agent import SimpleKnowledgeAgent
from omka.app.core.config import settings
from omka.app.core.logging import TraceContext, get_logger, trace
from omka.app.storage.db import AgentRun, ConversationMessage, get_session

logger = get_logger("feishu")


class FeishuConversationGateway(ABC):

    @abstractmethod
    async def handle_user_message(
        self,
        user_id: str,
        chat_id: str,
        message: str,
        context: dict | None = None,
    ) -> str:
        raise NotImplementedError


class DisabledFeishuConversationGateway(FeishuConversationGateway):

    async def handle_user_message(
        self,
        user_id: str,
        chat_id: str,
        message: str,
        context: dict | None = None,
    ) -> str:
        logger.debug("飞书对话网关已禁用 | user_id=%s", user_id)
        return "Agent 对话能力暂未开启，请在设置中启用 FEISHU_AGENT_CONVERSATION_ENABLED 后使用。"


class SimpleKnowledgeAgentGateway(FeishuConversationGateway):

    def __init__(self):
        self._agent = SimpleKnowledgeAgent()
        self._context_builder = ContextBuilder(
            max_recent_messages=settings.omka_agent_max_recent_messages,
            max_digest_items=settings.omka_agent_max_digest_items,
            max_knowledge_items=settings.omka_agent_max_knowledge_items,
            max_candidate_items=settings.omka_agent_max_candidate_items,
            max_context_chars=settings.omka_agent_max_context_chars,
        )

    @trace("feishu")
    async def handle_user_message(
        self,
        user_id: str,
        chat_id: str,
        message: str,
        context: dict | None = None,
    ) -> str:
        logger.info("开始处理用户消息 | user_id=%s | chat_id=%s", user_id, chat_id)
        self._save_message(chat_id, user_id, "user", message)

        logger.info("构建 Agent 上下文...")
        agent_context = await self._context_builder.build(
            user_message=message,
            conversation_id=chat_id,
            user_external_id=user_id,
        )
        logger.info("上下文构建完成 | recent=%d | digest=%d | knowledge=%d | candidate=%d",
                    len(agent_context.recent_messages),
                    len(agent_context.digest_items),
                    len(agent_context.knowledge_items),
                    len(agent_context.candidate_items))

        start_time = datetime.utcnow()
        agent_timeout = settings.omka_agent_timeout_seconds or 25
        logger.info("调用 Agent | timeout=%ds", agent_timeout)
        try:
            response = await asyncio.wait_for(
                self._agent.answer(agent_context),
                timeout=agent_timeout
            )
            logger.info("Agent 返回成功 | answer_length=%d", len(response.answer))
        except asyncio.TimeoutError:
            logger.error("Agent 回答超时 | timeout=%ds", agent_timeout)
            return "抱歉，处理你的问题时超时了。请稍后再试，或发送 /omka help 查看可用命令。"
        latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        self._save_message(chat_id, user_id, "assistant", response.answer)
        self._save_agent_run(chat_id, user_id, message, response, latency_ms)

        return response.answer

    def _save_message(self, conversation_id: str, user_external_id: str, role: str, content: str) -> None:
        try:
            with get_session() as session:
                msg = ConversationMessage(
                    channel="feishu",
                    conversation_id=conversation_id,
                    user_external_id=user_external_id,
                    role=role,
                    content=content,
                )
                session.add(msg)
                session.commit()
        except Exception as e:
            logger.error("保存对话消息失败 | error=%s", e)

    def _save_agent_run(
        self,
        conversation_id: str,
        user_external_id: str,
        user_message: str,
        response: "AgentResponse",
        latency_ms: int,
    ) -> None:
        try:
            with get_session() as session:
                run = AgentRun(
                    conversation_id=conversation_id,
                    user_external_id=user_external_id,
                    channel="feishu",
                    user_message=user_message,
                    answer_preview=response.answer[:200],
                    model=settings.omka_agent_model or settings.llm_model,
                    status="success",
                    latency_ms=latency_ms,
                    used_context_json={"used_context": response.used_context},
                )
                session.add(run)
                session.commit()
        except Exception as e:
            logger.error("保存 Agent 调用记录失败 | error=%s", e)
