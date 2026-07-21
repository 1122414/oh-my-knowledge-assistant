"""Conservative extraction of user-owned candidate memories from conversations."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from omka.app.core.config import settings
from omka.app.core.logging import get_logger
from omka.app.core.settings_service import get_setting
from omka.app.pipeline.summarizer import LLMClient
from omka.app.services.memory_service import MemoryService

logger = get_logger("agent")


class ExtractedMemory(BaseModel):
    subject: Literal["interest", "project", "preference", "task", "setting"]
    content: str = Field(min_length=2, max_length=1000)
    confidence: float = Field(ge=0, le=1)
    importance: float = Field(default=0.5, ge=0, le=1)
    tags: list[str] = Field(default_factory=list, max_length=8)


class MemoryExtractionResult(BaseModel):
    memories: list[ExtractedMemory] = Field(default_factory=list, max_length=5)


class ConversationMemoryExtractor:
    """Extracts only explicit, durable user facts and stores them for review."""

    _TRIGGERS = (
        "记住",
        "以后",
        "我喜欢",
        "我不喜欢",
        "我正在",
        "我在做",
        "我的项目",
        "我的偏好",
        "提醒我",
        "prefer",
        "remember",
    )

    def __init__(self) -> None:
        self._llm = LLMClient(
            provider=settings.omka_agent_provider or settings.llm_provider,
            model=settings.omka_agent_model or settings.llm_model,
        )

    async def extract(
        self,
        *,
        user_message: str,
        assistant_answer: str,
        user_external_id: str,
        conversation_id: str,
    ) -> list[str]:
        enabled = bool(get_setting("memory_extraction_enabled", settings.memory_extraction_enabled))
        if not enabled or not self._should_extract(user_message):
            return []

        threshold = float(
            get_setting(
                "memory_extraction_confidence_threshold",
                settings.memory_extraction_confidence_threshold,
            )
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "从用户消息中提取适合长期保存的明确事实。只提取用户明确表达的兴趣、"
                    "项目、偏好、长期任务或设置。不要从助手回答推断事实，不要保存临时问题、"
                    "敏感凭证、健康或财务隐私。严格返回 JSON："
                    '{"memories":[{"subject":"preference","content":"...",'
                    '"confidence":0.9,"importance":0.6,"tags":["..."]}]}。'
                    "没有可保存内容时返回 {\"memories\":[]}。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户消息：{user_message}\n"
                    f"助手回答仅供消歧，不得作为事实来源：{assistant_answer[:500]}"
                ),
            },
        ]
        try:
            raw = await self._llm.chat(messages=messages, temperature=0.0, max_tokens=500)
            result = self._parse(raw)
        except Exception as exc:
            logger.warning("对话记忆抽取失败 | error=%s", exc)
            return []

        existing = MemoryService.list_memories(
            owner_external_id=user_external_id,
            limit=200,
        )
        normalized_existing = {self._normalize(memory.content) for memory in existing}
        created_ids: list[str] = []
        for candidate in result.memories:
            if candidate.confidence < threshold:
                continue
            normalized = self._normalize(candidate.content)
            if not normalized or normalized in normalized_existing:
                continue
            memory = MemoryService.create_memory(
                memory_type="conversation",
                subject=candidate.subject,
                content=candidate.content,
                scope="user",
                owner_external_id=user_external_id,
                conversation_id=conversation_id,
                source_type="conversation",
                source_ref=conversation_id,
                confidence=candidate.confidence,
                importance=candidate.importance,
                status="candidate",
                tags=candidate.tags,
                actor_type="agent",
                actor_id=user_external_id,
            )
            created_ids.append(memory.id)
            normalized_existing.add(normalized)
        return created_ids

    @classmethod
    def _should_extract(cls, text: str) -> bool:
        lowered = text.lower()
        return any(trigger in lowered for trigger in cls._TRIGGERS)

    @staticmethod
    def _parse(raw: str) -> MemoryExtractionResult:
        text = raw.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        try:
            return MemoryExtractionResult.model_validate(json.loads(text.strip()))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError("记忆抽取响应不是有效 JSON") from exc

    @staticmethod
    def _normalize(text: str) -> str:
        return "".join(text.lower().split()).strip("。.!！")
