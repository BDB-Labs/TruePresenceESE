from __future__ import annotations

import uuid

from truepresence.detectors.human_plausibility import DetectorSignal
from truepresence.scoring.weights import (
    BASE_AGENTIC_CONTROL,
    BASE_AUTOMATION,
    BASE_HUMAN_PRESENCE,
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


def _risk_contributions(signals: list[DetectorSignal]) -> tuple[float, float, float]:
    human = 0.0
    automation = 0.0
    agentic = 0.0
    for signal in signals:
        contribution = SEVERITY_WEIGHTS[signal.severity] * signal.confidence
        if signal.contribution_target == "human_presence":
            human += contribution
        elif signal.contribution_target == "automation":
            automation += contribution
        elif signal.contribution_target == "agentic_control":
            agentic += contribution

    return human, automation, agentic


def _recommended_action(
    human_presence_likelihood: float,
    automation_likelihood: float,
    agentic_control_likelihood: float,
) -> RecommendedAction:
    risk = max(automation_likelihood, agentic_control_likelihood)
    if risk < 0.32:
        return "allow" if human_presence_likelihood >= 0.68 else "observe"
    if risk < 0.55:
        return "soft_challenge"
    if risk < 0.75:
        return "step_up_auth"
    return "manual_review"


def score_interaction(
    *,
    signals: list[DetectorSignal],
    feature_packet: InteractionFeaturePacket,
    enforcement_mode: EnforcementMode = "observe",
) -> TruePresenceEvaluationResponse:
    human_signal, automation_signal, agentic_signal = _risk_contributions(signals)
    human_support = _human_feature_support(feature_packet)

    automation_likelihood = _clamp(
        BASE_AUTOMATION + automation_signal + (agentic_signal * 0.15) - (human_support * 0.45)
    )
    agentic_control_likelihood = _clamp(
        BASE_AGENTIC_CONTROL + agentic_signal + (automation_signal * 0.25) - (human_support * 0.25)
    )
    human_presence_likelihood = _clamp(
        BASE_HUMAN_PRESENCE + human_support + human_signal - ((automation_signal + agentic_signal) * 0.70)
    )

    total_signal_weight = automation_signal + agentic_signal + human_signal
    confidence = 0.45 + min(0.35, total_signal_weight * 0.85) + min(0.15, human_support * 0.55)
    if human_support and (automation_signal or agentic_signal):
        confidence -= min(0.18, human_support * 0.6)
    confidence = _clamp(confidence)

    reason_codes = sorted({signal.reason_code for signal in signals})
    recommended_action = _recommended_action(
        human_presence_likelihood,
        automation_likelihood,
        agentic_control_likelihood,
    )

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
