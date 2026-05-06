from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from truepresence.safety.evidence_minimization import (
    SafetyAction,
    build_safety_evidence_card,
    risk_label_for_score,
)
from truepresence.safety.policy import (
    SafetySignal,
    TelegramSafetyFeatures,
    evaluate_telegram_safety_policy,
)


class ProviderRiskSignal(BaseModel):
    """External lawful-provider reference without local media classification."""

    model_config = ConfigDict(extra="forbid")

    provider_id: str
    provider_reference_id: str
    outcome: str
    risk_score: float = Field(ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)


class TelegramMediaRiskProvider(Protocol):
    def assess_telegram_media(self, metadata: dict[str, Any]) -> ProviderRiskSignal | None:
        """Return a provider reference/outcome for metadata supplied by the caller."""


class SafetyEscalation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_codes: list[str]
    risk_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    risk_label: str
    recommended_action: SafetyAction
    evidence_card: dict[str, Any]
    detector_signals: list[dict[str, Any]] = Field(default_factory=list)


def _provider_signal_from(value: Any) -> ProviderRiskSignal | None:
    if value is None:
        return None
    if isinstance(value, ProviderRiskSignal):
        return value
    if isinstance(value, dict):
        return ProviderRiskSignal(**value)
    return None


def build_telegram_safety_evidence_card(
    *,
    chat_id: int | str | None,
    message_id: int | str | None,
    sender_id: int | str | None,
    event_timestamp: int | float | None,
    event_type: str,
    media_present: bool,
    reason_codes: list[str],
    risk_score: float,
    confidence: float,
    recommended_action: SafetyAction,
    provider_signal: ProviderRiskSignal | dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = _provider_signal_from(provider_signal)
    return build_safety_evidence_card(
        chat_id=chat_id,
        message_id=message_id,
        sender_id=sender_id,
        event_timestamp=event_timestamp,
        event_type=event_type,
        media_present=media_present,
        reason_codes=reason_codes,
        risk_score=risk_score,
        confidence=confidence,
        recommended_action=recommended_action,
        provider_reference_id=provider.provider_reference_id if provider else None,
        provider_outcome=provider.outcome if provider else None,
    )


def _recommended_action(score: float, reason_count: int, provider: ProviderRiskSignal | None) -> SafetyAction:
    if provider is not None and provider.risk_score >= 0.85:
        return "mandatory_safety_escalation"
    if score >= 0.85 or (score >= 0.8 and reason_count >= 2):
        return "mandatory_safety_escalation"
    if score >= 0.8:
        return "restrict_sender"
    if score >= 0.75:
        return "admin_review"
    if score >= 0.65:
        return "quarantine_message"
    return "admin_review"


def evaluate_telegram_safety_escalation(
    features: TelegramSafetyFeatures,
    provider_signal: ProviderRiskSignal | dict[str, Any] | None = None,
) -> SafetyEscalation | None:
    provider = _provider_signal_from(provider_signal)
    signals = evaluate_telegram_safety_policy(features)
    if provider is not None and provider.risk_score >= 0.65:
        signals.append(
            SafetySignal(
                reason_code="new_account_high_risk_media_behavior",
                severity="critical" if provider.risk_score >= 0.85 else "high",
                confidence=provider.confidence or provider.risk_score,
                explanation="Lawful provider supplied a high-risk media reference outcome.",
            )
        )

    reason_codes = list(dict.fromkeys(signal.reason_code for signal in signals))
    if not reason_codes:
        return None

    signal_score = max((signal.confidence for signal in signals), default=0.0)
    provider_score = provider.risk_score if provider is not None else 0.0
    score = max(signal_score, provider_score)
    confidence = max(score, max((provider.confidence or 0.0,) if provider else (0.0,)))
    action = _recommended_action(score, len(reason_codes), provider)
    evidence_card = build_telegram_safety_evidence_card(
        chat_id=features.chat_id,
        message_id=features.message_id,
        sender_id=features.sender_id,
        event_timestamp=features.event_timestamp,
        event_type=features.event_type,
        media_present=features.media_present,
        reason_codes=reason_codes,
        risk_score=score,
        confidence=confidence,
        recommended_action=action,
        provider_signal=provider,
    )
    return SafetyEscalation(
        reason_codes=reason_codes,
        risk_score=score,
        confidence=confidence,
        risk_label=risk_label_for_score(score),
        recommended_action=action,
        evidence_card=evidence_card,
        detector_signals=[signal.model_dump() for signal in signals],
    )
