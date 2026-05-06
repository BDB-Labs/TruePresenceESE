from __future__ import annotations

from truepresence.detectors.human_plausibility import DetectorSignal, Severity, _signal
from truepresence.sdk.features import AgenticBehaviorFeatures


def _agentic_signal(
    reason_code: str,
    severity: Severity,
    confidence: float,
    explanation: str,
) -> DetectorSignal:
    return _signal(
        reason_code,
        severity,
        confidence,
        "agentic_control",
        explanation,
        category="agentic_behavior",
    )


def model_thinking_cadence(features: AgenticBehaviorFeatures | None) -> list[DetectorSignal]:
    if features is None:
        return []
    bursts = features.action_burst_count or 0
    mean_interval = features.mean_burst_interval_ms
    stddev = features.burst_interval_stddev_ms
    idle_latency = features.idle_to_action_latency_ms
    if bursts < 3 or mean_interval is None or stddev is None:
        return []
    if mean_interval < 1200 or mean_interval > 8000:
        return []
    if stddev > 450:
        return []

    severity: Severity = "medium"
    confidence = 0.68
    if bursts >= 4 and mean_interval >= 2200 and stddev <= 180:
        severity = "high"
        confidence = 0.82
    if idle_latency is not None and idle_latency >= 2000:
        confidence = min(0.9, confidence + 0.05)

    return [
        _agentic_signal(
            "model_thinking_cadence",
            severity,
            confidence,
            "Action bursts are separated by regular pause intervals consistent with plan/act loops.",
        )
    ]


def burst_pause_action_loop(features: AgenticBehaviorFeatures | None) -> list[DetectorSignal]:
    if features is None:
        return []
    bursts = features.action_burst_count or 0
    mean_interval = features.mean_burst_interval_ms
    if bursts < 3 or mean_interval is None or mean_interval < 900:
        return []

    severity: Severity = "medium" if bursts < 5 else "high"
    confidence = min(0.86, 0.56 + bursts * 0.06)
    return [
        _agentic_signal(
            "burst_pause_action_loop",
            severity,
            confidence,
            "The session alternates between compact action bursts and pauses.",
        )
    ]


def large_instant_input_delta(features: AgenticBehaviorFeatures | None) -> list[DetectorSignal]:
    if features is None:
        return []
    delta_count = features.large_instant_delta_count or 0
    if delta_count <= 0:
        return []

    submit_latency = features.submit_after_instant_input_ms
    severity: Severity = "medium"
    confidence = 0.66
    if delta_count >= 2 or (submit_latency is not None and submit_latency <= 250):
        severity = "high"
        confidence = 0.82

    return [
        _agentic_signal(
            "large_instant_input_delta",
            severity,
            confidence,
            "Input length changed by a large aggregate delta in one event without storing content.",
        )
    ]


def low_exploratory_noise(features: AgenticBehaviorFeatures | None) -> list[DetectorSignal]:
    if features is None:
        return []
    exploratory = features.exploratory_action_count
    directness = features.route_directness_score
    if exploratory is None or directness is None:
        return []
    if exploratory > 1 or directness < 0.85:
        return []

    severity: Severity = "medium" if directness < 0.95 else "high"
    confidence = 0.62 if severity == "medium" else 0.74
    return [
        _agentic_signal(
            "low_exploratory_noise",
            severity,
            confidence,
            "The interaction path is unusually direct with little exploratory activity.",
        )
    ]


def structured_retry_pattern(features: AgenticBehaviorFeatures | None) -> list[DetectorSignal]:
    if features is None:
        return []
    retries = features.structured_retry_count or 0
    repairs = features.validation_repair_count or 0
    if retries < 2 and repairs < 2:
        return []

    severity: Severity = "medium"
    confidence = 0.66
    if retries >= 3 or repairs >= 3:
        severity = "high"
        confidence = 0.8

    return [
        _agentic_signal(
            "structured_retry_pattern",
            severity,
            confidence,
            "Retry and validation-repair counts follow a structured correction pattern.",
        )
    ]


def implausible_task_efficiency(features: AgenticBehaviorFeatures | None) -> list[DetectorSignal]:
    if features is None:
        return []
    directness = features.route_directness_score
    idle_latency = features.idle_to_action_latency_ms
    submit_latency = features.submit_after_instant_input_ms
    exploratory = features.exploratory_action_count
    if directness is None or idle_latency is None or submit_latency is None or exploratory is None:
        return []
    if directness < 0.9 or idle_latency > 250 or submit_latency > 450 or exploratory > 1:
        return []

    severity: Severity = "medium"
    confidence = 0.68
    if directness >= 0.96 and idle_latency <= 120 and submit_latency <= 300:
        severity = "high"
        confidence = 0.82

    return [
        _agentic_signal(
            "implausible_task_efficiency",
            severity,
            confidence,
            "The task path is highly direct with very low idle-to-action and submit latency.",
        )
    ]


def run_agentic_control_detectors(
    features: AgenticBehaviorFeatures | None,
) -> list[DetectorSignal]:
    signals: list[DetectorSignal] = []
    signals.extend(model_thinking_cadence(features))
    signals.extend(burst_pause_action_loop(features))
    signals.extend(large_instant_input_delta(features))
    signals.extend(low_exploratory_noise(features))
    signals.extend(structured_retry_pattern(features))
    signals.extend(implausible_task_efficiency(features))
    return signals
