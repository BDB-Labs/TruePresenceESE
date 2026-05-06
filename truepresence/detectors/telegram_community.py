from __future__ import annotations

from truepresence.detectors.human_plausibility import (
    ContributionTarget,
    DetectorSignal,
    Severity,
    SignalCategory,
    _signal,
)
from truepresence.surfaces.telegram.community import TelegramCommunityFeatures


def _telegram_signal(
    reason_code: str,
    severity: Severity,
    confidence: float,
    contribution_target: ContributionTarget,
    category: SignalCategory,
    explanation: str,
) -> DetectorSignal:
    return _signal(
        reason_code,
        severity,
        confidence,
        contribution_target,
        explanation,
        category=category,
    )


def join_to_action_plausibility(
    features: TelegramCommunityFeatures | None,
) -> list[DetectorSignal]:
    if features is None or features.join_to_first_message_ms is None:
        return []
    latency = features.join_to_first_message_ms
    if latency > 10_000:
        return []

    severity: Severity = "medium"
    confidence = 0.62
    if latency <= 1_500:
        severity = "high"
        confidence = 0.78

    return [
        _telegram_signal(
            "join_to_action_plausibility",
            severity,
            confidence,
            "automation",
            "session_continuity",
            "First observed action followed the join event unusually quickly.",
        )
    ]


def instant_post_after_join(
    features: TelegramCommunityFeatures | None,
) -> list[DetectorSignal]:
    if features is None or features.join_to_first_message_ms is None:
        return []
    latency = features.join_to_first_message_ms
    if latency > 3_000:
        return []

    severity: Severity = "medium"
    confidence = 0.7
    if latency <= 1_000:
        severity = "high"
        confidence = 0.84

    return [
        _telegram_signal(
            "instant_post_after_join",
            severity,
            confidence,
            "automation",
            "session_continuity",
            "A message was posted almost immediately after joining.",
        )
    ]


def link_drop_after_join(
    features: TelegramCommunityFeatures | None,
) -> list[DetectorSignal]:
    if features is None or not features.link_present or features.join_to_first_link_ms is None:
        return []
    latency = features.join_to_first_link_ms
    if latency > 30_000:
        return []

    severity: Severity = "medium"
    confidence = 0.68
    if latency <= 5_000:
        severity = "high"
        confidence = 0.82

    return [
        _telegram_signal(
            "link_drop_after_join",
            severity,
            confidence,
            "automation",
            "environment",
            "A link entity appeared shortly after joining, using Telegram metadata only.",
        )
    ]


def message_burst_pattern(
    features: TelegramCommunityFeatures | None,
) -> list[DetectorSignal]:
    if features is None:
        return []
    message_count = features.message_count_window or 0
    burst_count = features.burst_count or 0
    if message_count < 5 or burst_count < 4:
        return []

    severity: Severity = "medium"
    confidence = 0.7
    if message_count >= 8 or burst_count >= 6:
        severity = "high"
        confidence = 0.82

    return [
        _telegram_signal(
            "message_burst_pattern",
            severity,
            confidence,
            "automation",
            "session_continuity",
            "Multiple messages landed in a compact timing window.",
        )
    ]


def conversation_cadence_anomaly(
    features: TelegramCommunityFeatures | None,
) -> list[DetectorSignal]:
    if features is None:
        return []
    message_count = features.message_count_window or 0
    mean_interval = features.mean_message_interval_ms
    stddev = features.message_interval_stddev_ms
    if message_count < 4 or mean_interval is None or stddev is None:
        return []
    if mean_interval > 3_000 or stddev > 500:
        return []

    severity: Severity = "medium"
    confidence = 0.64
    if message_count >= 6 and stddev <= 150:
        severity = "high"
        confidence = 0.76

    return [
        _telegram_signal(
            "conversation_cadence_anomaly",
            severity,
            confidence,
            "automation",
            "session_continuity",
            "Message intervals are unusually regular over the rolling window.",
        )
    ]


def synchronized_posting_cluster(
    features: TelegramCommunityFeatures | None,
) -> list[DetectorSignal]:
    if features is None:
        return []
    peer_count = features.synchronized_peer_count or 0
    if peer_count < 2:
        return []

    severity: Severity = "medium"
    confidence = 0.68
    if peer_count >= 4:
        severity = "high"
        confidence = 0.82

    return [
        _telegram_signal(
            "synchronized_posting_cluster",
            severity,
            confidence,
            "agentic_control",
            "agentic_behavior",
            "Several distinct peers posted in a tight time cluster.",
        )
    ]


def coordinated_join_pattern(
    features: TelegramCommunityFeatures | None,
) -> list[DetectorSignal]:
    if features is None:
        return []
    join_count = features.joined_within_cluster_count or 0
    if join_count < 5:
        return []

    severity: Severity = "medium"
    confidence = 0.66
    if join_count >= 10:
        severity = "high"
        confidence = 0.82

    return [
        _telegram_signal(
            "coordinated_join_pattern",
            severity,
            confidence,
            "automation",
            "session_continuity",
            "Several users joined the same group in a compact time cluster.",
        )
    ]


def repeat_group_hopping_pattern(
    features: TelegramCommunityFeatures | None,
) -> list[DetectorSignal]:
    if features is None:
        return []
    hop_count = features.group_hop_count or 0
    if hop_count < 3:
        return []

    severity: Severity = "medium"
    confidence = 0.64
    if hop_count >= 5:
        severity = "high"
        confidence = 0.78

    return [
        _telegram_signal(
            "repeat_group_hopping_pattern",
            severity,
            confidence,
            "automation",
            "environment",
            "The account appears across several groups in recent metadata.",
        )
    ]


def run_telegram_community_detectors(
    features: TelegramCommunityFeatures | None,
) -> list[DetectorSignal]:
    signals: list[DetectorSignal] = []
    signals.extend(join_to_action_plausibility(features))
    signals.extend(instant_post_after_join(features))
    signals.extend(link_drop_after_join(features))
    signals.extend(message_burst_pattern(features))
    signals.extend(conversation_cadence_anomaly(features))
    signals.extend(synchronized_posting_cluster(features))
    signals.extend(coordinated_join_pattern(features))
    signals.extend(repeat_group_hopping_pattern(features))
    return signals
