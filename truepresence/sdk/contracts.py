from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from truepresence.sdk.features import (
    ChallengeInteractionFeatures,
    EnvironmentFeatures,
    ExternalRiskProviderFeatures,
    PointerBehaviorFeatures,
    SessionContinuityFeatures,
    TypingCadenceFeatures,
)
from truepresence.sdk.privacy import ensure_privacy_safe_payload

RecommendedAction = Literal["allow", "observe", "soft_challenge", "step_up_auth", "manual_review"]
EnforcementMode = Literal["observe", "challenge_only", "review_required", "enforce"]


class InteractionFeaturePacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    surface: str = "web"
    site_id: str | None = None
    tenant_id: str | None = None
    session_id: str | None = None
    flow_id: str | None = None
    page_context: dict[str, Any] = Field(default_factory=dict)
    typing: TypingCadenceFeatures | None = None
    pointer: PointerBehaviorFeatures | None = None
    challenge: ChallengeInteractionFeatures | None = None
    session_continuity: SessionContinuityFeatures | None = None
    environment: EnvironmentFeatures | None = None
    external_risk: list[ExternalRiskProviderFeatures] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_raw_content(cls, data: Any) -> Any:
        ensure_privacy_safe_payload(data)
        return data


class TruePresenceEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    tenant_id: str = "default"
    enforcement_mode: EnforcementMode = "observe"
    feature_packet: InteractionFeaturePacket
    request_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_raw_content(cls, data: Any) -> Any:
        ensure_privacy_safe_payload(data)
        return data


class TruePresenceEvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    human_presence_likelihood: float = Field(ge=0, le=1)
    automation_likelihood: float = Field(ge=0, le=1)
    agentic_control_likelihood: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list)
    evidence_packet_id: str
    recommended_action: RecommendedAction
    enforcement_mode: EnforcementMode = "observe"
