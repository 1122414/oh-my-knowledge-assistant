"""OMKA 数据库配置与模型定义

使用 SQLModel 作为 ORM，SQLite 作为数据库。
所有模型继承 SQLModel，支持 Pydantic 验证。
"""

from datetime import datetime
from typing import Literal

from sqlalchemy import JSON, Column
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
# 请求缓存表（ETag / Last-Modified）
# ===========================================
class RequestCache(BaseSchema, table=True):
    """HTTP 请求缓存，用于条件请求"""

    __tablename__ = "request_cache"

    id: int | None = Field(default=None, primary_key=True)
    request_url: str = Field(description="请求 URL")
    etag: str | None = Field(default=None, description="ETag 响应头")
    last_modified: str | None = Field(default=None, description="Last-Modified 响应头")
    last_status: int = Field(description="上次响应状态码")
    last_fetched_at: datetime = Field(default_factory=datetime.utcnow, description="上次请求时间")


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
    channel_type: str = Field(description="通知渠道: feishu_webhook/email/telegram")
    job_id: int | None = Field(default=None, description="关联 FetchRun ID")
    digest_id: str | None = Field(default=None, description="关联 Digest ID")
    status: str = Field(default="running", description="状态: success/failed/skipped")
    sent_at: datetime | None = Field(default=None, description="发送时间")
    error_message: str | None = Field(default=None, description="错误信息")
    response_json: dict = Field(default_factory=dict, sa_column=Column(JSON), description="渠道响应")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# ===========================================
# 数据库初始化
# ===========================================
def init_db() -> None:
    """初始化数据库，创建所有表"""
    SQLModel.metadata.create_all(engine)
    logger.info("数据库初始化完成 | 路径=%s", settings.database_url)


def get_session() -> Session:
    """获取数据库会话"""
    return Session(engine)
