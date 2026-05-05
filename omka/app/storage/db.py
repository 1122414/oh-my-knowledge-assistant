"""OMKA 数据库配置与模型定义

使用 SQLModel 作为 ORM，SQLite 作为数据库。
所有模型继承 SQLModel，支持 Pydantic 验证。
"""

from datetime import datetime

from sqlalchemy import JSON, Column, text
from sqlmodel import Field, Session, SQLModel, create_engine

from omka.app.core.config import settings
from omka.app.core.logging import logger

# 创建数据库引擎
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)


class BaseSchema(SQLModel):
    """基础模型混入类"""

    model_config = {"arbitrary_types_allowed": True}


# ===========================================
# 数据源配置表
# ===========================================
class SourceConfig(BaseSchema, table=True):
    """用户配置的数据源"""

    __tablename__ = "source_configs"

    id: str = Field(primary_key=True, description="数据源唯一标识")
    source_type: str = Field(description="数据源类型，如 github")
    name: str = Field(description="数据源显示名称")
    enabled: bool = Field(default=True, description="是否启用")

    mode: str = Field(description="模式: repo 或 search")

    # repo 模式
    repo_full_name: str | None = Field(default=None, description="仓库全名，如 owner/repo")

    # search 模式
    query: str | None = Field(default=None, description="搜索查询词")
    limit: int = Field(default=5, description="返回结果数量限制")

    weight: float = Field(default=1.0, description="数据源权重")

    last_fetched_at: datetime | None = Field(default=None, description="上次抓取时间")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")


# ===========================================
# 抓取运行记录表
# ===========================================
class FetchRun(BaseSchema, table=True):
    """每次抓取任务的运行记录"""

    __tablename__ = "fetch_runs"

    id: int | None = Field(default=None, primary_key=True)
    job_type: str = Field(default="github_daily", description="任务类型: github_daily/manual_run/digest_generation/feishu_push")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="开始时间")
    finished_at: datetime | None = Field(default=None, description="结束时间")
    status: str = Field(default="running", description="状态: running/success/partial_success/failed")
    fetched_count: int = Field(default=0, description="抓取条目数（兼容旧数据）")
    fetched_repo_count: int = Field(default=0, description="抓取仓库数")
    fetched_release_count: int = Field(default=0, description="抓取 Release 数")
    fetched_search_result_count: int = Field(default=0, description="抓取搜索结果数")
    normalized_count: int = Field(default=0, description="规范化条目数")
    candidate_count: int = Field(default=0, description="候选条目数")
    digest_item_count: int = Field(default=0, description="Digest 条目数")
    error_count: int = Field(default=0, description="错误数")
    error_message: str | None = Field(default=None, description="错误信息")
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="额外元数据")


# ===========================================
# 原始抓取数据表
# ===========================================
class RawItem(BaseSchema, table=True):
    """GitHub API 原始抓取结果"""

    __tablename__ = "raw_items"

    id: str = Field(primary_key=True, description="唯一标识")
    source_id: str = Field(description="关联的 SourceConfig ID")
    source_type: str = Field(description="数据源类型")
    item_type: str = Field(description="条目类型: github_repo/github_release/github_repo_search_result")

    fetch_url: str = Field(description="请求 URL")
    http_status: int = Field(description="HTTP 状态码")

    raw_data: dict = Field(default_factory=dict, sa_column=Column(JSON), description="原始 JSON 数据")

    etag: str | None = Field(default=None, description="ETag")
    last_modified: str | None = Field(default=None, description="Last-Modified")

    fetched_at: datetime = Field(default_factory=datetime.utcnow, description="抓取时间")


# ===========================================
# 规范化数据表
# ===========================================
class NormalizedItem(BaseSchema, table=True):
    """统一结构化的知识条目"""

    __tablename__ = "normalized_items"

    id: str = Field(primary_key=True, description="唯一标识")
    source_type: str = Field(description="数据源类型")
    source_id: str = Field(description="关联 SourceConfig ID")
    item_type: str = Field(description="条目类型: repo/release/repo_search_result")

    title: str = Field(description="标题")
    url: str = Field(description="链接")
    content: str = Field(description="正文内容")

    author: str | None = Field(default=None, description="作者")
    repo_full_name: str | None = Field(default=None, description="仓库全名")

    published_at: datetime | None = Field(default=None, description="发布时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")
    fetched_at: datetime = Field(default_factory=datetime.utcnow, description="抓取时间")

    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON), description="标签列表")
    item_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON), description="元数据")
    content_hash: str = Field(description="内容指纹，用于去重")


# ===========================================
# 候选推荐表
# ===========================================
class CandidateItem(BaseSchema, table=True):
    """进入每日简报前的候选条目"""

    __tablename__ = "candidate_items"

    id: str = Field(primary_key=True, description="唯一标识")
    normalized_item_id: str = Field(description="关联 NormalizedItem ID")

    title: str = Field(description="标题")
    url: str = Field(description="链接")
    item_type: str = Field(description="条目类型")

    summary: str | None = Field(default=None, description="摘要")
    recommendation_reason: str | None = Field(default=None, description="推荐理由")

    score: float = Field(default=0.0, description="综合得分")
    score_detail: dict = Field(default_factory=dict, sa_column=Column(JSON), description="分数明细")

    matched_interests: list[str] = Field(default_factory=list, sa_column=Column(JSON), description="匹配的兴趣")
    matched_projects: list[str] = Field(default_factory=list, sa_column=Column(JSON), description="匹配的项目")

    status: str = Field(default="pending", description="状态: pending/confirmed/ignored/disliked/read_later")

    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")


# ===========================================
# 知识库表
# ===========================================
class KnowledgeItem(BaseSchema, table=True):
    """用户确认后的正式知识条目"""

    __tablename__ = "knowledge_items"

    id: str = Field(primary_key=True, description="唯一标识")
    candidate_item_id: str = Field(description="来源 CandidateItem ID")

    title: str = Field(description="标题")
    url: str = Field(description="链接")
    item_type: str = Field(description="条目类型")
    content: str = Field(description="正文")

    summary: str | None = Field(default=None, description="摘要")
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON), description="标签")
    item_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON), description="元数据")

    # 知识图谱预留字段
    entities: list[str] = Field(default_factory=list, sa_column=Column(JSON), description="实体")
    relations: list[dict] = Field(default_factory=list, sa_column=Column(JSON), description="关系")
    related_projects: list[str] = Field(default_factory=list, sa_column=Column(JSON), description="相关项目")

    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")


# ===========================================
# 用户反馈表
# ===========================================
class UserFeedback(BaseSchema, table=True):
    """用户对候选条目的反馈"""

    __tablename__ = "user_feedback"

    id: int | None = Field(default=None, primary_key=True)
    candidate_item_id: str = Field(description="关联 CandidateItem ID")
    feedback_type: str = Field(description="反馈类型: confirm/ignore/not_interested/read_later")
    notes: str | None = Field(default=None, description="备注")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="反馈时间")


# ===========================================
# 应用配置表（运行时动态配置，优先级高于 .env）
# ===========================================
class AppSetting(BaseSchema, table=True):
    """应用运行时配置，支持 UI 动态修改"""

    __tablename__ = "app_settings"

    key: str = Field(primary_key=True, description="配置键名")
    value: str = Field(description="配置值（JSON 字符串或纯文本）")
    is_secret: bool = Field(default=False, description="是否为敏感字段")
    category: str = Field(default="general", description="分类: general/github/llm/feishu/scheduler")
    description: str | None = Field(default=None, description="配置说明")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")


# ===========================================
# 通知推送记录表
# ===========================================
class NotificationRun(BaseSchema, table=True):
    """通知推送运行记录"""

    __tablename__ = "notification_runs"

    id: int | None = Field(default=None, primary_key=True)
    channel_type: str = Field(description="通知渠道: feishu_webhook/feishu_app_bot/email/telegram")
    job_id: int | None = Field(default=None, description="关联 FetchRun ID")
    digest_id: str | None = Field(default=None, description="关联 Digest ID")
    status: str = Field(default="running", description="状态: success/failed/skipped")
    sent_at: datetime | None = Field(default=None, description="发送时间")
    error_message: str | None = Field(default=None, description="错误信息")
    response_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="渠道响应")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# ===========================================
# 飞书消息发送记录表
# ===========================================
class FeishuMessageRun(BaseSchema, table=True):
    """飞书消息发送记录"""

    __tablename__ = "feishu_message_runs"

    id: int | None = Field(default=None, primary_key=True)
    message_type: str = Field(description="消息类型: test/digest/reply/command_result")
    receive_id_type: str = Field(description="接收者类型: chat_id/open_id/user_id/email")
    receive_id_masked: str = Field(description="接收者 ID（脱敏）")
    status: str = Field(default="pending", description="状态: success/failed/skipped")
    message_id: str | None = Field(default=None, description="飞书消息 ID")
    error_code: str | None = Field(default=None, description="错误码")
    error_message: str | None = Field(default=None, description="错误信息")
    request_id: str | None = Field(default=None, description="请求 ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="额外元数据")


# ===========================================
# 飞书事件日志表
# ===========================================
class FeishuEventLog(BaseSchema, table=True):
    """飞书事件接收日志"""

    __tablename__ = "feishu_event_logs"

    id: int | None = Field(default=None, primary_key=True)
    event_id: str = Field(description="事件 ID")
    event_type: str = Field(description="事件类型")
    chat_id: str | None = Field(default=None, description="群聊 ID")
    sender_id: str | None = Field(default=None, description="发送者 ID")
    message_id: str | None = Field(default=None, description="消息 ID")
    message_type: str | None = Field(default=None, description="消息类型")
    raw_event_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="原始事件数据")
    handled_status: str = Field(default="received", description="处理状态: received/ignored/routed/failed")
    error_message: str | None = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# ===========================================
# 飞书单聊绑定表
# ===========================================
class FeishuDirectConversation(BaseSchema, table=True):
    """飞书单聊绑定"""

    __tablename__ = "feishu_direct_conversations"

    id: int | None = Field(default=None, primary_key=True)
    open_id: str = Field(description="用户 open_id")
    chat_id: str = Field(description="单聊 chat_id")
    enabled: bool = Field(default=True, description="是否启用")
    is_default: bool = Field(default=False, description="是否默认推送目标")
    last_message_at: datetime | None = Field(default=None, description="最后消息时间")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")


# ===========================================
# 对话消息历史表
# ===========================================
class ConversationMessage(BaseSchema, table=True):
    """对话消息历史"""

    __tablename__ = "conversation_messages"

    id: int | None = Field(default=None, primary_key=True)
    channel: str = Field(default="feishu", description="渠道")
    conversation_id: str = Field(description="会话 ID（chat_id）")
    user_external_id: str = Field(description="用户外部 ID（open_id）")
    role: str = Field(description="角色: user/assistant/system")
    content: str = Field(description="消息内容")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# ===========================================
# Agent 调用记录表
# ===========================================
class AgentRun(BaseSchema, table=True):
    """Agent 调用记录"""

    __tablename__ = "agent_runs"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(description="会话 ID")
    user_external_id: str = Field(description="用户外部 ID")
    channel: str = Field(default="feishu", description="渠道")
    user_message: str = Field(description="用户消息")
    answer_preview: str = Field(default="", description="回答预览")
    model: str = Field(default="", description="使用的模型")
    status: str = Field(default="pending", description="状态: success/failed/skipped")
    latency_ms: int = Field(default=0, description="耗时（毫秒）")
    used_context_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="使用的上下文")
    error_message: str | None = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# ===========================================
# 记忆条目表
# ===========================================
class MemoryItem(BaseSchema, table=True):
    """统一记忆条目：用户记忆、对话记忆、系统记忆"""

    __tablename__ = "memory_items"

    id: str = Field(primary_key=True, description="唯一标识")
    memory_type: str = Field(description="记忆类型: user / conversation / system")
    scope: str = Field(default="global", description="作用域: global / user / conversation / source / project")
    subject: str = Field(description="主题: user_profile / project / preference / task / setting / status")
    content: str = Field(description="记忆内容")
    summary: str | None = Field(default=None, description="摘要")
    source_type: str = Field(default="manual", description="来源: manual / conversation / feedback / system_event / import")
    source_ref: str | None = Field(default=None, description="来源引用")
    confidence: float = Field(default=0.8, description="置信度")
    importance: float = Field(default=0.5, description="重要性")
    status: str = Field(default="active", description="状态: candidate / active / archived / rejected / expired")
    visibility: str = Field(default="private", description="可见性: private / shared")
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON), description="标签")
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="元数据")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    last_used_at: datetime | None = Field(default=None, description="最后使用时间")
    expires_at: datetime | None = Field(default=None, description="过期时间")


# ===========================================
# 记忆事件表
# ===========================================
class MemoryEvent(BaseSchema, table=True):
    """记忆变更事件日志"""

    __tablename__ = "memory_events"

    id: int | None = Field(default=None, primary_key=True)
    memory_id: str = Field(description="关联 MemoryItem ID")
    event_type: str = Field(description="事件类型: created / confirmed / edited / used / rejected / expired")
    actor_type: str = Field(default="system", description="操作者类型: user / agent / system")
    actor_id: str | None = Field(default=None, description="操作者 ID")
    detail_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="详情")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# ===========================================
# 推荐运行记录表
# ===========================================
class RecommendationRun(BaseSchema, table=True):
    """推荐运行记录"""

    __tablename__ = "recommendation_runs"

    id: int | None = Field(default=None, primary_key=True)
    trigger_type: str = Field(description="触发类型: daily / manual / feishu_query / push")
    user_external_id: str | None = Field(default=None, description="用户外部 ID")
    candidate_count: int = Field(default=0, description="候选数量")
    selected_count: int = Field(default=0, description="选中数量")
    strategy: str = Field(default="default", description="策略名称")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="元数据")


# ===========================================
# 推荐决策表
# ===========================================
class RecommendationDecision(BaseSchema, table=True):
    """推荐决策记录"""

    __tablename__ = "recommendation_decisions"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(description="关联 RecommendationRun ID")
    candidate_item_id: str = Field(description="关联 CandidateItem ID")
    final_score: float = Field(description="最终得分")
    rank: int = Field(description="排名")
    explanation: str = Field(description="推荐解释文本")
    explanation_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="结构化解释")
    action_hint: str | None = Field(default=None, description="建议操作")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# ===========================================
# 系统操作审计表
# ===========================================
class SystemAction(BaseSchema, table=True):
    """Agent 系统操作审计日志"""

    __tablename__ = "system_actions"

    id: int | None = Field(default=None, primary_key=True)
    action_type: str = Field(description="操作类型: source.create / candidate.confirm / memory.delete 等")
    actor_channel: str = Field(default="feishu", description="操作渠道")
    actor_external_id: str = Field(description="操作者外部 ID")
    permission_level: str = Field(default="viewer", description="权限级别: viewer / operator / admin")
    target_type: str = Field(description="目标类型: source / candidate / knowledge / memory / config / push / job")
    target_id: str | None = Field(default=None, description="目标 ID")
    request_text: str | None = Field(default=None, description="原始请求文本")
    params_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="参数")
    status: str = Field(default="pending", description="状态: pending / success / failed / denied / needs_confirm")
    result_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="结果")
    error_message: str | None = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    confirmed_at: datetime | None = Field(default=None, description="确认时间")


# ===========================================
# 推送策略表
# ===========================================
class PushPolicy(BaseSchema, table=True):
    """主动推送策略配置"""

    __tablename__ = "push_policies"

    id: str = Field(primary_key=True, description="策略唯一标识")
    name: str = Field(description="策略名称")
    enabled: bool = Field(default=True, description="是否启用")
    channel: str = Field(default="feishu", description="推送渠道")
    trigger_type: str = Field(description="触发类型: daily / high_score / reminder / system_alert")
    threshold: float | None = Field(default=None, description="分数阈值")
    quiet_hours_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="安静时间配置")
    max_per_day: int = Field(default=5, description="每日最大推送次数")
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="元数据")


# ===========================================
# 推送事件表
# ===========================================
class PushEvent(BaseSchema, table=True):
    """推送事件记录"""

    __tablename__ = "push_events"

    id: int | None = Field(default=None, primary_key=True)
    policy_id: str = Field(description="关联 PushPolicy ID")
    channel: str = Field(description="推送渠道")
    target_id: str = Field(description="目标 ID")
    title: str = Field(description="标题")
    content: str = Field(description="内容")
    status: str = Field(default="pending", description="状态: pending / sent / failed / skipped")
    reason: str | None = Field(default=None, description="跳过/失败原因")
    related_candidate_id: str | None = Field(default=None, description="关联候选 ID")
    related_memory_id: str | None = Field(default=None, description="关联记忆 ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    sent_at: datetime | None = Field(default=None, description="发送时间")
    response_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="响应")


# ===========================================
# 知识资产表
# ===========================================
class KnowledgeAsset(BaseSchema, table=True):
    """多模态知识资产"""

    __tablename__ = "knowledge_assets"

    id: str = Field(primary_key=True, description="唯一标识")
    asset_type: str = Field(description="资产类型: image / pdf / doc / sheet / ppt / webpage / text")
    title: str = Field(description="标题")
    source_type: str = Field(default="upload", description="来源: upload / feishu / url / github / manual")
    source_ref: str | None = Field(default=None, description="来源引用")
    file_path: str | None = Field(default=None, description="文件路径")
    original_filename: str | None = Field(default=None, description="原始文件名")
    mime_type: str | None = Field(default=None, description="MIME 类型")
    size_bytes: int | None = Field(default=None, description="文件大小")
    content_hash: str = Field(description="内容哈希")
    status: str = Field(default="uploaded", description="状态: uploaded / processing / processed / failed / archived")
    extracted_text: str | None = Field(default=None, description="提取的文本")
    summary: str | None = Field(default=None, description="摘要")
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON), description="标签")
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="元数据")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")


# ===========================================
# 数据库初始化
# ===========================================
def _migrate_fetch_runs(engine) -> None:
    """迁移 fetch_runs 表，添加缺失的列"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(fetch_runs)"))
            existing_columns = {row[1] for row in result}

            columns_to_add = [
                ("fetched_repo_count", "INTEGER DEFAULT 0"),
                ("fetched_release_count", "INTEGER DEFAULT 0"),
                ("fetched_search_result_count", "INTEGER DEFAULT 0"),
                ("normalized_count", "INTEGER DEFAULT 0"),
                ("digest_item_count", "INTEGER DEFAULT 0"),
                ("error_count", "INTEGER DEFAULT 0"),
                ("error_message", "TEXT"),
                ("metadata_json", "TEXT DEFAULT '{}'"),
            ]

            for col_name, col_type in columns_to_add:
                if col_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE fetch_runs ADD COLUMN {col_name} {col_type}"))
                    logger.info("迁移 fetch_runs 表 | 添加列: %s", col_name)

            conn.commit()
    except Exception as e:
        logger.debug("迁移 fetch_runs 表跳过（可能表不存在）| error=%s", e)


def init_db() -> None:
    """初始化数据库，创建所有表"""
    SQLModel.metadata.create_all(engine)
    _migrate_fetch_runs(engine)
    logger.info("数据库初始化完成 | 路径=%s", settings.database_url)


def get_session() -> Session:
    """获取数据库会话"""
    return Session(engine)
