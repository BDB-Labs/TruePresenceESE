from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DecisionState(str, Enum):
    ALLOW = "ALLOW"
    OBSERVE = "OBSERVE"
    CHALLENGE = "CHALLENGE"
    STEP_UP_AUTH = "STEP_UP_AUTH"
    RESTRICT = "RESTRICT"
    BLOCK = "BLOCK"
    EJECT = "EJECT"


class DecisionObject(BaseModel):
    state: DecisionState
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)
    human_probability: float = 0.5
    bot_probability: float = 0.5
    explanation: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionArtifact(BaseModel):
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    argument_graph: dict[str, Any] = Field(default_factory=dict)
    router: dict[str, Any] = Field(default_factory=dict)
    role_outputs: dict[str, Any] = Field(default_factory=dict)
    reasoning_trace: dict[str, str] = Field(default_factory=dict)
    synthesis: dict[str, Any] = Field(default_factory=dict)
