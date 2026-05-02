import time

import httpx

from omka.app.core.logging import logger
from omka.app.integrations.feishu.config import FeishuConfig
from omka.app.integrations.feishu.errors import FeishuAuthError, FeishuConfigError


class FeishuAuthService:
    REFRESH_BUFFER_SECONDS = 300

    def __init__(self, config: FeishuConfig):
        if not config.is_configured():
            raise FeishuConfigError("飞书配置不完整：缺少 app_id 或 app_secret")

        self._config = config
        self._token: str | None = None
        self._expires_at: float = 0.0

    async def get_tenant_access_token(self) -> str:
        if self._is_token_valid():
            assert self._token is not None
            return self._token

        return await self.refresh_tenant_access_token()

    async def refresh_tenant_access_token(self) -> str:
        url = f"{self._config.api_base_url.rstrip('/')}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self._config.app_id,
            "app_secret": self._config.app_secret,
        }

        try:
            async with httpx.AsyncClient(timeout=self._config.request_timeout_seconds) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            logger.error("获取 tenant_access_token 超时 | url=%s", url)
            raise FeishuAuthError("获取 tenant_access_token 超时")
        except httpx.HTTPStatusError as e:
            logger.error(
                "获取 tenant_access_token HTTP 错误 | status=%d",
                e.response.status_code,
            )
            raise FeishuAuthError(
                f"获取 tenant_access_token HTTP 错误: {e.response.status_code}"
            )
        except Exception as e:
            logger.error("获取 tenant_access_token 异常 | error=%s", type(e).__name__)
            raise FeishuAuthError(f"获取 tenant_access_token 异常: {e}")

        code = data.get("code")
        if code != 0:
            msg = data.get("msg", "unknown error")
            logger.error("获取 tenant_access_token 业务错误 | code=%d | msg=%s", code, msg)
            raise FeishuAuthError(f"飞书 API 错误: code={code}, msg={msg}", error_code=str(code))

        token = data.get("tenant_access_token")
        expire = data.get("expire", 7200)

        if not token:
            logger.error("飞书 API 返回空 token")
            raise FeishuAuthError("飞书 API 返回空 tenant_access_token")

        self._token = token
        self._expires_at = time.time() + expire

        logger.info(
            "tenant_access_token 已刷新 | expires_in=%ds",
            expire,
        )
        return token

    def _is_token_valid(self) -> bool:
        if self._token is None:
            return False
        return time.time() < (self._expires_at - self.REFRESH_BUFFER_SECONDS)

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = 0.0
        logger.debug("tenant_access_token 缓存已清除")
