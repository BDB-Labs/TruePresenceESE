from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SAFETY_REASON_CODES = {
    "instant_media_post_after_join",
    "media_burst_pattern",
    "rapid_delete_repost_pattern",
    "coordinated_media_distribution_cluster",
    "new_account_high_risk_media_behavior",
    "repeat_group_hopping_pattern",
}

SAFETY_RECOMMENDED_ACTIONS = {
    "quarantine_message",
    "restrict_sender",
    "admin_review",
    "mandatory_safety_escalation",
}

SafetySeverity = Literal["medium", "high", "critical"]


class TelegramSafetyFeatures(BaseModel):
    """Derived Telegram media-distribution behavior only; no media content."""

    model_config = ConfigDict(extra="forbid")

    chat_id: int | str | None = None
    message_id: int | str | None = None
    sender_id: int | str | None = None
    event_timestamp: int | float | None = None
    event_type: str = "message"
    media_present: bool = False
    join_to_first_media_ms: float | None = Field(default=None, ge=0)
    media_count_window: int = Field(default=0, ge=0)
    media_burst_count: int = Field(default=0, ge=0)
    synchronized_media_peer_count: int = Field(default=0, ge=0)
    group_hop_count: int = Field(default=0, ge=0)
    account_age_days: int | None = Field(default=None, ge=0)
    rapid_delete_repost_count: int = Field(default=0, ge=0)


class SafetySignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason_code: str
    severity: SafetySeverity
    confidence: float = Field(ge=0, le=1)
    explanation: str


def _signal(
    reason_code: str,
    severity: SafetySeverity,
    confidence: float,
    explanation: str,
) -> SafetySignal:
    return SafetySignal(
        reason_code=reason_code,
        severity=severity,
        confidence=max(0.0, min(1.0, confidence)),
        explanation=explanation,
    )


def evaluate_telegram_safety_policy(features: TelegramSafetyFeatures) -> list[SafetySignal]:
    if not features.media_present:
        return []

    signals: list[SafetySignal] = []

    if features.join_to_first_media_ms is not None and features.join_to_first_media_ms <= 5_000:
        confidence = 0.86 if features.join_to_first_media_ms <= 1_500 else 0.74
        signals.append(
            _signal(
                "instant_media_post_after_join",
                "critical" if confidence >= 0.85 else "high",
                confidence,
                "Media was posted shortly after the account joined the group.",
            )
        )

    if features.media_count_window >= 3 and features.media_burst_count >= 2:
        confidence = 0.88 if features.media_count_window >= 4 else 0.8
        signals.append(
            _signal(
                "media_burst_pattern",
                "critical" if confidence >= 0.85 else "high",
                confidence,
                "Multiple media messages appeared in a compact rolling window.",
            )
        )

    if features.rapid_delete_repost_count >= 2:
        confidence = 0.84 if features.rapid_delete_repost_count < 4 else 0.9
        signals.append(
            _signal(
                "rapid_delete_repost_pattern",
                "critical" if confidence >= 0.85 else "high",
                confidence,
                "Delete/repost metadata indicates repeated media redistribution behavior.",
            )
        )

    if features.synchronized_media_peer_count >= 2:
        confidence = 0.82 if features.synchronized_media_peer_count < 4 else 0.9
        signals.append(
            _signal(
                "coordinated_media_distribution_cluster",
                "critical" if confidence >= 0.85 else "high",
                confidence,
                "Several distinct peers distributed media within a tight time cluster.",
            )
        )

    if features.group_hop_count >= 3:
        confidence = 0.72 if features.group_hop_count < 5 else 0.82
        signals.append(
            _signal(
                "repeat_group_hopping_pattern",
                "high",
                confidence,
                "The account appears across several groups in recent metadata.",
            )
        )

    account_age = features.account_age_days
    high_risk_behavior = any(
        signal.reason_code
        in {
            "instant_media_post_after_join",
            "media_burst_pattern",
            "coordinated_media_distribution_cluster",
        }
        for signal in signals
    )
    if account_age is not None and account_age <= 30 and high_risk_behavior:
        signals.append(
            _signal(
                "new_account_high_risk_media_behavior",
                "critical",
                0.86,
                "A new account is associated with high-risk media distribution metadata.",
            )
        )

    return signals
