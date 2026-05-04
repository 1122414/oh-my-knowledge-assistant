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
    "feishu_app_secret",
    "feishu_verification_token",
    "feishu_encrypt_key",
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
    "feishu_enabled": "feishu",
    "feishu_app_id": "feishu",
    "feishu_app_secret": "feishu",
    "feishu_verification_token": "feishu",
    "feishu_encrypt_key": "feishu",
    "feishu_api_base_url": "feishu",
    "feishu_request_timeout_seconds": "feishu",
    "feishu_max_retries": "feishu",
    "feishu_default_receive_id_type": "feishu",
    "feishu_default_chat_id": "feishu",
    "feishu_command_prefix": "feishu",
    "feishu_require_mention": "feishu",
    "feishu_group_allowlist": "feishu",
    "feishu_user_allowlist": "feishu",
    "feishu_push_digest_enabled": "feishu",
    "feishu_push_digest_top_n": "feishu",
    "feishu_event_callback_path": "feishu",
    "feishu_public_callback_url": "feishu",
    "feishu_agent_conversation_enabled": "feishu",
    "feishu_agent_session_ttl_minutes": "feishu",
    "feishu_agent_max_message_chars": "feishu",
    "feishu_auto_bind_direct_chat": "feishu",
    "feishu_admin_open_ids": "feishu",
    "feishu_operator_open_ids": "feishu",
    "feishu_doc_folder_token": "feishu",
    "feishu_base_folder_token": "feishu",
    "feishu_sheet_folder_token": "feishu",
    "feishu_default_calendar_id": "feishu",
    "feishu_webhook_enabled": "feishu",
    "feishu_webhook_url": "feishu",
    "feishu_webhook_secret": "feishu",
    "omka_agent_chat_enabled": "agent",
    "omka_agent_provider": "agent",
    "omka_agent_model": "agent",
    "omka_agent_temperature": "agent",
    "omka_agent_timeout_seconds": "agent",
    "omka_agent_max_recent_messages": "agent",
    "omka_agent_max_digest_items": "agent",
    "omka_agent_max_knowledge_items": "agent",
    "omka_agent_max_candidate_items": "agent",
    "omka_agent_max_context_chars": "agent",
    "scheduler_daily_cron": "scheduler",
    "digest_top_n": "scheduler",
    "candidate_score_threshold": "scoring",
    "search_qualifiers": "fetch",
    "search_min_stars": "fetch",
    "search_max_candidates_per_query": "fetch",
    "search_expand_queries": "fetch",
    "search_rate_limit": "fetch",
    "search_results_per_query": "fetch",
    "score_weight_interest": "scoring",
    "score_weight_project": "scoring",
    "score_weight_freshness": "scoring",
    "score_weight_popularity": "scoring",
    "freshness_decay_days": "scoring",
    "recommendation_enabled": "recommendation",
    "recommendation_explanation_enabled": "recommendation",
    "recommendation_feedback_learning_enabled": "recommendation",
    "push_high_score_threshold": "push",
    "push_max_per_day": "push",
    "push_quiet_hours_start": "push",
    "push_quiet_hours_end": "push",
    "memory_extraction_enabled": "memory",
    "memory_extraction_confidence_threshold": "memory",
    "memory_max_active_items": "memory",
    "asset_max_file_size_mb": "asset",
    "asset_allowed_image_types": "asset",
    "asset_allowed_document_types": "asset",
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
    for key in env_settings.model_fields:
        try:
            value = getattr(env_settings, key)
            # 只保留基本类型
            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                result[key] = value
        except Exception:
            continue

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
        "feishu_enabled": (env_settings.feishu_enabled, "是否启用飞书应用机器人"),
        "feishu_app_id": (env_settings.feishu_app_id, "飞书应用 App ID"),
        "feishu_app_secret": (env_settings.feishu_app_secret, "飞书应用 App Secret"),
        "feishu_verification_token": (env_settings.feishu_verification_token, "事件订阅验证 Token"),
        "feishu_encrypt_key": (env_settings.feishu_encrypt_key, "事件订阅加密 Key"),
        "feishu_api_base_url": (env_settings.feishu_api_base_url, "飞书 API 基础 URL"),
        "feishu_request_timeout_seconds": (env_settings.feishu_request_timeout_seconds, "飞书请求超时（秒）"),
        "feishu_max_retries": (env_settings.feishu_max_retries, "飞书最大重试次数"),
        "feishu_default_receive_id_type": (env_settings.feishu_default_receive_id_type, "默认接收者类型"),
        "feishu_default_chat_id": (env_settings.feishu_default_chat_id, "默认群聊 ID"),
        "feishu_command_prefix": (env_settings.feishu_command_prefix, "命令前缀"),
        "feishu_require_mention": (env_settings.feishu_require_mention, "群聊中是否需要 @ 机器人"),
        "feishu_group_allowlist": (env_settings.feishu_group_allowlist, "允许的群聊 ID 列表"),
        "feishu_user_allowlist": (env_settings.feishu_user_allowlist, "允许的用户 ID 列表"),
        "feishu_push_digest_enabled": (env_settings.feishu_push_digest_enabled, "是否推送每日简报"),
        "feishu_push_digest_top_n": (env_settings.feishu_push_digest_top_n, "推送简报条目数"),
        "feishu_event_callback_path": (env_settings.feishu_event_callback_path, "事件回调路径"),
        "feishu_public_callback_url": (env_settings.feishu_public_callback_url, "公开回调 URL"),
        "feishu_agent_conversation_enabled": (env_settings.feishu_agent_conversation_enabled, "是否启用 Agent 对话"),
        "feishu_agent_session_ttl_minutes": (env_settings.feishu_agent_session_ttl_minutes, "Agent 会话 TTL（分钟）"),
        "feishu_agent_max_message_chars": (env_settings.feishu_agent_max_message_chars, "Agent 消息最大字符数"),
        "feishu_auto_bind_direct_chat": (env_settings.feishu_auto_bind_direct_chat, "自动绑定单聊会话"),
        "feishu_admin_open_ids": (env_settings.feishu_admin_open_ids, "管理员 open_id 列表"),
        "feishu_operator_open_ids": (env_settings.feishu_operator_open_ids, "操作员 open_id 列表"),
        "feishu_webhook_enabled": (env_settings.feishu_webhook_enabled, "[已废弃] 是否启用飞书 Webhook"),
        "feishu_webhook_url": (env_settings.feishu_webhook_url, "[已废弃] 飞书自定义机器人 Webhook URL"),
        "feishu_webhook_secret": (env_settings.feishu_webhook_secret, "[已废弃] 飞书自定义机器人 Secret"),
        "omka_agent_chat_enabled": (env_settings.omka_agent_chat_enabled, "启用 Agent 自由聊天"),
        "omka_agent_provider": (env_settings.omka_agent_provider, "Agent LLM 提供商"),
        "omka_agent_model": (env_settings.omka_agent_model, "Agent 模型名称"),
        "omka_agent_temperature": (env_settings.omka_agent_temperature, "Agent 温度"),
        "omka_agent_timeout_seconds": (env_settings.omka_agent_timeout_seconds, "Agent 超时"),
        "omka_agent_max_recent_messages": (env_settings.omka_agent_max_recent_messages, "最大最近消息数"),
        "omka_agent_max_digest_items": (env_settings.omka_agent_max_digest_items, "最大 Digest 上下文数"),
        "omka_agent_max_knowledge_items": (env_settings.omka_agent_max_knowledge_items, "最大 Knowledge 上下文数"),
        "omka_agent_max_candidate_items": (env_settings.omka_agent_max_candidate_items, "最大 Candidate 上下文数"),
        "omka_agent_max_context_chars": (env_settings.omka_agent_max_context_chars, "最大上下文字数"),
        "score_weight_interest": (env_settings.score_weight_interest, "兴趣匹配权重"),
        "score_weight_project": (env_settings.score_weight_project, "项目相关权重"),
        "score_weight_freshness": (env_settings.score_weight_freshness, "新鲜度权重"),
        "score_weight_popularity": (env_settings.score_weight_popularity, "热度权重"),
        "freshness_decay_days": (env_settings.freshness_decay_days, "新鲜度衰减天数"),
        "recommendation_enabled": (env_settings.recommendation_enabled, "是否启用推荐系统"),
        "recommendation_explanation_enabled": (env_settings.recommendation_explanation_enabled, "是否生成推荐解释"),
        "recommendation_feedback_learning_enabled": (env_settings.recommendation_feedback_learning_enabled, "是否启用反馈学习"),
        "push_high_score_threshold": (env_settings.push_high_score_threshold, "高价值推送分数阈值"),
        "push_max_per_day": (env_settings.push_max_per_day, "每日最大推送次数"),
        "push_quiet_hours_start": (env_settings.push_quiet_hours_start, "安静时间开始（小时）"),
        "push_quiet_hours_end": (env_settings.push_quiet_hours_end, "安静时间结束（小时）"),
        "memory_extraction_enabled": (env_settings.memory_extraction_enabled, "是否启用对话记忆抽取"),
        "memory_extraction_confidence_threshold": (env_settings.memory_extraction_confidence_threshold, "记忆抽取置信度阈值"),
        "memory_max_active_items": (env_settings.memory_max_active_items, "Agent上下文最大活跃记忆数"),
        "asset_max_file_size_mb": (env_settings.asset_max_file_size_mb, "最大上传文件大小（MB）"),
        "asset_allowed_image_types": (env_settings.asset_allowed_image_types, "允许的图片类型"),
        "asset_allowed_document_types": (env_settings.asset_allowed_document_types, "允许的文档类型"),
    }

    for key, (value, desc) in defaults.items():
        # 如果 DB 中已存在，跳过（保留用户手动修改的值）
        with get_session() as session:
            existing = session.get(AppSetting, key)
            if existing is None:
                set_setting(key, value, description=desc)
                logger.info("初始化默认配置 | key=%s", key)

    logger.info("默认配置初始化完成")
