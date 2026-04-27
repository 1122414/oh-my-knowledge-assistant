"""OMKA 全局配置管理

所有配置项从环境变量读取，支持 .env 文件。
环境变量定义在 .env.example 中，复制为 .env 后填入实际值。
"""

from functools import lru_cache
from pathlib import Path

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
    releases_per_repo: int = Field(default=1, description="每仓库获取 Release 数")

    # ===========================================
    # 个性化排序配置
    # ===========================================
    score_weight_interest: float = Field(default=0.40, description="兴趣匹配权重")
    score_weight_project: float = Field(default=0.30, description="项目相关权重")
    score_weight_freshness: float = Field(default=0.15, description="新鲜度权重")
    score_weight_popularity: float = Field(default=0.15, description="热度权重")

    freshness_decay_days: int = Field(default=7, description="新鲜度衰减天数")
    digest_top_n: int = Field(default=10, description="每日简报 Top N 条目数")

    # ===========================================
    # 数据目录配置
    # ===========================================
    data_dir: Path = Field(default=DATA_DIR, description="数据目录")
    profiles_dir: Path = Field(default=DATA_DIR / "profiles", description="用户画像目录")
    raw_data_dir: Path = Field(default=DATA_DIR / "raw", description="原始数据目录")
    digests_dir: Path = Field(default=DATA_DIR / "digests", description="简报输出目录")
    knowledge_dir: Path = Field(default=DATA_DIR / "knowledge", description="知识库目录")

    # ===========================================
    # 日志配置
    # ===========================================
    log_level: str = Field(default="INFO", description="日志级别")
    log_dir: Path = Field(default=LOGS_DIR, description="日志目录")
    log_file_max_bytes: int = Field(default=10 * 1024 * 1024, description="单个日志文件最大字节数")
    log_file_backup_count: int = Field(default=5, description="日志文件备份数量")

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
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """获取全局配置实例（单例模式）"""
    settings = Settings()
    settings.ensure_dirs()
    return settings


# 全局配置快捷访问
settings = get_settings()
