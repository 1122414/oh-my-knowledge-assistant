from pydantic import BaseModel, Field


class FeishuConfig(BaseModel):
    """飞书应用机器人配置"""

    enabled: bool = Field(default=False, description="是否启用飞书应用机器人")

    app_id: str = Field(default="", description="飞书应用 App ID")
    app_secret: str = Field(default="", description="飞书应用 App Secret")

    verification_token: str = Field(default="", description="事件订阅验证 Token")
    encrypt_key: str = Field(default="", description="事件订阅加密 Key")

    api_base_url: str = Field(
        default="https://open.feishu.cn/open-apis",
        description="飞书 API 基础 URL",
    )
    request_timeout_seconds: int = Field(default=10, description="请求超时（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")

    default_receive_id_type: str = Field(
        default="chat_id",
        description="默认接收者类型: chat_id, open_id, user_id, email",
    )
    default_chat_id: str = Field(default="", description="默认群聊 ID")

    command_prefix: str = Field(default="/omka", description="命令前缀")
    require_mention: bool = Field(default=True, description="群聊中是否需要 @ 机器人")
    group_allowlist: list[str] = Field(default_factory=list, description="允许的群聊 ID 列表")
    user_allowlist: list[str] = Field(default_factory=list, description="允许的用户 ID 列表")

    push_digest_enabled: bool = Field(default=True, description="是否推送每日简报")
    push_digest_top_n: int = Field(default=6, description="推送简报条目数")

    event_callback_path: str = Field(
        default="/api/integrations/feishu/events",
        description="事件回调路径",
    )
    public_callback_url: str = Field(default="", description="公开回调 URL")

    agent_conversation_enabled: bool = Field(default=False, description="是否启用 Agent 对话")
    agent_session_ttl_minutes: int = Field(default=60, description="Agent 会话 TTL（分钟）")
    agent_max_message_chars: int = Field(default=4000, description="Agent 消息最大字符数")

    auto_bind_direct_chat: bool = Field(default=True, description="自动绑定单聊会话")

    doc_folder_token: str = Field(default="", description="云文档默认文件夹 token")
    base_folder_token: str = Field(default="", description="多维表格默认文件夹 token")
    sheet_folder_token: str = Field(default="", description="电子表格默认文件夹 token")
    default_calendar_id: str = Field(default="", description="默认日历 ID")

    def is_configured(self) -> bool:
        """检查是否已配置必要的凭证"""
        return bool(self.app_id and self.app_secret)

    def get_masked_config(self) -> dict:
        """返回脱敏后的配置"""
        return {
            "enabled": self.enabled,
            "app_id": self.app_id,
            "app_secret": "****" if self.app_secret else "",
            "verification_token": "****" if self.verification_token else "",
            "encrypt_key": "****" if self.encrypt_key else "",
            "api_base_url": self.api_base_url,
            "request_timeout_seconds": self.request_timeout_seconds,
            "max_retries": self.max_retries,
            "default_receive_id_type": self.default_receive_id_type,
            "default_chat_id": self.default_chat_id,
            "command_prefix": self.command_prefix,
            "require_mention": self.require_mention,
            "group_allowlist": self.group_allowlist,
            "user_allowlist": self.user_allowlist,
            "push_digest_enabled": self.push_digest_enabled,
            "push_digest_top_n": self.push_digest_top_n,
            "event_callback_path": self.event_callback_path,
            "public_callback_url": self.public_callback_url,
            "agent_conversation_enabled": self.agent_conversation_enabled,
            "agent_session_ttl_minutes": self.agent_session_ttl_minutes,
            "agent_max_message_chars": self.agent_max_message_chars,
            "doc_folder_token": self.doc_folder_token,
            "base_folder_token": self.base_folder_token,
            "sheet_folder_token": self.sheet_folder_token,
            "default_calendar_id": self.default_calendar_id,
        }
