from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    is_bot: bool = False

class TelegramChat(BaseModel):
    id: int
    type: str
    title: Optional[str] = None

class TelegramMessage(BaseModel):
    message_id: int
    from_user: TelegramUser = Field(..., alias="from")
    chat: TelegramChat
    text: str = ""
    date: int
    reply_to_message_id: Optional[int] = None
    has_attachments: bool = False

class TelegramEvent(BaseModel):
    event_type: str
    timestamp: int
    payload: Dict[str, Any]
    features: Dict[str, float]
    signals: Dict[str, float]
    context: Dict[str, Any]
    threat_analysis: Dict[str, Any]

class TelegramAction(BaseModel):
    action: str
    reason: str = ""
    confidence: float = 0.0
    threat_categories: List[str] = Field(default_factory=list)
    tenant_id: Optional[str] = None
    rate_limited: bool = False
    evaluation: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
