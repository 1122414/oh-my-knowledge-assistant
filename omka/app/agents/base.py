from abc import ABC, abstractmethod

from typing import Any

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Agent 上下文"""

    user_message: str = Field(description="用户消息")
    conversation_id: str = Field(description="会话 ID（chat_id）")
    user_external_id: str = Field(description="用户外部 ID（open_id）")
    recent_messages: list[dict[str, str]] = Field(default_factory=list, description="最近对话消息")
    digest_items: list[dict[str, str]] = Field(default_factory=list, description="最新 Digest 条目")
    knowledge_items: list[dict[str, str]] = Field(default_factory=list, description="已收藏知识")
    candidate_items: list[dict[str, str]] = Field(default_factory=list, description="候选内容")
    memory_items: list[dict[str, str]] = Field(default_factory=list, description="活跃记忆")
    user_profile: dict[str, Any] = Field(default_factory=dict, description="证据驱动的用户画像")
    task_brief: dict[str, Any] = Field(default_factory=dict, description="结构化任务理解")


class AgentResponse(BaseModel):
    """Agent 响应"""

    answer: str = Field(description="回答文本")
    used_context: list[dict[str, str]] = Field(default_factory=list, description="使用的上下文")
    suggested_actions: list[str] = Field(default_factory=list, description="建议的下一步动作")
    run_id: int | None = Field(default=None, description="关联 AgentRun ID")
    status: str = Field(default="success", description="运行状态")


class BaseAgent(ABC):
    """Agent 基类"""

    @abstractmethod
    async def answer(self, context: AgentContext) -> AgentResponse:
        """根据上下文生成回答

        Args:
            context: Agent 上下文

        Returns:
            Agent 响应
        """
        raise NotImplementedError
