from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    HUMAN_PRESENT = "human_present"
    VERIFIED_CHALLENGE = "verified_challenge"
    AI_MEDIATED = "ai_mediated"
    RELAY_RISK = "relay_risk"
    TEMPORAL_DRIFT = "temporal_drift"
    CROSS_SESSION_RISK = "cross_session_risk"
    POLICY_VIOLATION = "policy_violation"


class Claim(BaseModel):
    claim_id: str
    type: ClaimType
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    detail: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
