from __future__ import annotations

from truepresence.detectors.human_plausibility import DetectorSignal, _signal
from truepresence.sdk.features import ChallengeInteractionFeatures


def implausible_read_response_time(
    features: ChallengeInteractionFeatures | None,
) -> list[DetectorSignal]:
    if features is None:
        return []
    if features.response_latency_ms is None or features.expected_reading_time_ms is None:
        return []
    if features.expected_reading_time_ms <= 0:
        return []

    response_latency = features.response_latency_ms
    plausible_floor = max(350.0, features.expected_reading_time_ms * 0.55)
    if response_latency >= plausible_floor:
        return []

    ratio = response_latency / plausible_floor if plausible_floor else 1.0
    severity = "medium"
    if response_latency <= 300 or ratio <= 0.35:
        severity = "high"

    confidence = min(0.92, 0.55 + ((1 - ratio) * 0.45))
    return [
        _signal(
            "implausible_read_response_time",
            severity,
            confidence,
            "agentic_control",
            "Response latency was faster than the expected human read-and-respond window.",
        )
    ]
