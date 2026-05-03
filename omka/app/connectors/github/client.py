import asyncio
from typing import Any

import httpx

from omka.app.core.config import settings
from omka.app.core.logging import logger


class GitHubClient:
    """GitHub REST API 客户端

    支持条件请求（ETag/Last-Modified）、限速、重试。
    """

    def __init__(self, token: str | None = None):
        self.token = token or settings.github_token
        self.base_url = settings.github_api_base_url.rstrip("/")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": settings.github_api_version,
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

        self.client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(settings.fetch_concurrency)

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=settings.fetch_timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """获取仓库基础信息"""
        url = f"{self.base_url}/repos/{owner}/{repo}"
        return await self._request("GET", url)

    async def get_latest_release(self, owner: str, repo: str, per_page: int = 1) -> list[dict[str, Any]]:
        """获取仓库最新 Release"""
        url = f"{self.base_url}/repos/{owner}/{repo}/releases"
        params = {"per_page": per_page}
        result = await self._request("GET", url, params=params)
        return result if isinstance(result, list) else []

    async def search_repositories(self, query: str, per_page: int = 5, sort: str | None = "updated", qualifiers: str | None = None) -> list[dict[str, Any]]:
        url = f"{self.base_url}/search/repositories"
        effective_qualifiers = qualifiers if qualifiers is not None else settings.search_qualifiers
        full_query = f"{query} {effective_qualifiers}".strip() if effective_qualifiers else query
        params = {
            "q": full_query,
            "per_page": per_page,
        }
        if sort:
            params["sort"] = sort
            params["order"] = "desc"
        result = await self._request("GET", url, params=params)
        return result.get("items", []) if isinstance(result, dict) else []

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """发送 HTTP 请求，支持重试和限速"""
        if not self.client:
            raise RuntimeError("Client not initialized. Use async with.")

        async with self._semaphore:
            for attempt in range(settings.fetch_max_retries):
                try:
                    response = await self.client.request(
                        method, url, params=params, headers=headers
                    )

                    if response.status_code == 304:
                        logger.debug("内容未变化 | URL=%s", url)
                        return {}

                    if response.status_code in (403, 429):
                        retry_after = response.headers.get("retry-after")
                        wait = int(retry_after) if retry_after else 60
                        logger.warning(
                            "API 限速 | URL=%s | 等待=%ds | 重试=%d/%d",
                            url, wait, attempt + 1, settings.fetch_max_retries,
                        )
                        await asyncio.sleep(wait)
                        continue

                    response.raise_for_status()
                    return response.json()

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        logger.warning("资源不存在 | URL=%s", url)
                        return {}
                    logger.error(
                        "HTTP 错误 | URL=%s | 状态=%d | 重试=%d/%d",
                        url, e.response.status_code, attempt + 1, settings.fetch_max_retries,
                    )
                    if attempt == settings.fetch_max_retries - 1:
                        raise

                except httpx.TimeoutException:
                    delay = settings.fetch_retry_base_delay ** attempt
                    logger.warning(
                        "请求超时 | URL=%s | 等待=%ds | 重试=%d/%d",
                        url, delay, attempt + 1, settings.fetch_max_retries,
                    )
                    await asyncio.sleep(delay)

                except Exception as e:
                    logger.error(
                        "请求异常 | URL=%s | 错误=%s | 重试=%d/%d",
                        url, str(e), attempt + 1, settings.fetch_max_retries,
                    )
                    if attempt == settings.fetch_max_retries - 1:
                        raise

        return {}
