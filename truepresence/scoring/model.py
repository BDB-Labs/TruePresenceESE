"""
Calibrated probabilistic scoring model for TruePresence.

Replaces the v0 additive/linear model with a mathematically grounded approach:

  1. Per-signal strength  = severity_weight * confidence * category_weight
  2. Category aggregation = 1 - Π(1 - signal_strength_i)   [within each category]
  3. Risk aggregation     = 1 - Π(1 - cat_weight * cat_strength)  [across categories]
  4. Corroboration bonus  = +0.05 per independent category beyond 1, capped at 0.15
  5. Human-support reduction = adjusted_risk = risk * (1 - human_strength * 0.6)
  6. Contradiction penalty   = −20% if human_strength > 0.5 and risk > 0.5
  7. Evidence sufficiency    = f(n_categories, n_signals), range [0.2, 1.0]
  8. Confidence              = sufficiency * (1 - contradiction_penalty) * adjusted_risk
  9. recommended_action      = f(adjusted_risk, confidence)
 10. agentic_control_likelihood is derived solely from agentic_control signals,
     NOT from automation spillover.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict

from truepresence.detectors.human_plausibility import DetectorSignal
from truepresence.scoring.weights import (
    BASE_HUMAN_PRESENCE,
    CATEGORY_WEIGHTS,
    SEVERITY_WEIGHTS,
)
from truepresence.sdk.contracts import (
    EnforcementMode,
    InteractionFeaturePacket,
    RecommendedAction,
    TruePresenceEvaluationResponse,
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# Human-feature support (unchanged from v0 — direct feature extraction)
# ---------------------------------------------------------------------------

def _human_feature_support(packet: InteractionFeaturePacket) -> float:
    support = 0.0

    typing = packet.typing
    if typing is not None:
        stddev = typing.inter_key_interval_stddev_ms
        cpm = typing.characters_per_minute
        if stddev is not None and 25 <= stddev <= 220 and cpm is not None and 80 <= cpm <= 420:
            support += 0.09
        if (typing.correction_count or 0) > 0 or (typing.correction_rate or 0) > 0:
            support += 0.05
        if (typing.paste_count or 0) == 0:
            support += 0.03
        if (
            typing.focus_to_first_input_ms is not None
            and typing.focus_to_first_input_ms >= 150
        ):
            support += 0.03

    challenge = packet.challenge
    if (
        challenge is not None
        and challenge.response_latency_ms is not None
        and challenge.expected_reading_time_ms is not None
        and challenge.response_latency_ms >= max(350.0, challenge.expected_reading_time_ms * 0.75)
    ):
        support += 0.07

    pointer = packet.pointer
    if pointer is not None:
        if pointer.pointer_entropy is not None and pointer.pointer_entropy >= 0.35:
            support += 0.04
        if pointer.click_hesitation_ms is not None and pointer.click_hesitation_ms >= 80:
            support += 0.03
        if pointer.scroll_cadence_score is not None and pointer.scroll_cadence_score >= 0.35:
            support += 0.03

    return min(0.30, support)


# ---------------------------------------------------------------------------
# Core probabilistic aggregation helpers
# ---------------------------------------------------------------------------

def _product_of_complements(strengths: list[float]) -> float:
    """Compute 1 - Π(1 - s_i), i.e. probabilistic OR combination."""
    result = 1.0
    for s in strengths:
        result *= (1.0 - _clamp(s))
    return _clamp(1.0 - result)


def _signal_strength(signal: DetectorSignal) -> float:
    """Per-signal strength: severity_weight * confidence."""
    return SEVERITY_WEIGHTS[signal.severity] * signal.confidence


def _partition_signals(
    signals: list[DetectorSignal],
    target: str,
) -> dict[str, list[float]]:
    """
    For a given contribution_target, partition signal strengths by category.
    Returns {category: [strength, ...]} for signals matching that target.
    """
    by_cat: dict[str, list[float]] = defaultdict(list)
    for sig in signals:
        if sig.contribution_target == target:
            by_cat[sig.category].append(_signal_strength(sig))
    return dict(by_cat)


def _aggregate_risk(by_category: dict[str, list[float]]) -> tuple[float, int]:
    """
    Two-level aggregation:
      1. Within each category: category_strength = product_of_complements(signals)
      2. Across categories:    risk = product_of_complements(cat_weight * cat_strength)

    Returns (risk_strength, n_categories_with_signal).
    """
    if not by_category:
        return 0.0, 0

    cat_strengths: list[float] = []
    for cat, strengths in by_category.items():
        cat_strength = _product_of_complements(strengths)
        weighted = CATEGORY_WEIGHTS.get(cat, 0.5) * cat_strength
        cat_strengths.append(weighted)

    return _product_of_complements(cat_strengths), len(by_category)


# ---------------------------------------------------------------------------
# Evidence sufficiency
# ---------------------------------------------------------------------------

def _evidence_sufficiency(n_categories: int, n_signals: int) -> float:
    """
    Estimate how much evidence we have to trust the score.
    Range: [0.2, 1.0]
    - Needs ≥ 1 category and ≥ 1 signal for anything above floor.
    - Approaches 1.0 with 3+ categories and 4+ signals.
    """
    if n_signals == 0:
        return 0.20
    cat_factor = min(1.0, n_categories / 3.0)
    sig_factor = min(1.0, n_signals / 4.0)
    raw = 0.20 + 0.80 * ((cat_factor + sig_factor) / 2.0)
    return _clamp(raw)


# ---------------------------------------------------------------------------
# Main scoring entry point
# ---------------------------------------------------------------------------

def score_interaction(
    *,
    signals: list[DetectorSignal],
    feature_packet: InteractionFeaturePacket,
    enforcement_mode: EnforcementMode = "observe",
) -> TruePresenceEvaluationResponse:

    # ── 1. Human-feature support from raw packet ─────────────────────────
    human_strength = _human_feature_support(feature_packet)

    # ── 2. Partition signals by target and aggregate per target ──────────
    #    automation and agentic_control each get independent aggregation.
    #    human_presence signals reduce risk (treated as corroborating humans).

    automation_by_cat = _partition_signals(signals, "automation")
    agentic_by_cat = _partition_signals(signals, "agentic_control")
    human_signal_by_cat = _partition_signals(signals, "human_presence")

    automation_risk, auto_n_cats = _aggregate_risk(automation_by_cat)
    agentic_risk, agentic_n_cats = _aggregate_risk(agentic_by_cat)
    human_signal_strength, _ = _aggregate_risk(human_signal_by_cat)

    # ── 3. Corroboration bonus ────────────────────────────────────────────
    #    Each independent risk category beyond the first adds +0.05, cap 0.15.
    total_risk_cats = auto_n_cats + agentic_n_cats
    corroboration_bonus = _clamp(min(0.15, max(0, total_risk_cats - 1) * 0.05))

    # Combine automation and agentic into a single risk score, then add bonus
    combined_risk = _product_of_complements([automation_risk, agentic_risk])
    combined_risk = _clamp(combined_risk + corroboration_bonus)

    # ── 4. Human-support reduction ────────────────────────────────────────
    effective_human = _clamp(human_strength + human_signal_strength * 0.5)
    adjusted_risk = _clamp(combined_risk * (1.0 - effective_human * 0.6))

    # ── 5. Contradiction penalty ──────────────────────────────────────────
    #    If strong human evidence coexists with high risk, reduce ~20%.
    contradiction_factor = 0.0
    if effective_human > 0.5 and adjusted_risk > 0.5:
        contradiction_factor = 0.20
        adjusted_risk = _clamp(adjusted_risk * (1.0 - contradiction_factor))

    # ── 6. Evidence sufficiency ───────────────────────────────────────────
    n_risk_signals = sum(
        1 for s in signals if s.contribution_target in ("automation", "agentic_control")
    )
    sufficiency = _evidence_sufficiency(total_risk_cats, n_risk_signals)

    # ── 7. Confidence ─────────────────────────────────────────────────────
    confidence = _clamp(sufficiency * (1.0 - contradiction_factor) * (0.5 + adjusted_risk * 0.5))

    # ── 8. Derived likelihoods ────────────────────────────────────────────
    # automation_likelihood: from automation signals only (no agentic spillover)
    automation_likelihood = _clamp(
        automation_risk * (1.0 - effective_human * 0.6)
    )

    # agentic_control_likelihood: from agentic signals only
    agentic_control_likelihood = _clamp(
        agentic_risk * (1.0 - effective_human * 0.3)
    )

    # human_presence_likelihood: complement of adjusted_risk, anchored to human evidence
    human_presence_likelihood = _clamp(
        BASE_HUMAN_PRESENCE * (1.0 - adjusted_risk) + effective_human * 0.4
    )

    # ── 9. Recommended action ─────────────────────────────────────────────
    recommended_action = _recommended_action(adjusted_risk, confidence)

    reason_codes = sorted({signal.reason_code for signal in signals})

    return TruePresenceEvaluationResponse(
        human_presence_likelihood=round(human_presence_likelihood, 4),
        automation_likelihood=round(automation_likelihood, 4),
        agentic_control_likelihood=round(agentic_control_likelihood, 4),
        confidence=round(confidence, 4),
        reason_codes=reason_codes,
        evidence_packet_id=f"ep_{uuid.uuid4().hex}",
        recommended_action=recommended_action,
        enforcement_mode=enforcement_mode,
    )


def _recommended_action(risk: float, confidence: float) -> RecommendedAction:
    """
    Decision depends on BOTH risk and confidence.
    High risk + low confidence → stay cautious but don't escalate aggressively.
    High risk + high confidence → escalate.
    """
    if risk < 0.30:
        return "allow" if confidence >= 0.50 else "observe"
    if risk < 0.50:
        return "observe" if confidence < 0.45 else "soft_challenge"
    if risk < 0.70:
        if confidence < 0.40:
            return "soft_challenge"
        return "step_up_auth"
    # risk >= 0.70
    if confidence < 0.45:
        return "step_up_auth"
    return "manual_review"
