from datetime import datetime
from typing import Any, Dict, Literal

from pydantic import BaseModel

EventType = Literal[
    "cursor_move",
    "key_timing",
    "click",
    "focus",
    "blur",
    "challenge_response",
    "audio_signal",
    "video_signal",
    "device_attestation",
    "clipboard",
]


class Event(BaseModel):
    session_id: str
    event_type: EventType
    timestamp: datetime
    payload: Dict[str, Any]
