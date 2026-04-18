from __future__ import annotations

import uuid
from typing import Any, Dict, List

from truepresence.decision import reason_codes as rc
from truepresence.decision.decision_object import DecisionObject, DecisionState


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _average(values: List[float], default: float = 0.5) -> float:
    if not values:
        return default
    return sum(values) / len(values)


def _risk_rank(risk_level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(risk_level, 0)


def _max_risk(left: str, right: str) -> str:
    return left if _risk_rank(left) >= _risk_rank(right) else right


def _explanation_for_state(state: str) -> str:
    explanations = {
        DecisionState.ALLOW.value: "Signals are coherent enough to allow the session.",
        DecisionState.OBSERVE.value: "Signals are mixed; keep the session under observation.",
        DecisionState.ELEVATED_OBSERVE.value: "Signals are mixed with elevated risk; continue with stronger observation.",
        DecisionState.CHALLENGE.value: "The session should complete an active challenge before proceeding.",
        DecisionState.STEP_UP_AUTH.value: "The session should be stepped up for stronger verification.",
        DecisionState.RESTRICT.value: "Limit high-risk actions while the session is evaluated further.",
        DecisionState.BLOCK.value: "The session should be blocked based on ensemble risk.",
        DecisionState.EJECT.value: "Deterministic policy violations require immediate removal.",
    }
    return explanations.get(state, "")


def synthesize_decision(*, packet, graph, role_reports, tier: str, context: dict) -> DecisionObject:
    reason_codes: List[str] = []
    state = DecisionState.ALLOW.value
    enforcement = "allow"
    confidence = 0.5
    risk_level = "low"

    human_probability = _average(
        [_coerce_float(report.get("human_probability")) for report in (role_reports or []) if report.get("human_probability") is not None],
        default=0.5,
    )
    role_confidence = _average(
        [_coerce_float(report.get("confidence")) for report in (role_reports or []) if report.get("confidence") is not None],
        default=0.5,
    )
    confidence = max(confidence, role_confidence)
    bot_probability = max(0.0, min(1.0, 1.0 - human_probability))

    if tier == "tier0":
        risk_level = "high"
        confidence = 0.99
        human_probability = 0.01
        bot_probability = 0.99
        if packet.provenance.get("invalid_attestation"):
            reason_codes.append(rc.INVALID_ATTESTATION)
        if packet.behavioral_features.get("known_automation_fingerprint"):
            reason_codes.append(rc.KNOWN_AUTOMATION_FINGERPRINT)
        if packet.risk_context.get("impossible_event_sequence"):
            reason_codes.append(rc.IMPOSSIBLE_EVENT_SEQUENCE)
        if packet.challenge_data.get("status") == "deterministic_failure":
            reason_codes.append(rc.CHALLENGE_FAILURE_DETERMINISTIC)

        state = DecisionState.EJECT.value
        enforcement = "eject"
    else:
        if packet.policy_context.get("require_step_up"):
            reason_codes.append(rc.POLICY_REQUIRES_STEP_UP)
            state = DecisionState.STEP_UP_AUTH.value
            enforcement = "step_up_auth"
            confidence = max(confidence, 0.75)
            risk_level = _max_risk(risk_level, "medium")

        if packet.identity_refs.get("cluster_risk") == "high":
            if rc.CROSS_SESSION_CLUSTER_MATCH not in reason_codes:
                reason_codes.append(rc.CROSS_SESSION_CLUSTER_MATCH)
            if tier == "tier2":
                state = DecisionState.CHALLENGE.value
                enforcement = "challenge"
                confidence = max(confidence, 0.80)
                risk_level = _max_risk(risk_level, "high")

        if packet.timing_features.get("constant_latency_pattern"):
            if rc.TIMING_AUTOMATION_PATTERN not in reason_codes:
                reason_codes.append(rc.TIMING_AUTOMATION_PATTERN)
            if state == DecisionState.ALLOW.value:
                state = DecisionState.CHALLENGE.value
                enforcement = "challenge"
                confidence = max(confidence, 0.70)
                risk_level = _max_risk(risk_level, "medium")

        if tier == "tier2" and packet.policy_context.get("high_value_flow"):
            if rc.HIGH_VALUE_TRANSACTION_ESCALATION not in reason_codes:
                reason_codes.append(rc.HIGH_VALUE_TRANSACTION_ESCALATION)
            if state in {DecisionState.ALLOW.value, DecisionState.OBSERVE.value}:
                state = DecisionState.STEP_UP_AUTH.value
                enforcement = "step_up_auth"
                confidence = max(confidence, 0.80)
                risk_level = _max_risk(risk_level, "high")

        disagreement = 0.0
        for report in role_reports or []:
            disagreement = max(disagreement, _coerce_float(report.get("metadata", {}).get("disagreement_score"), 0.0))

        if disagreement > 0.8:
            if rc.EXCESSIVE_ROLE_DISAGREEMENT not in reason_codes:
                reason_codes.append(rc.EXCESSIVE_ROLE_DISAGREEMENT)
            state = DecisionState.RESTRICT.value
            enforcement = "restrict"
            confidence = max(confidence, 0.65)
            risk_level = _max_risk(risk_level, "medium")
        elif disagreement > 0.5 and state == DecisionState.ALLOW.value:
            state = DecisionState.ELEVATED_OBSERVE.value
            enforcement = "observe"
            confidence = max(confidence, 0.6)
            risk_level = _max_risk(risk_level, "medium")

        if human_probability <= 0.25 and confidence >= 0.75:
            state = DecisionState.BLOCK.value
            enforcement = "block"
            risk_level = _max_risk(risk_level, "high")
        elif human_probability <= 0.45 and state == DecisionState.ALLOW.value:
            state = DecisionState.OBSERVE.value
            enforcement = "observe"
            risk_level = _max_risk(risk_level, "medium")

    return DecisionObject(
        decision_id=str(uuid.uuid4()),
        session_id=packet.session_id,
        tenant_id=packet.tenant_id,
        surface=packet.surface,
        state=state,
        recommended_enforcement=enforcement,
        confidence=confidence,
        risk_level=risk_level,
        reason_codes=list(dict.fromkeys(reason_codes)),
        challenge_required=(state == DecisionState.CHALLENGE.value),
        step_up_required=(state == DecisionState.STEP_UP_AUTH.value),
        human_review_required=(state == DecisionState.RESTRICT.value and tier == "tier2"),
        evidence_packet_id=packet.packet_id,
        argument_graph_id=f"graph:{packet.packet_id}",
        role_report_ids=[r.get("report_id") for r in (role_reports or []) if isinstance(r, dict) and r.get("report_id")],
        decision_trace_id=f"trace:{packet.packet_id}",
        tier_path=tier,
        metadata={},
        human_probability=human_probability,
        bot_probability=bot_probability,
        explanation=_explanation_for_state(state),
    )


class DecisionSynthesizer:
    """Compatibility wrapper around the canonical V1 decision synthesizer."""

    def synthesize(
        self,
        *,
        packet,
        argument_graph,
        ensemble_result: Dict[str, Any] | None = None,
        route: Any | None = None,
        role_reports: List[Dict[str, Any]] | None = None,
        tier: str | None = None,
        context: Dict[str, Any] | None = None,
    ) -> DecisionObject:
        reports = role_reports
        if reports is None and ensemble_result and isinstance(ensemble_result.get("role_reports"), list):
            reports = ensemble_result.get("role_reports", [])
        if reports is None:
            reports = []
        resolved_tier = tier or ("tier0" if route is not None else "tier1")
        return synthesize_decision(
            packet=packet,
            graph=argument_graph,
            role_reports=reports,
            tier=resolved_tier,
            context=context or {},
        )
