from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from truepresence.evidence.argument_graph import ArgumentGraph
from truepresence.evidence.packet_builder import EvidencePacket

from .decision_object import DecisionState
from .reason_codes import ReasonCode


def _score(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        return 1.0 if value else 0.0
    return 0.0


class DecisionRoute(BaseModel):
    state: DecisionState
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class DecisionRouter:
    """Tier-0 deterministic guardrails that can bypass the ensemble."""

    def route(self, packet: EvidencePacket, argument_graph: ArgumentGraph) -> DecisionRoute | None:
        threat_analysis = packet.latest_event.get("threat_analysis", {})
        threats = set(threat_analysis.get("threats_detected", []))
        illegal_score = _score(packet.signals.get("illegal_indicators"))
        if threats.intersection({"child_exploitation", "illegal_content"}) or illegal_score >= 0.8:
            return DecisionRoute(
                state=DecisionState.EJECT,
                confidence=max(0.9, illegal_score),
                reason_codes=[
                    ReasonCode.DETERMINISTIC_POLICY_VIOLATION.value,
                    ReasonCode.ILLEGAL_CONTENT.value,
                ],
                details={"threats_detected": sorted(threats)},
            )

        cross_session_risk = _score(packet.identity_refs.get("cluster_risk"))
        relay_risk = _score(packet.signals.get("relay_risk"))
        if cross_session_risk >= 0.85 and relay_risk >= 0.6:
            return DecisionRoute(
                state=DecisionState.STEP_UP_AUTH,
                confidence=max(cross_session_risk, relay_risk),
                reason_codes=[
                    ReasonCode.CROSS_SESSION_RISK.value,
                    ReasonCode.RELAY_RISK.value,
                ],
                details={"graph": argument_graph.summary()},
            )

        deterministic_violation = _score(packet.signals.get("deterministic_policy_violation"))
        if deterministic_violation >= 1.0 and threats:
            return DecisionRoute(
                state=DecisionState.RESTRICT,
                confidence=0.8,
                reason_codes=[ReasonCode.DETERMINISTIC_POLICY_VIOLATION.value],
                details={"threats_detected": sorted(threats)},
            )

        return None
