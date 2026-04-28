from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SendResult:
    success: bool
    message: str
    response: dict[str, Any] | None = None


class NotificationChannel(ABC):
    channel_type: str = ""

    @abstractmethod
    async def send_digest(self, digest: dict[str, Any]) -> SendResult:
        raise NotImplementedError
