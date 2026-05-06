from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TelegramCommunityFeatures(BaseModel):
    """Metadata-only Telegram community behavior summaries."""

    model_config = ConfigDict(extra="forbid")

    join_to_first_message_ms: float | None = Field(default=None, ge=0)
    join_to_first_media_ms: float | None = Field(default=None, ge=0)
    join_to_first_link_ms: float | None = Field(default=None, ge=0)
    message_count_window: int | None = Field(default=None, ge=0)
    burst_count: int | None = Field(default=None, ge=0)
    mean_message_interval_ms: float | None = Field(default=None, ge=0)
    message_interval_stddev_ms: float | None = Field(default=None, ge=0)
    joined_within_cluster_count: int | None = Field(default=None, ge=0)
    synchronized_peer_count: int | None = Field(default=None, ge=0)
    group_hop_count: int | None = Field(default=None, ge=0)
    link_present: bool = False
    media_present: bool = False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _feature_summary(value: Any) -> dict[str, Any]:
    if isinstance(value, TelegramCommunityFeatures):
        return value.model_dump(exclude_none=True)
    if isinstance(value, dict):
        return dict(value)
    return {}


def _reason_codes_from(*sources: Any) -> list[str]:
    reason_codes: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        values = source.get("reason_codes")
        if values is None and isinstance(source.get("final"), dict):
            values = source["final"].get("reason_codes")
        if not values:
            continue
        reason_codes.extend(str(value) for value in values)
    return list(dict.fromkeys(reason_codes))


def _detector_signal_summaries(signals: Any) -> list[dict[str, Any]]:
    if not isinstance(signals, list):
        return []
    summaries: list[dict[str, Any]] = []
    for signal in signals:
        if hasattr(signal, "model_dump"):
            signal = signal.model_dump()
        if not isinstance(signal, dict):
            continue
        summaries.append(
            {
                "reason_code": signal.get("reason_code"),
                "severity": signal.get("severity"),
                "confidence": signal.get("confidence"),
                "contribution_target": signal.get("contribution_target"),
                "category": signal.get("category"),
                "explanation": signal.get("explanation"),
            }
        )
    return summaries


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def build_telegram_community_evidence_card(
    *,
    event: dict[str, Any],
    action: dict[str, Any],
    evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a content-minimized Telegram admin evidence card.

    The card intentionally excludes message text, captions, raw media objects,
    file identifiers, and the raw Telegram update body.
    """

    evaluation = evaluation or {}
    context = event.get("context") if isinstance(event, dict) else {}
    community = context.get("telegram_community", {}) if isinstance(context, dict) else {}
    features = _feature_summary(community.get("features"))
    detector_signals = _detector_signal_summaries(community.get("detector_signals"))
    reason_codes = _reason_codes_from(community, evaluation, action)

    detector_confidence = max(
        (float(signal.get("confidence") or 0.0) for signal in detector_signals),
        default=0.0,
    )
    action_confidence = float(action.get("confidence") or 0.0)
    final_confidence = 0.0
    final = evaluation.get("final") if isinstance(evaluation, dict) else None
    if isinstance(final, dict):
        final_confidence = float(final.get("confidence") or 0.0)
    confidence = max(action_confidence, final_confidence, detector_confidence)

    return {
        "surface": "telegram",
        "risk": {
            "score": round(confidence, 3),
            "level": _risk_level(confidence),
        },
        "confidence": round(confidence, 3),
        "reason_codes": reason_codes,
        "timestamps": {
            "event_timestamp": event.get("timestamp") if isinstance(event, dict) else None,
            "created_at": _utc_now_iso(),
        },
        "recommended_action": action.get("action"),
        "feature_summaries": features,
        "detector_signals": detector_signals,
        "actor_refs": {
            "user_id": context.get("user_id") if isinstance(context, dict) else None,
            "group_id": context.get("group_id") if isinstance(context, dict) else None,
        },
        "privacy_boundary": "metadata_only_no_content_preview",
    }
