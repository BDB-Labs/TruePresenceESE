from __future__ import annotations

from truepresence.detectors.agentic_control import (
    burst_pause_action_loop,
    implausible_task_efficiency,
    large_instant_input_delta,
    low_exploratory_noise,
    model_thinking_cadence,
    run_agentic_control_detectors,
    structured_retry_pattern,
)
from truepresence.detectors.human_plausibility import (
    DetectorSignal,
    run_human_plausibility_detectors,
)
from truepresence.scoring.model import score_interaction
from truepresence.sdk.contracts import InteractionFeaturePacket
from truepresence.sdk.features import AgenticBehaviorFeatures, TypingCadenceFeatures


def _agentic_features(**overrides: float | int) -> AgenticBehaviorFeatures:
    values = {
        "action_burst_count": 1,
        "mean_burst_interval_ms": 900,
        "burst_interval_stddev_ms": 320,
        "idle_to_action_latency_ms": 1400,
        "exploratory_action_count": 8,
        "route_directness_score": 0.55,
        "large_instant_delta_count": 0,
        "submit_after_instant_input_ms": 1200,
        "structured_retry_count": 0,
        "validation_repair_count": 1,
    }
    values.update(overrides)
    return AgenticBehaviorFeatures(**values)


def _reason_codes(signals: list[DetectorSignal]) -> set[str]:
    return {signal.reason_code for signal in signals}


def test_human_like_exploratory_behavior_does_not_trigger_high_agentic_risk() -> None:
    features = _agentic_features(
        action_burst_count=1,
        mean_burst_interval_ms=850,
        burst_interval_stddev_ms=260,
        exploratory_action_count=14,
        route_directness_score=0.48,
        large_instant_delta_count=0,
        submit_after_instant_input_ms=1800,
        structured_retry_count=0,
        validation_repair_count=1,
    )

    signals = run_agentic_control_detectors(features)
    result = score_interaction(
        signals=signals,
        feature_packet=InteractionFeaturePacket(agentic=features),
    )

    assert signals == []
    assert result.agentic_control_likelihood < 0.25


def test_burst_pause_action_cadence_triggers_model_thinking_signal() -> None:
    features = _agentic_features(
        action_burst_count=4,
        mean_burst_interval_ms=3200,
        burst_interval_stddev_ms=120,
        idle_to_action_latency_ms=2800,
        exploratory_action_count=1,
    )

    assert model_thinking_cadence(features)
    signals = burst_pause_action_loop(features)

    assert "burst_pause_action_loop" in _reason_codes(signals)
    assert all(signal.contribution_target == "agentic_control" for signal in signals)
    assert all(signal.category == "agentic_behavior" for signal in signals)


def test_large_instant_input_delta_triggers_agentic_signal() -> None:
    features = _agentic_features(
        large_instant_delta_count=2,
        submit_after_instant_input_ms=180,
        exploratory_action_count=1,
    )

    signals = large_instant_input_delta(features)

    assert "large_instant_input_delta" in _reason_codes(signals)
    assert signals[0].contribution_target == "agentic_control"


def test_structured_retries_trigger_agentic_signal() -> None:
    features = _agentic_features(
        structured_retry_count=3,
        validation_repair_count=3,
        route_directness_score=0.92,
    )

    signals = structured_retry_pattern(features)

    assert "structured_retry_pattern" in _reason_codes(signals)
    assert signals[0].severity in {"medium", "high"}


def test_low_exploration_and_direct_route_trigger_efficiency_signal() -> None:
    features = _agentic_features(
        action_burst_count=3,
        exploratory_action_count=0,
        route_directness_score=0.96,
        idle_to_action_latency_ms=80,
        submit_after_instant_input_ms=240,
    )

    signals = low_exploratory_noise(features) + implausible_task_efficiency(features)

    assert {"low_exploratory_noise", "implausible_task_efficiency"}.issubset(_reason_codes(signals))


def test_detector_runner_includes_agentic_detectors_when_features_present() -> None:
    packet = InteractionFeaturePacket(
        agentic=_agentic_features(
            action_burst_count=4,
            mean_burst_interval_ms=3000,
            burst_interval_stddev_ms=90,
            idle_to_action_latency_ms=2600,
            large_instant_delta_count=1,
            submit_after_instant_input_ms=160,
            structured_retry_count=2,
            validation_repair_count=2,
            exploratory_action_count=0,
            route_directness_score=0.94,
        )
    )

    signals = run_human_plausibility_detectors(packet)

    assert "model_thinking_cadence" in _reason_codes(signals)
    assert "large_instant_input_delta" in _reason_codes(signals)
    assert all(signal.contribution_target == "agentic_control" for signal in signals)


def test_generic_automation_alone_does_not_create_high_agentic_likelihood() -> None:
    automation_signal = DetectorSignal(
        reason_code="uniform_typing_cadence",
        severity="high",
        confidence=0.9,
        contribution_target="automation",
        category="typing_cadence",
        explanation="Generic automation cadence signal.",
    )

    result = score_interaction(
        signals=[automation_signal],
        feature_packet=InteractionFeaturePacket(
            typing=TypingCadenceFeatures(
                inter_key_interval_stddev_ms=1,
                characters_per_minute=900,
            )
        ),
    )

    assert result.automation_likelihood > result.agentic_control_likelihood
    assert result.agentic_control_likelihood < 0.25


def test_explicit_agentic_signals_raise_agentic_control_likelihood() -> None:
    features = _agentic_features(
        action_burst_count=5,
        mean_burst_interval_ms=2800,
        burst_interval_stddev_ms=80,
        idle_to_action_latency_ms=2500,
        exploratory_action_count=0,
        route_directness_score=0.96,
        large_instant_delta_count=2,
        submit_after_instant_input_ms=180,
        structured_retry_count=2,
        validation_repair_count=3,
    )
    signals = run_agentic_control_detectors(features)

    result = score_interaction(
        signals=signals,
        feature_packet=InteractionFeaturePacket(agentic=features),
    )

    assert result.agentic_control_likelihood >= 0.55
    assert result.agentic_control_likelihood > result.automation_likelihood
