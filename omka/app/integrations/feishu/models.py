from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class FeishuSendStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class FeishuEventType(str, Enum):
    MESSAGE = "message"
    URL_VERIFICATION = "url_verification"


class FeishuCommandType(str, Enum):
    HELP = "help"
    BIND = "bind"
    STATUS = "status"
    LATEST = "latest"
    RUN = "run"
    CHAT = "chat"
    SOURCE = "source"
    CANDIDATE = "candidate"
    CONFIG = "config"
    PUSH = "push"
    KNOWLEDGE = "knowledge"
    DOC = "doc"
    BASE = "base"
    SHEET = "sheet"
    CALENDAR = "calendar"
    TASK = "task"
    UNKNOWN = "unknown"


@dataclass
class FeishuSendResult:
    success: bool
    message: str
    message_id: str | None = None
    request_id: str | None = None
    error_code: str | None = None
    response: dict[str, Any] | None = None


@dataclass
class FeishuTokenInfo:
    token: str
    expires_at: datetime
    tenant_access_token: str


@dataclass
class FeishuMessageEvent:
    event_id: str
    event_type: str
    chat_id: str
    sender_id: str
    message_id: str
    message_type: str
    content: str
    mentions: list[dict[str, Any]] | None = None


@dataclass
class FeishuCommandResult:
    success: bool
    message: str
    command: FeishuCommandType = FeishuCommandType.UNKNOWN
    args: list[str] | None = None
