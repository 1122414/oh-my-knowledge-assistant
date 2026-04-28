"""OMKA 运行时配置服务

支持从 DB app_settings 表动态读写配置，优先级高于 .env。
启动时从 .env 加载默认值，运行时优先读取 DB 值。
"""

import json
from datetime import datetime
from typing import Any

from sqlmodel import select

from omka.app.core.config import settings as env_settings
from omka.app.core.logging import logger
from omka.app.storage.db import AppSetting, get_session

# 敏感字段列表
SENSITIVE_KEYS = {
    "github_token",
    "llm_api_key",
    "feishu_webhook_url",
    "feishu_webhook_secret",
}

# 配置分类映射
CATEGORY_MAP = {
    "app_name": "general",
    "app_version": "general",
    "app_env": "general",
    "debug": "general",
    "api_host": "general",
    "api_port": "general",
    "github_token": "github",
    "github_api_base_url": "github",
    "llm_provider": "llm",
    "llm_api_key": "llm",
    "llm_base_url": "llm",
    "llm_model": "llm",
    "feishu_webhook_enabled": "feishu",
    "feishu_webhook_url": "feishu",
    "feishu_webhook_secret": "feishu",
    "feishu_push_digest_top_n": "feishu",
    "scheduler_daily_cron": "scheduler",
    "digest_top_n": "scheduler",
}


def _is_secret(key: str) -> bool:
    """判断是否为敏感字段"""
    return key.lower() in SENSITIVE_KEYS


def _mask_value(value: str) -> str:
    """对敏感值进行脱敏"""
    if not value or len(value) <= 4:
        return "****"
    return value[:4] + "****"


def get_setting(key: str, default: Any = None) -> Any:
    """获取配置值

    优先级：DB app_settings > .env 默认值

    Args:
        key: 配置键名
        default: 默认值

    Returns:
        配置值
    """
    # 1. 先查 DB
    try:
        with get_session() as session:
            db_setting = session.get(AppSetting, key)
            if db_setting and db_setting.value is not None:
                # 尝试解析 JSON
                try:
                    return json.loads(db_setting.value)
                except (json.JSONDecodeError, TypeError):
                    return db_setting.value
    except Exception as e:
        logger.debug("读取 DB 配置失败 | key=%s | error=%s", key, e)

    # 2. 回退到 .env
    if hasattr(env_settings, key):
        return getattr(env_settings, key)

    return default


def set_setting(key: str, value: Any, description: str | None = None) -> None:
    """设置配置值（写入 DB）

    Args:
        key: 配置键名
        value: 配置值（支持 str/int/float/bool/list/dict）
        description: 配置说明
    """
    # 将值序列化为字符串
    if isinstance(value, (dict, list, bool, int, float)):
        str_value = json.dumps(value, ensure_ascii=False)
    else:
        str_value = str(value)

    is_secret = _is_secret(key)
    category = CATEGORY_MAP.get(key, "general")

    with get_session() as session:
        db_setting = session.get(AppSetting, key)
        if db_setting:
            db_setting.value = str_value
            db_setting.is_secret = is_secret
            db_setting.category = category
            db_setting.updated_at = datetime.utcnow()
            if description:
                db_setting.description = description
        else:
            db_setting = AppSetting(
                key=key,
                value=str_value,
                is_secret=is_secret,
                category=category,
                description=description or f"配置项: {key}",
            )
        session.merge(db_setting)
        session.commit()

    if is_secret:
        logger.info("更新配置 | key=%s | category=%s | value=****", key, category)
    else:
        logger.info("更新配置 | key=%s | category=%s | value=%s", key, category, str_value[:100])


def get_all_settings(mask_secrets: bool = True) -> dict[str, Any]:
    """获取所有配置（用于 Settings API）

    Args:
        mask_secrets: 是否脱敏敏感字段

    Returns:
        配置字典
    """
    result = {}

    # 1. 从 .env 加载所有默认值
    for key in dir(env_settings):
        if key.startswith("_"):
            continue
        value = getattr(env_settings, key)
        # 过滤掉非配置属性
        if callable(value) or isinstance(value, type):
            continue
        # 只保留基本类型
        if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
            continue
        result[key] = value

    # 2. 用 DB 值覆盖
    try:
        with get_session() as session:
            db_settings = session.exec(select(AppSetting)).all()
            for db_setting in db_settings:
                key = db_setting.key
                try:
                    value = json.loads(db_setting.value)
                except (json.JSONDecodeError, TypeError):
                    value = db_setting.value

                if mask_secrets and db_setting.is_secret and value:
                    value = _mask_value(str(value))

                result[key] = value
    except Exception as e:
        logger.warning("读取 DB 配置失败 | error=%s", e)

    return result


def init_default_settings() -> None:
    """初始化默认配置到 DB

    将 .env 中的关键配置项同步到 DB app_settings 表，
    便于后续通过 UI 动态修改。
    """
    defaults = {
        "app_name": (env_settings.app_name, "应用名称"),
        "app_env": (env_settings.app_env, "运行环境"),
        "debug": (env_settings.debug, "调试模式"),
        "api_host": (env_settings.api_host, "API 监听地址"),
        "api_port": (env_settings.api_port, "API 端口"),
        "github_token": (env_settings.github_token, "GitHub Personal Access Token"),
        "github_api_base_url": (env_settings.github_api_base_url, "GitHub API 基础 URL"),
        "llm_provider": (env_settings.llm_provider, "LLM 提供商"),
        "llm_api_key": (env_settings.llm_api_key, "LLM API 密钥"),
        "llm_base_url": (env_settings.llm_base_url, "LLM API 基础 URL"),
        "llm_model": (env_settings.llm_model, "LLM 模型名称"),
        "scheduler_daily_cron": (env_settings.scheduler_daily_cron, "每日任务 Cron 表达式"),
        "scheduler_timezone": (env_settings.scheduler_timezone, "调度器时区"),
        "digest_top_n": (env_settings.digest_top_n, "每日简报 Top N"),
        "feishu_webhook_enabled": (env_settings.feishu_webhook_enabled, "是否启用飞书 Webhook"),
        "feishu_webhook_url": (env_settings.feishu_webhook_url, "飞书自定义机器人 Webhook URL"),
        "feishu_webhook_secret": (env_settings.feishu_webhook_secret, "飞书自定义机器人 Secret"),
        "feishu_push_digest_top_n": (env_settings.feishu_push_digest_top_n, "飞书推送 Digest Top N"),
    }

    for key, (value, desc) in defaults.items():
        # 如果 DB 中已存在，跳过（保留用户手动修改的值）
        with get_session() as session:
            existing = session.get(AppSetting, key)
            if existing is None:
                set_setting(key, value, description=desc)
                logger.info("初始化默认配置 | key=%s", key)

    logger.info("默认配置初始化完成")
