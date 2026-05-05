"""OMKA 全局配置管理

所有配置项从环境变量读取，支持 .env 文件。
环境变量定义在 .env.example 中，复制为 .env 后填入实际值。
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"


class Settings(BaseSettings):
    """应用配置类

    所有配置项都有默认值，实际值从环境变量或 .env 文件读取。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略未定义的环境变量
    )

    # ===========================================
    # 应用基础配置
    # ===========================================
    app_name: str = Field(default="OMKA", description="应用名称")
    app_version: str = Field(default="0.1.0", description="应用版本")
    app_env: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=False, description="调试模式")

    # API 服务配置
    api_host: str = Field(default="0.0.0.0", description="API 监听地址")
    api_port: int = Field(default=8000, description="API 端口")
    api_workers: int = Field(default=1, description="工作进程数")

    # ===========================================
    # GitHub API 配置
    # ===========================================
    github_token: str = Field(default="", description="GitHub Personal Access Token")
    github_api_base_url: str = Field(default="https://api.github.com", description="GitHub API 基础 URL")
    github_api_version: str = Field(default="2022-11-28", description="GitHub API 版本")

    # ===========================================
    # LLM 模型配置
    # ===========================================
    llm_provider: Literal["openai", "qwen", "ollama"] = Field(default="openai", description="LLM 提供商")
    llm_api_key: str = Field(default="", description="LLM API 密钥")
    llm_base_url: str = Field(default="https://api.openai.com/v1", description="LLM API 基础 URL")
    llm_model: str = Field(default="gpt-4o-mini", description="LLM 模型名称")
    llm_temperature: float = Field(default=0.7, description="采样温度", ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2048, description="最大生成 Token 数")
    llm_timeout: int = Field(default=30, description="LLM 请求超时（秒）")

    # Ollama 本地模型配置
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama 服务地址")
    ollama_model: str = Field(default="qwen2.5:7b", description="Ollama 模型名称")

    # ===========================================
    # 数据库配置
    # ===========================================
    database_url: str = Field(
        default=f"sqlite:///{DATA_DIR}/db/app.sqlite",
        description="数据库连接 URL",
    )
    database_echo: bool = Field(default=False, description="是否打印 SQL 语句")

    # ===========================================
    # 调度器配置
    # ===========================================
    scheduler_daily_cron: str = Field(default="0 9 * * *", description="每日任务 Cron 表达式")
    scheduler_timezone: str = Field(default="Asia/Shanghai", description="调度器时区")

    # ===========================================
    # 数据采集配置
    # ===========================================
    fetch_concurrency: int = Field(default=3, description="全局并发请求数", ge=1, le=10)
    fetch_timeout: int = Field(default=30, description="请求超时（秒）")
    fetch_max_retries: int = Field(default=3, description="失败重试次数")
    fetch_retry_base_delay: int = Field(default=2, description="重试间隔基数（秒）")

    search_rate_limit: int = Field(default=10, description="Search API 限速（次/分钟）")
    search_results_per_query: int = Field(default=5, description="每查询返回结果数")
    search_qualifiers: str = Field(default="in:name,description stars:>=5", description="GitHub 搜索限定符")
    search_min_stars: int = Field(default=10, description="搜索结果最低 star 数")
    search_max_candidates_per_query: int = Field(default=15, description="每搜索源最大候选数")
    search_expand_queries: bool = Field(default=False, description="是否启用多策略召回")
    search_quality_min_score: float = Field(default=0.35, description="源头质量最低分数阈值")
    search_stale_days_threshold: int = Field(default=365, description="仓库停更多少天算过期")
    search_daily_request_limit: int = Field(default=120, description="每日 GitHub Search API 请求上限")
    search_daily_enrich_limit: int = Field(default=40, description="每日 enrich 总量上限")
    releases_per_repo: int = Field(default=1, description="每仓库获取 Release 数")

    # ===========================================
    # 个性化排序配置
    # ===========================================
    score_weight_interest: float = Field(default=0.30, description="兴趣匹配权重")
    score_weight_project: float = Field(default=0.20, description="项目相关权重")
    score_weight_freshness: float = Field(default=0.15, description="新鲜度权重")
    score_weight_popularity: float = Field(default=0.10, description="热度权重")
    score_weight_source_quality: float = Field(default=0.25, description="源头质量权重")

    freshness_decay_days: int = Field(default=7, description="新鲜度衰减天数")
    candidate_score_threshold: float = Field(default=0.10, description="候选人最低分数阈值，低于此值的自动忽略")
    digest_top_n: int = Field(default=10, description="每日简报 Top N 条目数")

    # ===========================================
    # 数据目录配置
    # ===========================================
    data_dir: Path = Field(default=DATA_DIR, description="数据目录")
    profiles_dir: Path = Field(default=DATA_DIR / "profiles", description="用户画像目录")
    raw_data_dir: Path = Field(default=DATA_DIR / "raw", description="原始数据目录")
    digests_dir: Path = Field(default=DATA_DIR / "digests", description="简报输出目录")
    knowledge_dir: Path = Field(default=DATA_DIR / "knowledge", description="知识库目录")
    assets_dir: Path = Field(default=DATA_DIR / "assets", description="多模态资产目录")

    # ===========================================
    # 飞书应用机器人配置
    # ===========================================
    feishu_enabled: bool = Field(default=False, description="是否启用飞书应用机器人")
    feishu_app_id: str = Field(default="", description="飞书应用 App ID")
    feishu_app_secret: str = Field(default="", description="飞书应用 App Secret")
    feishu_verification_token: str = Field(default="", description="事件订阅验证 Token")
    feishu_encrypt_key: str = Field(default="", description="事件订阅加密 Key")
    feishu_api_base_url: str = Field(
        default="https://open.feishu.cn/open-apis",
        description="飞书 API 基础 URL",
    )
    feishu_request_timeout_seconds: int = Field(default=10, description="飞书请求超时（秒）")
    feishu_max_retries: int = Field(default=3, description="飞书最大重试次数")
    feishu_default_receive_id_type: str = Field(
        default="chat_id",
        description="默认接收者类型: chat_id, open_id, user_id, email",
    )
    feishu_default_chat_id: str = Field(default="", description="默认群聊 ID")
    feishu_command_prefix: str = Field(default="/omka", description="命令前缀")
    feishu_require_mention: bool = Field(default=True, description="群聊中是否需要 @ 机器人")
    feishu_group_allowlist: str = Field(default="", description="允许的群聊 ID 列表（逗号分隔）")
    feishu_user_allowlist: str = Field(default="", description="允许的用户 ID 列表（逗号分隔）")
    feishu_push_digest_enabled: bool = Field(default=True, description="是否推送每日简报")
    feishu_push_digest_top_n: int = Field(default=6, description="推送简报条目数")
    feishu_event_callback_path: str = Field(
        default="/api/integrations/feishu/events",
        description="事件回调路径",
    )
    feishu_public_callback_url: str = Field(default="", description="公开回调 URL")
    feishu_agent_conversation_enabled: bool = Field(default=False, description="是否启用 Agent 对话")
    feishu_agent_session_ttl_minutes: int = Field(default=60, description="Agent 会话 TTL（分钟）")
    feishu_agent_max_message_chars: int = Field(default=4000, description="Agent 消息最大字符数")
    feishu_auto_bind_direct_chat: bool = Field(default=True, description="自动绑定单聊会话")
    feishu_admin_open_ids: str = Field(default="", description="管理员 open_id 列表（逗号分隔）")
    feishu_operator_open_ids: str = Field(default="", description="操作员 open_id 列表（逗号分隔）")

    feishu_doc_folder_token: str = Field(default="", description="云文档默认文件夹 token")
    feishu_base_folder_token: str = Field(default="", description="多维表格默认文件夹 token")
    feishu_sheet_folder_token: str = Field(default="", description="电子表格默认文件夹 token")
    feishu_default_calendar_id: str = Field(default="", description="默认日历 ID")

    # ===========================================
    # Agent 配置
    # ===========================================
    omka_agent_chat_enabled: bool = Field(default=False, description="启用 Agent 自由聊天")
    omka_agent_provider: str = Field(default="", description="Agent LLM 提供商")
    omka_agent_model: str = Field(default="", description="Agent 模型名称")
    omka_agent_temperature: float = Field(default=0.2, description="Agent 温度")
    omka_agent_timeout_seconds: int = Field(default=60, description="Agent 超时")
    omka_agent_max_recent_messages: int = Field(default=6, description="最大最近消息数")
    omka_agent_max_digest_items: int = Field(default=5, description="最大 Digest 上下文数")
    omka_agent_max_knowledge_items: int = Field(default=5, description="最大 Knowledge 上下文数")
    omka_agent_max_candidate_items: int = Field(default=5, description="最大 Candidate 上下文数")
    omka_agent_max_context_chars: int = Field(default=12000, description="最大上下文字数")

    # ===========================================
    # 推荐系统配置
    # ===========================================
    recommendation_enabled: bool = Field(default=True, description="是否启用推荐系统")
    recommendation_explanation_enabled: bool = Field(default=True, description="是否生成推荐解释")
    recommendation_feedback_learning_enabled: bool = Field(default=True, description="是否启用反馈学习")

    # ===========================================
    # 推送策略配置
    # ===========================================
    push_high_score_threshold: float = Field(default=0.85, description="高价值推送分数阈值")
    push_max_per_day: int = Field(default=5, description="每日最大推送次数")
    push_quiet_hours_start: int = Field(default=22, description="安静时间开始（小时）")
    push_quiet_hours_end: int = Field(default=8, description="安静时间结束（小时）")

    # ===========================================
    # 记忆系统配置
    # ===========================================
    memory_extraction_enabled: bool = Field(default=True, description="是否启用对话记忆抽取")
    memory_extraction_confidence_threshold: float = Field(default=0.8, description="记忆抽取置信度阈值")
    memory_max_active_items: int = Field(default=20, description="Agent 上下文最大活跃记忆数")

    # ===========================================
    # 多模态资产配置
    # ===========================================
    asset_max_file_size_mb: int = Field(default=10, description="最大上传文件大小（MB）")
    asset_allowed_image_types: str = Field(default="jpg,jpeg,png,webp", description="允许的图片类型")
    asset_allowed_document_types: str = Field(default="pdf,md,txt", description="允许的文档类型")

    # 废弃的 Webhook 配置（保留兼容性，默认关闭）
    feishu_webhook_enabled: bool = Field(default=False, description="[已废弃] 是否启用飞书 Webhook")
    feishu_webhook_url: str = Field(default="", description="[已废弃] 飞书自定义机器人 Webhook URL")
    feishu_webhook_secret: str = Field(default="", description="[已废弃] 飞书自定义机器人 Secret")

    # ===========================================
    # 日志配置
    # ===========================================
    log_level: str = Field(default="INFO", description="日志级别: DEBUG, INFO, WARNING, ERROR")
    log_dir: Path = Field(default=LOGS_DIR, description="日志目录")
    log_file_max_bytes: int = Field(default=10 * 1024 * 1024, description="单个日志文件最大字节数")
    log_file_backup_count: int = Field(default=5, description="日志文件备份数量")
    log_trace_enabled: bool = Field(default=True, description="启用函数调用追踪 @trace")
    log_api_enabled: bool = Field(default=True, description="启用 API 请求日志")

    def ensure_dirs(self) -> None:
        """确保所有数据目录存在"""
        dirs = [
            self.data_dir,
            self.profiles_dir,
            self.raw_data_dir / "github",
            self.digests_dir,
            self.knowledge_dir / "github",
            self.data_dir / "db",
            self.log_dir,
            self.assets_dir / "images",
            self.assets_dir / "documents",
            self.assets_dir / "pdf",
            self.assets_dir / "derived",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局配置实例（单例模式）"""
    settings = Settings()
    settings.ensure_dirs()
    return settings


# 全局配置快捷访问
settings = get_settings()
