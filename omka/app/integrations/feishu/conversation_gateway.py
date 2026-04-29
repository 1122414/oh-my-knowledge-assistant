from abc import ABC, abstractmethod

from omka.app.core.logging import logger


class FeishuConversationGateway(ABC):
    """飞书对话网关抽象接口

    为后续接入后端 Agent 预留扩展接口。
    """

    @abstractmethod
    async def handle_user_message(
        self,
        user_id: str,
        chat_id: str,
        message: str,
        context: dict | None = None,
    ) -> str:
        """处理用户消息并返回回复

        Args:
            user_id: 用户 ID
            chat_id: 群聊 ID
            message: 消息内容
            context: 额外上下文

        Returns:
            回复消息
        """
        raise NotImplementedError


class DisabledFeishuConversationGateway(FeishuConversationGateway):
    """禁用状态的对话网关

    当 FEISHU_AGENT_CONVERSATION_ENABLED=false 时使用。
    """

    async def handle_user_message(
        self,
        user_id: str,
        chat_id: str,
        message: str,
        context: dict | None = None,
    ) -> str:
        logger.debug("飞书对话网关已禁用 | user_id=%s", user_id)
        return "Agent 对话能力暂未开启，请在设置中启用 FEISHU_AGENT_CONVERSATION_ENABLED 后使用。"
