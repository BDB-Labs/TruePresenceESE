from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SafetyAction = Literal[
    "quarantine_message",
    "restrict_sender",
    "admin_review",
    "mandatory_safety_escalation",
]


class SafetyEvidenceCard(BaseModel):
    """Content-minimized safety evidence for Telegram media behavior."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chat_id: int | str | None = None
    message_id: int | str | None = None
    sender_id: int | str | None = None
    timestamps: dict[str, Any] = Field(default_factory=dict)
    media_present: bool
    event_type: str
    reason_codes: list[str] = Field(default_factory=list)
    risk: dict[str, float | str] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    risk_label: Literal["low", "medium", "high", "critical"]
    recommended_action: SafetyAction
    provider_reference_id: str | None = None
    provider_outcome: str | None = None


def risk_label_for_score(score: float) -> Literal["low", "medium", "high", "critical"]:
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def build_safety_evidence_card(
    *,
    chat_id: int | str | None,
    message_id: int | str | None,
    sender_id: int | str | None,
    event_timestamp: Any,
    event_type: str,
    media_present: bool,
    reason_codes: list[str],
    risk_score: float,
    confidence: float,
    recommended_action: SafetyAction,
    provider_reference_id: str | None = None,
    provider_outcome: str | None = None,
    evidence_id: str | None = None,
) -> dict[str, Any]:
    score = max(0.0, min(1.0, float(risk_score)))
    bounded_confidence = max(0.0, min(1.0, float(confidence)))
    card = SafetyEvidenceCard(
        evidence_id=evidence_id or str(uuid.uuid4()),
        chat_id=chat_id,
        message_id=message_id,
        sender_id=sender_id,
        timestamps={"event_timestamp": event_timestamp},
        media_present=bool(media_present),
        event_type=event_type,
        reason_codes=list(dict.fromkeys(reason_codes)),
        risk={"score": round(score, 3), "label": risk_label_for_score(score)},
        confidence=round(bounded_confidence, 3),
        risk_label=risk_label_for_score(score),
        recommended_action=recommended_action,
        provider_reference_id=provider_reference_id,
        provider_outcome=provider_outcome,
    )
    return card.model_dump(exclude_none=True)


def telegram_event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    context = event.get("context", {}) if isinstance(event, dict) else {}
    payload = event.get("payload", {}) if isinstance(event, dict) else {}
    safety = context.get("telegram_safety", {}) if isinstance(context, dict) else {}
    evidence = safety.get("evidence_card", {}) if isinstance(safety, dict) else {}
    if evidence:
        return {
            "chat_id": evidence.get("chat_id"),
            "message_id": evidence.get("message_id"),
            "sender_id": evidence.get("sender_id"),
            "timestamps": dict(evidence.get("timestamps", {})),
            "media_present": bool(evidence.get("media_present", False)),
            "event_type": evidence.get("event_type"),
        }
    return {
        "chat_id": context.get("group_id") if isinstance(context, dict) else None,
        "message_id": payload.get("message_id") if isinstance(payload, dict) else None,
        "sender_id": context.get("user_id") if isinstance(context, dict) else None,
        "timestamps": {"event_timestamp": event.get("timestamp") if isinstance(event, dict) else None},
        "media_present": bool(payload.get("has_attachments")) if isinstance(payload, dict) else False,
        "event_type": event.get("event_type") if isinstance(event, dict) else None,
    }
