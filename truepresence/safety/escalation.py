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

_PROVIDER_CONFIDENCE_FALLBACK = 0.55
_REASON_CONFIDENCE_BONUS = 0.04
_MAX_REASON_CONFIDENCE_BONUS = 0.12


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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _provider_assessment_confidence(provider: ProviderRiskSignal | None) -> float:
    if provider is None:
        return 0.0
    if provider.confidence is not None:
        return _clamp01(provider.confidence)
    return min(_PROVIDER_CONFIDENCE_FALLBACK, _clamp01(provider.risk_score))


def _has_sufficient_metadata(
    features: TelegramSafetyFeatures,
    provider: ProviderRiskSignal | None,
) -> bool:
    references = [
        features.chat_id,
        features.message_id,
        features.sender_id,
        features.event_timestamp,
    ]
    present_reference_count = sum(reference is not None for reference in references)
    if provider is not None and provider.provider_reference_id:
        present_reference_count += 1
    return features.media_present and present_reference_count >= 3


def _reason_corroboration_bonus(
    *,
    reason_codes: list[str],
    features: TelegramSafetyFeatures,
    provider: ProviderRiskSignal | None,
) -> float:
    if not _has_sufficient_metadata(features, provider):
        return 0.0
    additional_reasons = max(0, len(set(reason_codes)) - 1)
    return min(_MAX_REASON_CONFIDENCE_BONUS, additional_reasons * _REASON_CONFIDENCE_BONUS)


def _assessment_confidence(
    *,
    signals: list[SafetySignal],
    provider: ProviderRiskSignal | None,
    reason_codes: list[str],
    features: TelegramSafetyFeatures,
) -> float:
    signal_confidence = max((signal.confidence for signal in signals), default=0.0)
    provider_confidence = _provider_assessment_confidence(provider)
    reason_bonus = _reason_corroboration_bonus(
        reason_codes=reason_codes,
        features=features,
        provider=provider,
    )
    return _clamp01(max(signal_confidence, provider_confidence) + reason_bonus)


def evaluate_telegram_safety_escalation(
    features: TelegramSafetyFeatures,
    provider_signal: ProviderRiskSignal | dict[str, Any] | None = None,
) -> SafetyEscalation | None:
    provider = _provider_signal_from(provider_signal)
    policy_signals = evaluate_telegram_safety_policy(features)
    signals = list(policy_signals)
    if provider is not None and provider.risk_score >= 0.65:
        signals.append(
            SafetySignal(
                reason_code="new_account_high_risk_media_behavior",
                severity="critical" if provider.risk_score >= 0.85 else "high",
                confidence=_provider_assessment_confidence(provider),
                explanation="Lawful provider supplied a high-risk media reference outcome.",
            )
        )

    reason_codes = list(dict.fromkeys(signal.reason_code for signal in signals))
    if not reason_codes:
        return None

    signal_score = max((signal.confidence for signal in policy_signals), default=0.0)
    provider_score = provider.risk_score if provider is not None else 0.0
    score = max(signal_score, provider_score)
    confidence = _assessment_confidence(
        signals=signals,
        provider=provider,
        reason_codes=reason_codes,
        features=features,
    )
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
