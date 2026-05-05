"""
Tests for the calibrated probabilistic scoring model.

Covers both the original behavioral contracts (updated for v1 shapes) and
the new requirements specified in feature/scoring-calibration-v1:

  - Multiple same-category signals do not overcount
  - Cross-category signals increase risk more than same-category signals
  - Contradictory signals reduce confidence
  - Low evidence limits confidence
  - Automation alone does not create high agentic_control_likelihood
  - High risk + low confidence does not escalate aggressively
"""

from __future__ import annotations

import pytest

from truepresence.detectors.human_plausibility import DetectorSignal
from truepresence.scoring.model import score_interaction
from truepresence.sdk.contracts import InteractionFeaturePacket
from truepresence.sdk.features import (
    ChallengeInteractionFeatures,
    PointerBehaviorFeatures,
    TypingCadenceFeatures,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auto_signal(
    reason_code: str = "uniform_typing_cadence",
    severity: str = "high",
    confidence: float = 0.86,
    category: str = "typing_cadence",
) -> DetectorSignal:
    return DetectorSignal(
        reason_code=reason_code,
        severity=severity,
        confidence=confidence,
        contribution_target="automation",
        category=category,
        explanation="Test signal.",
    )


def _agentic_signal(
    reason_code: str = "implausible_read_response_time",
    severity: str = "medium",
    confidence: float = 0.72,
    category: str = "agentic_behavior",
) -> DetectorSignal:
    return DetectorSignal(
        reason_code=reason_code,
        severity=severity,
        confidence=confidence,
        contribution_target="agentic_control",
        category=category,
        explanation="Test agentic signal.",
    )


def _empty_packet() -> InteractionFeaturePacket:
    return InteractionFeaturePacket()


def _human_packet() -> InteractionFeaturePacket:
    return InteractionFeaturePacket(
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
    )


# ---------------------------------------------------------------------------
# Existing behavioral contracts (updated for v1 DetectorSignal shape)
# ---------------------------------------------------------------------------

def test_multiple_suspicious_signals_raise_automation_likelihood() -> None:
    result = score_interaction(
        signals=[
            DetectorSignal(
                reason_code="uniform_typing_cadence",
                severity="high",
                confidence=0.86,
                contribution_target="automation",
                category="typing_cadence",
                explanation="Cadence variance is near zero.",
            ),
            DetectorSignal(
                reason_code="paste_or_instant_input",
                severity="medium",
                confidence=0.76,
                contribution_target="automation",
                category="input_method",
                explanation="Input appeared immediately after focus.",
            ),
            DetectorSignal(
                reason_code="implausible_read_response_time",
                severity="medium",
                confidence=0.72,
                contribution_target="agentic_control",
                category="agentic_behavior",
                explanation="Response was faster than plausible reading time.",
            ),
        ],
        feature_packet=_empty_packet(),
    )

    assert result.automation_likelihood > 0.4
    assert result.human_presence_likelihood < 0.6
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
                category="typing_cadence",
                explanation="No corrections observed.",
            )
        ],
        feature_packet=_empty_packet(),
    )

    assert result.automation_likelihood < 0.45
    assert result.recommended_action in {"allow", "observe"}


def test_human_like_features_produce_higher_human_presence_likelihood() -> None:
    result = score_interaction(
        signals=[],
        feature_packet=_human_packet(),
    )

    assert result.human_presence_likelihood > result.automation_likelihood
    assert result.human_presence_likelihood > 0.5


def test_agentic_control_likelihood_remains_separate_from_generic_automation() -> None:
    result = score_interaction(
        signals=[
            DetectorSignal(
                reason_code="implausible_read_response_time",
                severity="high",
                confidence=0.9,
                contribution_target="agentic_control",
                category="agentic_behavior",
                explanation="Prompt response beat the expected reading window.",
            )
        ],
        feature_packet=_empty_packet(),
    )

    assert result.agentic_control_likelihood > result.automation_likelihood
    assert result.automation_likelihood < 0.55


# ---------------------------------------------------------------------------
# NEW: Requirement R1 — same-category signals do not overcount
# ---------------------------------------------------------------------------

def test_same_category_signals_do_not_overcount() -> None:
    """
    Adding 10 signals from the same category should not produce a risk
    significantly higher than a few strong signals from that category.
    The product-of-complements saturates within [0, 1] without unbounded growth.
    """
    few = score_interaction(
        signals=[
            _auto_signal("sig_a", "high", 0.85, "typing_cadence"),
            _auto_signal("sig_b", "high", 0.85, "typing_cadence"),
        ],
        feature_packet=_empty_packet(),
    )
    many = score_interaction(
        signals=[
            _auto_signal(f"sig_{i}", "high", 0.85, "typing_cadence")
            for i in range(10)
        ],
        feature_packet=_empty_packet(),
    )
    # Many same-category signals can increase risk but must stay bounded
    assert many.automation_likelihood <= 1.0
    # Should not produce dramatically higher risk vs. 2 strong signals
    assert many.automation_likelihood < few.automation_likelihood + 0.30


# ---------------------------------------------------------------------------
# NEW: Requirement R2 — cross-category signals increase risk more
# ---------------------------------------------------------------------------

def test_cross_category_signals_increase_risk_more_than_same_category() -> None:
    """
    Two signals from different categories should produce a higher combined risk
    than two equal-strength signals from the same category.
    """
    same_cat = score_interaction(
        signals=[
            _auto_signal("s1", "high", 0.85, "typing_cadence"),
            _auto_signal("s2", "high", 0.85, "typing_cadence"),
        ],
        feature_packet=_empty_packet(),
    )
    diff_cat = score_interaction(
        signals=[
            _auto_signal("s1", "high", 0.85, "typing_cadence"),
            _auto_signal("s2", "high", 0.85, "input_method"),
        ],
        feature_packet=_empty_packet(),
    )
    # Cross-category gets corroboration bonus and separate category aggregation
    assert diff_cat.automation_likelihood >= same_cat.automation_likelihood


# ---------------------------------------------------------------------------
# NEW: Requirement R3 — contradictory signals reduce confidence
# ---------------------------------------------------------------------------

def test_contradictory_signals_reduce_confidence() -> None:
    """
    Strong human packet + strong automation signals should trigger the
    contradiction path and result in lower confidence than automation alone.
    """
    no_contradiction = score_interaction(
        signals=[
            _auto_signal("s1", "high", 0.90, "typing_cadence"),
            _auto_signal("s2", "high", 0.90, "input_method"),
        ],
        feature_packet=_empty_packet(),
    )
    with_contradiction = score_interaction(
        signals=[
            _auto_signal("s1", "high", 0.90, "typing_cadence"),
            _auto_signal("s2", "high", 0.90, "input_method"),
        ],
        feature_packet=_human_packet(),
    )
    assert with_contradiction.confidence <= no_contradiction.confidence


# ---------------------------------------------------------------------------
# NEW: Requirement R4 — low evidence limits confidence
# ---------------------------------------------------------------------------

def test_low_evidence_limits_confidence() -> None:
    """
    A single weak signal should produce a low confidence value regardless
    of whether the risk itself is moderate.
    """
    result = score_interaction(
        signals=[
            _auto_signal("s1", "low", 0.30, "typing_cadence"),
        ],
        feature_packet=_empty_packet(),
    )
    # With only 1 low-strength signal, sufficiency is low → confidence is low
    assert result.confidence < 0.50


def test_zero_signals_has_minimal_confidence() -> None:
    result = score_interaction(signals=[], feature_packet=_empty_packet())
    assert result.confidence < 0.30


# ---------------------------------------------------------------------------
# NEW: Requirement R5 — automation alone does not drive agentic_control high
# ---------------------------------------------------------------------------

def test_automation_alone_does_not_create_high_agentic_control_likelihood() -> None:
    """
    Pure automation signals (typing_cadence, input_method) must not inflate
    agentic_control_likelihood. The two channels are independent.
    """
    result = score_interaction(
        signals=[
            _auto_signal("s1", "high", 0.90, "typing_cadence"),
            _auto_signal("s2", "high", 0.90, "input_method"),
            _auto_signal("s3", "high", 0.90, "typing_cadence"),
        ],
        feature_packet=_empty_packet(),
    )
    # automation can be high, but agentic must stay low without agentic signals
    assert result.agentic_control_likelihood < 0.25


# ---------------------------------------------------------------------------
# NEW: Requirement R6 — high risk + low confidence does not escalate aggressively
# ---------------------------------------------------------------------------

def test_high_risk_low_confidence_does_not_escalate_to_manual_review() -> None:
    """
    When risk is elevated but confidence is limited (sparse evidence),
    the system should not jump straight to manual_review.
    """
    # Single weak agentic signal: risk may be moderate but sufficiency is minimal
    result = score_interaction(
        signals=[
            _agentic_signal("s1", "medium", 0.55, "agentic_behavior"),
        ],
        feature_packet=_empty_packet(),
    )
    assert result.recommended_action != "manual_review"
