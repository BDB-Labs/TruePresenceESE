from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from truepresence.ensemble.orchestrator import TruePresenceEnsembleOrchestrator
from truepresence.evidence import (
    ArgumentGraph,
    ArgumentGraphBuilder,
    EvidencePacket,
    EvidencePacketBuilder,
)

from .decision_object import DecisionArtifact, DecisionObject, DecisionState
from .decision_router import DecisionRouter
from .synthesizer import DecisionSynthesizer


def _legacy_decision_for_state(state: DecisionState) -> str:
    mapping = {
        DecisionState.ALLOW: "allow",
        DecisionState.OBSERVE: "allow",
        DecisionState.CHALLENGE: "challenge",
        DecisionState.STEP_UP_AUTH: "challenge",
        DecisionState.RESTRICT: "review",
        DecisionState.BLOCK: "block",
        DecisionState.EJECT: "block",
    }
    return mapping[state]


class DecisionEngineResult(BaseModel):
    session_id: str
    surface: str
    decision_object: DecisionObject
    evidence_packet: EvidencePacket
    decision_artifact: DecisionArtifact
    argument_graph: ArgumentGraph
    ensemble_result: dict[str, Any] = Field(default_factory=dict)

    def to_response(self) -> dict[str, Any]:
        decision = self.decision_object
        evidence_summary = dict(self.decision_artifact.evidence_summary)
        final = {
            "state": decision.state.value,
            "decision": _legacy_decision_for_state(decision.state),
            "confidence": decision.confidence,
            "human_probability": decision.human_probability,
            "bot_probability": decision.bot_probability,
            "reason_codes": list(decision.reason_codes),
            "threat_categories": evidence_summary.get("threat_categories", []),
            "block_reason": evidence_summary.get("block_reason", ""),
            "risk_factors": evidence_summary.get("risk_factors", []),
        }
        return {
            "session_id": self.session_id,
            "surface": self.surface,
            "state": decision.state.value,
            "decision": final["decision"],
            "human_probability": decision.human_probability,
            "bot_probability": decision.bot_probability,
            "confidence": decision.confidence,
            "risk_factors": evidence_summary.get("risk_factors", []),
            "reason_codes": list(decision.reason_codes),
            "reasoning_trace": dict(self.decision_artifact.reasoning_trace),
            "temporal_signals": evidence_summary.get("temporal_signals", {}),
            "roles": dict(self.decision_artifact.role_outputs),
            "final": final,
            "synthesis": dict(self.ensemble_result),
            "decision_object": decision.model_dump(),
            "evidence_packet": self.evidence_packet.model_dump(),
            "decision_artifact": self.decision_artifact.model_dump(),
            "argument_graph": self.argument_graph.model_dump(),
        }


class TruePresenceDecisionEngine:
    """Product-level contract: surfaces hand events to this engine."""

    def __init__(
        self,
        *,
        orchestrator: TruePresenceEnsembleOrchestrator | None = None,
        packet_builder: EvidencePacketBuilder | None = None,
        graph_builder: ArgumentGraphBuilder | None = None,
        router: DecisionRouter | None = None,
        synthesizer: DecisionSynthesizer | None = None,
    ) -> None:
        self.orchestrator = orchestrator or TruePresenceEnsembleOrchestrator()
        self.packet_builder = packet_builder or EvidencePacketBuilder()
        self.graph_builder = graph_builder or ArgumentGraphBuilder()
        self.router = router or DecisionRouter()
        self.synthesizer = synthesizer or DecisionSynthesizer()

    def evaluate(
        self,
        *,
        session_id: str,
        surface: str,
        event: dict[str, Any],
        session: dict[str, Any] | None = None,
        challenge_results: list[dict[str, Any]] | None = None,
        tenant_id: str | None = None,
    ) -> DecisionEngineResult:
        identity_refs: dict[str, Any] = {}
        if hasattr(self.orchestrator, "identity_graph"):
            connected = self.orchestrator.identity_graph.get_connected_sessions(session_id)
            identity_refs["connected_sessions"] = len(connected)
            if connected:
                identity_refs["cluster_risk"] = self.orchestrator.identity_graph.get_session_risk(session_id)

        packet = self.packet_builder.build(
            session_id=session_id,
            surface=surface,
            event=event,
            session=session,
            challenge_results=challenge_results,
            session_history=list(self.orchestrator.memory.window(50)),
            identity_refs=identity_refs,
            tenant_id=tenant_id,
        )
        argument_graph = self.graph_builder.build(packet)
        route = self.router.route(packet, argument_graph)

        ensemble_result: dict[str, Any] = {}
        if route is None:
            ensemble_result = self.orchestrator.run(packet, argument_graph, session=session or {})
            packet = EvidencePacket(**ensemble_result.get("evidence_packet", packet.model_dump()))
            argument_graph = ArgumentGraph(**ensemble_result.get("argument_graph", argument_graph.model_dump()))

        decision_object = self.synthesizer.synthesize(
            packet=packet,
            argument_graph=argument_graph,
            ensemble_result=ensemble_result,
            route=route,
        )
        decision_artifact = self._build_artifact(
            packet=packet,
            argument_graph=argument_graph,
            decision_object=decision_object,
            route=route,
            ensemble_result=ensemble_result,
        )
        return DecisionEngineResult(
            session_id=session_id,
            surface=surface,
            decision_object=decision_object,
            evidence_packet=packet,
            decision_artifact=decision_artifact,
            argument_graph=argument_graph,
            ensemble_result=ensemble_result,
        )

    def _build_artifact(
        self,
        *,
        packet: EvidencePacket,
        argument_graph: ArgumentGraph,
        decision_object: DecisionObject,
        route: Any,
        ensemble_result: dict[str, Any],
    ) -> DecisionArtifact:
        roles = dict(ensemble_result.get("roles", {}))
        threat_categories = roles.get("adversarial", {}).get("threat_categories", [])
        block_reason = roles.get("adversarial", {}).get("block_reason", "")
        if route is not None and route.details.get("threats_detected"):
            threat_categories = route.details["threats_detected"]
            block_reason = block_reason or "Deterministic policy violation"
        elif decision_object.state not in {DecisionState.RESTRICT, DecisionState.BLOCK, DecisionState.EJECT}:
            block_reason = ""

        risk_factors = list(ensemble_result.get("risk_factors", []))
        risk_factors.extend(decision_object.reason_codes)
        risk_factors = list(dict.fromkeys(risk_factors))

        temporal_signals = {
            "drift": float(packet.metadata.get("temporal_drift", 0.0)),
            "cross_session_risk": float(packet.identity_refs.get("cluster_risk", 0.0)),
        }

        return DecisionArtifact(
            evidence_summary={
                "session_id": packet.session_id,
                "surface": packet.surface,
                "event_count": len(packet.events),
                "risk_factors": risk_factors,
                "temporal_signals": temporal_signals,
                "threat_categories": threat_categories,
                "block_reason": block_reason,
            },
            argument_graph=argument_graph.summary(),
            router=route.model_dump() if route is not None else {},
            role_outputs=roles,
            reasoning_trace=dict(ensemble_result.get("reasoning_trace", {})),
            synthesis={
                **ensemble_result,
                "decision_state": decision_object.state.value,
                "legacy_decision": _legacy_decision_for_state(decision_object.state),
            },
        )
