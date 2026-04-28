"""Settings API 路由

提供配置读写和测试接口。
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from omka.app.core.logging import logger
from omka.app.core.settings_service import get_all_settings, get_setting, set_setting

router = APIRouter()


class SettingsUpdateRequest(BaseModel):
    key: str = Field(..., description="配置键名")
    value: Any = Field(..., description="配置值")


class SettingsTestResponse(BaseModel):
    success: bool
    message: str


@router.get("")
async def get_settings():
    """获取所有配置（敏感字段已脱敏）"""
    settings = get_all_settings(mask_secrets=True)
    return {"settings": settings}


@router.put("")
async def update_settings(data: dict[str, Any]):
    """批量更新配置

    Args:
        data: 配置字典，key-value 形式
    """
    updated = []
    for key, value in data.items():
        # 不允许修改只读配置
        if key in {"app_version"}:
            continue
        set_setting(key, value)
        updated.append(key)

    logger.info("批量更新配置 | keys=%s", ", ".join(updated))
    return {"updated": updated, "message": f"已更新 {len(updated)} 项配置"}


@router.post("/{key}")
async def update_setting(key: str, data: dict[str, Any]):
    """更新单个配置"""
    value = data.get("value")
    if value is None:
        raise HTTPException(status_code=400, detail="缺少 value 字段")

    set_setting(key, value)
    return {"key": key, "message": "配置已更新"}


@router.post("/test-github", response_model=SettingsTestResponse)
async def test_github():
    """测试 GitHub Token 是否有效"""
    import httpx

    token = get_setting("github_token", "")
    if not token:
        return SettingsTestResponse(success=False, message="GitHub Token 未配置")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,
            )
            if response.status_code == 200:
                user_data = response.json()
                return SettingsTestResponse(
                    success=True,
                    message=f"GitHub Token 有效 | 用户: {user_data.get('login', 'unknown')}",
                )
            elif response.status_code == 401:
                return SettingsTestResponse(success=False, message="GitHub Token 无效或已过期")
            else:
                return SettingsTestResponse(
                    success=False, message=f"GitHub API 返回错误: HTTP {response.status_code}"
                )
    except Exception as e:
        logger.error("测试 GitHub Token 失败 | error=%s", e)
        return SettingsTestResponse(success=False, message=f"测试失败: {str(e)}")


@router.post("/test-llm", response_model=SettingsTestResponse)
async def test_llm():
    """测试 LLM 配置是否可用"""
    import httpx

    provider = get_setting("llm_provider", "openai")
    api_key = get_setting("llm_api_key", "")
    base_url = get_setting("llm_base_url", "")
    model = get_setting("llm_model", "")

    if not api_key:
        return SettingsTestResponse(success=False, message="LLM API Key 未配置")

    if not base_url:
        return SettingsTestResponse(success=False, message="LLM Base URL 未配置")

    try:
        async with httpx.AsyncClient() as client:
            if provider == "ollama":
                # Ollama 测试
                response = await client.get(
                    f"{base_url}/api/tags",
                    timeout=10,
                )
                if response.status_code == 200:
                    return SettingsTestResponse(success=True, message="Ollama 服务可用")
                else:
                    return SettingsTestResponse(
                        success=False, message=f"Ollama 服务不可用: HTTP {response.status_code}"
                    )
            else:
                # OpenAI / Qwen 测试
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model or "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "max_tokens": 5,
                    },
                    timeout=30,
                )
                if response.status_code == 200:
                    return SettingsTestResponse(success=True, message="LLM 服务可用")
                elif response.status_code == 401:
                    return SettingsTestResponse(success=False, message="LLM API Key 无效")
                else:
                    return SettingsTestResponse(
                        success=False, message=f"LLM API 返回错误: HTTP {response.status_code}"
                    )
    except Exception as e:
        logger.error("测试 LLM 配置失败 | error=%s", e)
        return SettingsTestResponse(success=False, message=f"测试失败: {str(e)}")


@router.post("/test-feishu", response_model=SettingsTestResponse)
async def test_feishu():
    """测试飞书 Webhook 是否可用"""
    import httpx

    from omka.app.notifications.channels.feishu_webhook import build_feishu_signature

    webhook_url = get_setting("feishu_webhook_url", "")
    secret = get_setting("feishu_webhook_secret", "")

    if not webhook_url:
        return SettingsTestResponse(success=False, message="飞书 Webhook URL 未配置")

    try:
        # 构建测试消息
        payload = {
            "msg_type": "text",
            "content": {"text": "🔧 OMKA 测试消息\n\n这是来自 OMKA 知识助手的测试推送，配置验证成功！"},
        }

        # 如果配置了 secret，添加签名
        if secret:
            timestamp, sign = build_feishu_signature(secret)
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=10,
            )
            if response.status_code == 200:
                resp_data = response.json()
                if resp_data.get("code") == 0:
                    return SettingsTestResponse(success=True, message="飞书 Webhook 测试成功")
                else:
                    return SettingsTestResponse(
                        success=False,
                        message=f"飞书返回错误: {resp_data.get('msg', '未知错误')}",
                    )
            else:
                return SettingsTestResponse(
                    success=False, message=f"飞书 API 返回错误: HTTP {response.status_code}"
                )
    except Exception as e:
        logger.error("测试飞书 Webhook 失败 | error=%s", e)
        return SettingsTestResponse(success=False, message=f"测试失败: {str(e)}")
