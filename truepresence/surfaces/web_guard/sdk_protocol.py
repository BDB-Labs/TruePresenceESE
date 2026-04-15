from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WebGuardEvent(BaseModel):
    session_id: str
    event_type: str
    timestamp: float
    payload: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, float] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class WebGuardDecisionEnvelope(BaseModel):
    state: str
    legacy_decision: str
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)
    challenge: dict[str, Any] | None = None
