"""Settings API 路由

提供配置读写和测试接口。
"""

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from omka.app.core.logging import logger
from omka.app.core.settings_service import get_all_settings, get_setting, set_setting

router = APIRouter()


class SettingsTestResponse(BaseModel):
    success: bool
    message: str


class SettingUpdateRequest(BaseModel):
    value: str | int | float | bool | None


@router.get("")
async def get_settings():
    settings = get_all_settings(mask_secrets=True)
    return {"settings": settings}


@router.put("")
async def update_settings(data: dict[str, Any]):
    updated = []
    has_scheduler = False
    for key, value in data.items():
        if key in {"app_version"}:
            continue
        set_setting(key, value)
        if key == "scheduler_daily_cron":
            has_scheduler = True
        updated.append(key)

    if has_scheduler:
        from omka.app.services.scheduler_service import update_schedule
        ok, _ = update_schedule(data["scheduler_daily_cron"])
        if not ok:
            logger.warning("设置已保存但调度器更新失败")

    logger.info("批量更新配置 | keys=%s", ", ".join(updated))
    return {"updated": updated, "message": f"已更新 {len(updated)} 项配置"}


@router.post("/test-github", response_model=SettingsTestResponse)
async def test_github():
    """测试 GitHub Token 是否有效"""
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
    """测试飞书应用机器人是否可用"""
    from omka.app.integrations.feishu.service import feishu_notification_service

    result = await feishu_notification_service.send_test_message()
    return SettingsTestResponse(success=result.success, message=result.message)


@router.post("/{key}")
async def update_setting(key: str, data: SettingUpdateRequest):
    if data.value is None:
        raise HTTPException(status_code=400, detail="缺少 value 字段")

    set_setting(key, data.value)

    if key == "scheduler_daily_cron" and isinstance(data.value, str):
        from omka.app.services.scheduler_service import update_schedule
        ok, _ = update_schedule(data.value)
        if not ok:
            logger.warning("设置已保存但调度器更新失败")

    return {"key": key, "message": "配置已更新"}
