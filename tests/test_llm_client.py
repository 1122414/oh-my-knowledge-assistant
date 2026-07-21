from __future__ import annotations

from typing import Any

import httpx
import pytest

from omka.app.pipeline import summarizer
from omka.app.pipeline.summarizer import LLMClient


@pytest.mark.asyncio
async def test_openai_chat_retries_transient_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "choices": [
                    {"message": {"content": "retry succeeded"}}
                ]
            }

    class FakeAsyncClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        async def post(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise httpx.ConnectError("temporary disconnect")
            return FakeResponse()

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(summarizer.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(summarizer.asyncio, "sleep", no_sleep)

    client = LLMClient(provider="openai", model="test-model")
    result = await client.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result == "retry succeeded"
    assert attempts == 3
