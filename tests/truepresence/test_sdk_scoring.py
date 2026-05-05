from __future__ import annotations

from truepresence.detectors.human_plausibility import DetectorSignal
from truepresence.scoring.model import score_interaction
from truepresence.sdk.contracts import InteractionFeaturePacket
from truepresence.sdk.features import (
    ChallengeInteractionFeatures,
    PointerBehaviorFeatures,
    TypingCadenceFeatures,
)


def test_multiple_suspicious_signals_raise_automation_likelihood() -> None:
    result = score_interaction(
        signals=[
            DetectorSignal(
                reason_code="uniform_typing_cadence",
                severity="high",
                confidence=0.86,
                contribution_target="automation",
                explanation="Cadence variance is near zero.",
            ),
            DetectorSignal(
                reason_code="paste_or_instant_input",
                severity="medium",
                confidence=0.76,
                contribution_target="automation",
                explanation="Input appeared immediately after focus.",
            ),
            DetectorSignal(
                reason_code="implausible_read_response_time",
                severity="medium",
                confidence=0.72,
                contribution_target="agentic_control",
                explanation="Response was faster than plausible reading time.",
            ),
        ],
        feature_packet=InteractionFeaturePacket(),
    )

    assert result.automation_likelihood > 0.6
    assert result.human_presence_likelihood < 0.45
    assert set(result.reason_codes) == {
        "uniform_typing_cadence",
        "paste_or_instant_input",
        "implausible_read_response_time",
    }


def test_isolated_weak_signal_does_not_overfire() -> None:
    result = score_interaction(
        signals=[
            DetectorSignal(
                reason_code="zero_correction_pattern",
                severity="low",
                confidence=0.35,
                contribution_target="automation",
                explanation="No corrections observed.",
            )
        ],
        feature_packet=InteractionFeaturePacket(),
    )

    assert result.automation_likelihood < 0.45
    assert result.recommended_action in {"allow", "observe"}


def test_human_like_features_produce_higher_human_presence_likelihood() -> None:
    result = score_interaction(
        signals=[],
        feature_packet=InteractionFeaturePacket(
            typing=TypingCadenceFeatures(
                mean_inter_key_interval_ms=190,
                inter_key_interval_stddev_ms=72,
                characters_per_minute=190,
                correction_count=2,
                correction_rate=0.04,
                paste_count=0,
                focus_to_first_input_ms=420,
                prompt_render_to_first_input_ms=1100,
            ),
            challenge=ChallengeInteractionFeatures(
                response_latency_ms=3600,
                expected_reading_time_ms=1500,
            ),
            pointer=PointerBehaviorFeatures(
                pointer_entropy=0.68,
                click_hesitation_ms=240,
                scroll_cadence_score=0.63,
            ),
        ),
    )

    assert result.human_presence_likelihood > result.automation_likelihood
    assert result.human_presence_likelihood > 0.6


def test_agentic_control_likelihood_remains_separate_from_generic_automation() -> None:
    result = score_interaction(
        signals=[
            DetectorSignal(
                reason_code="implausible_read_response_time",
                severity="high",
                confidence=0.9,
                contribution_target="agentic_control",
                explanation="Prompt response beat the expected reading window.",
            )
        ],
        feature_packet=InteractionFeaturePacket(),
    )

    assert result.agentic_control_likelihood > result.automation_likelihood
    assert result.automation_likelihood < 0.55
