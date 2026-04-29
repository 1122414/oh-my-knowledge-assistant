import json
from typing import Any

import httpx

from omka.app.core.config import settings
from omka.app.core.logging import logger


class LLMClient:
    def __init__(self):
        self.provider = settings.llm_provider
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self.timeout = settings.llm_timeout

    async def summarize(self, title: str, content: str, item_type: str) -> dict[str, str]:
        prompt = self._build_summary_prompt(title, content, item_type)
        try:
            response = await self._chat_completion(prompt)
            return self._parse_summary_response(response)
        except Exception as e:
            logger.error("LLM 摘要失败 | title=%s | error=%s", title, e)
            return {
                "summary": content[:200] + "..." if len(content) > 200 else content,
                "recommendation_reason": "基于关键词匹配推荐",
                "suggested_action": "查看详情",
            }

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """多轮对话接口

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            助手回复文本
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        if self.provider == "ollama":
            return await self._ollama_chat_messages(messages, temp, tokens)

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _ollama_chat_messages(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        url = f"{settings.ollama_base_url}/api/chat"
        payload = {
            "model": settings.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    def _build_summary_prompt(self, title: str, content: str, item_type: str) -> str:
        return f"""请为以下 GitHub 内容生成摘要和推荐理由。

标题: {title}
类型: {item_type}
内容:
{content[:2000]}

请用中文 JSON 格式回复，字段如下:
- summary: 一句话摘要（不超过 100 字）
- recommendation_reason: 为什么值得关注的理由（不超过 80 字）
- suggested_action: 建议的下一步动作（如"收藏研究","阅读文档","暂时忽略"）

只返回 JSON，不要其他内容。"""

    async def _chat_completion(self, prompt: str) -> str:
        if self.provider == "ollama":
            return await self._ollama_chat(prompt)

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _ollama_chat(self, prompt: str) -> str:
        url = f"{settings.ollama_base_url}/api/chat"
        payload = {
            "model": settings.ollama_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    def _parse_summary_response(self, text: str) -> dict[str, str]:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
            return {
                "summary": data.get("summary", "")[:200],
                "recommendation_reason": data.get("recommendation_reason", "")[:200],
                "suggested_action": data.get("suggested_action", "查看详情"),
            }
        except json.JSONDecodeError:
            lines = text.split("\n")
            return {
                "summary": lines[0][:200] if lines else "",
                "recommendation_reason": lines[1][:200] if len(lines) > 1 else "",
                "suggested_action": "查看详情",
            }
