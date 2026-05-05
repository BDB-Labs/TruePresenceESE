from __future__ import annotations

from truepresence.detectors.human_plausibility import (
    paste_or_instant_input,
    zero_correction_pattern,
)
from truepresence.detectors.reading_time import implausible_read_response_time
from truepresence.detectors.typing_cadence import uniform_typing_cadence
from truepresence.sdk.features import (
    ChallengeInteractionFeatures,
    TypingCadenceFeatures,
)


def _reason_codes(signals):
    return {signal.reason_code for signal in signals}


def test_implausibly_fast_response_flagged() -> None:
    signals = implausible_read_response_time(
        ChallengeInteractionFeatures(
            response_latency_ms=220,
            expected_reading_time_ms=1600,
        )
    )

    assert "implausible_read_response_time" in _reason_codes(signals)


def test_plausible_reading_response_time_not_flagged() -> None:
    signals = implausible_read_response_time(
        ChallengeInteractionFeatures(
            response_latency_ms=2800,
            expected_reading_time_ms=1600,
        )
    )

    assert "implausible_read_response_time" not in _reason_codes(signals)


def test_perfectly_uniform_typing_cadence_flagged() -> None:
    signals = uniform_typing_cadence(
        TypingCadenceFeatures(
            mean_inter_key_interval_ms=120,
            inter_key_interval_stddev_ms=0,
            characters_per_minute=260,
        )
    )

    assert "uniform_typing_cadence" in _reason_codes(signals)
    assert signals[0].severity in {"medium", "high"}


def test_human_like_typing_variance_not_flagged() -> None:
    signals = uniform_typing_cadence(
        TypingCadenceFeatures(
            mean_inter_key_interval_ms=190,
            inter_key_interval_stddev_ms=68,
            characters_per_minute=190,
        )
    )

    assert "uniform_typing_cadence" not in _reason_codes(signals)


def test_paste_or_instant_input_flagged() -> None:
    signals = paste_or_instant_input(
        TypingCadenceFeatures(
            characters_per_minute=900,
            paste_count=1,
            focus_to_first_input_ms=15,
            prompt_render_to_first_input_ms=35,
            typing_duration_ms=25,
        )
    )

    assert "paste_or_instant_input" in _reason_codes(signals)


def test_zero_correction_alone_is_weak() -> None:
    signals = zero_correction_pattern(
        TypingCadenceFeatures(
            characters_per_minute=185,
            correction_count=0,
            correction_rate=0,
            inter_key_interval_stddev_ms=72,
        )
    )

    assert len(signals) == 1
    assert signals[0].reason_code == "zero_correction_pattern"
    assert signals[0].severity == "low"
    assert signals[0].confidence < 0.5
