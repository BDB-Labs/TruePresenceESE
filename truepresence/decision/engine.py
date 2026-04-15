from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from truepresence.artifacts.artifact_store import ArtifactStore
from truepresence.decision.decision_object import DecisionObject, DecisionState
from truepresence.decision.synthesizer import synthesize_decision
from truepresence.decision.tier_router import choose_tier
from truepresence.evidence.argument_graph import ArgumentGraph, build_argument_graph
from truepresence.evidence.packet import EvidencePacket
from truepresence.evidence.packet_builder import build_evidence_packet
from truepresence.memory.session_timeline import SessionTimeline


def _legacy_decision_for_state(state: str) -> str:
    mapping = {
        DecisionState.ALLOW.value: "allow",
        DecisionState.OBSERVE.value: "allow",
        DecisionState.ELEVATED_OBSERVE.value: "review",
        DecisionState.CHALLENGE.value: "challenge",
        DecisionState.STEP_UP_AUTH.value: "challenge",
        DecisionState.RESTRICT.value: "review",
        DecisionState.BLOCK.value: "block",
        DecisionState.EJECT.value: "block",
    }
    return mapping.get(state, "review")


@dataclass
class DecisionResult:
    decision: DecisionObject
    evidence_packet: EvidencePacket
    argument_graph: ArgumentGraph
    decision_artifact: Dict[str, Any]

    @property
    def decision_object(self) -> DecisionObject:
        return self.decision

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

    def to_response(self) -> Dict[str, Any]:
        decision = self.decision
        final = {
            "state": decision.state,
            "decision": _legacy_decision_for_state(decision.state),
            "confidence": decision.confidence,
            "human_probability": decision.human_probability,
            "bot_probability": decision.bot_probability,
            "reason_codes": list(decision.reason_codes),
            "risk_factors": list(decision.reason_codes),
            "threat_categories": self.decision_artifact.get("threat_categories", []),
            "block_reason": self.decision_artifact.get("block_reason", ""),
        }
        return {
            "session_id": decision.session_id,
            "surface": decision.surface,
            "state": decision.state,
            "decision": final["decision"],
            "human_probability": decision.human_probability,
            "bot_probability": decision.bot_probability,
            "confidence": decision.confidence,
            "risk_factors": list(decision.reason_codes),
            "reason_codes": list(decision.reason_codes),
            "reasoning_trace": dict(self.decision_artifact.get("reasoning_trace", {})),
            "temporal_signals": {
                "drift": self.evidence_packet.timing_features.get("temporal_drift", 0.0),
                "cross_session_risk": self.evidence_packet.identity_refs.get("cluster_risk", 0.0),
            },
            "roles": {
                report["role"]: {
                    "summary": report.get("summary"),
                    "confidence": report.get("confidence"),
                    "findings": report.get("findings", []),
                    "metadata": report.get("metadata", {}),
                }
                for report in self.decision_artifact.get("role_reports", [])
            },
            "final": final,
            "decision_object": decision.model_dump(),
            "evidence_packet": self.evidence_packet.model_dump(),
            "decision_artifact": dict(self.decision_artifact),
            "argument_graph": self.argument_graph.model_dump(),
        }


class _NoOpIdentityGraph:
    def get_connected_sessions(self, session_id: str):
        return set()

    def get_session_risk(self, session_id: str) -> float:
        return 0.0

    def get_session_cluster(self, session_id: str):
        return set()


class _NoOpEnsembleRuntime:
    def __init__(self) -> None:
        self.memory = SessionTimeline()
        self.identity_graph = _NoOpIdentityGraph()

    def run(self, **kwargs):
        return []

    def get_session_cluster(self, session_id: str):
        return set()


class TruePresenceDecisionEngine:
    def __init__(self, ensemble_runtime=None, artifact_store: Optional[ArtifactStore] = None):
        if ensemble_runtime is None:
            try:
                from truepresence.ensemble.orchestrator import TruePresenceEnsembleRuntime
            except Exception:
                ensemble_runtime = _NoOpEnsembleRuntime()
            else:
                try:
                    ensemble_runtime = TruePresenceEnsembleRuntime()
                except Exception:
                    ensemble_runtime = _NoOpEnsembleRuntime()
        self.ensemble_runtime = ensemble_runtime
        self.artifact_store = artifact_store or ArtifactStore()

    def evaluate(
        self,
        surface: str,
        session_id: str,
        tenant_id: str | None = None,
        event: Dict[str, Any] | None = None,
        context: Optional[Dict[str, Any]] = None,
        *,
        session: Optional[Dict[str, Any]] = None,
        challenge_results: Optional[list[Dict[str, Any]]] = None,
    ) -> DecisionResult:
        if event is None:
            raise ValueError("event is required")

        ctx = dict(context or {})
        session_dict = dict(session or {})
        if session_dict:
            ctx.setdefault("session", session_dict)
            ctx.setdefault("actor_id", session_dict.get("actor_id") or session_dict.get("user_id"))

        resolved_tenant_id = tenant_id or session_dict.get("tenant_id") or ctx.get("tenant_id") or "default"

        if challenge_results and "challenge_data" not in ctx:
            latest = dict(challenge_results[-1])
            if latest.get("verified") is True:
                latest.setdefault("status", "passed")
            elif latest.get("verified") is False:
                latest.setdefault("status", "failed")
            ctx["challenge_data"] = latest

        if "session_history" not in ctx and hasattr(self.ensemble_runtime, "memory"):
            ctx["session_history"] = self.ensemble_runtime.memory.window(session_id, 50)

        if "identity_refs" not in ctx and getattr(self.ensemble_runtime, "identity_graph", None) is not None:
            connected = self.ensemble_runtime.identity_graph.get_connected_sessions(session_id)
            identity_refs = {
                "connected_sessions": len(connected),
            }
            if connected:
                cluster_risk = self.ensemble_runtime.identity_graph.get_session_risk(session_id)
                identity_refs["cluster_risk"] = "high" if cluster_risk >= 0.75 else cluster_risk
            ctx["identity_refs"] = identity_refs

        packet = build_evidence_packet(
            surface=surface,
            session_id=session_id,
            tenant_id=resolved_tenant_id,
            event=dict(event),
            context=ctx,
        )
        graph = build_argument_graph(packet)
        tier = choose_tier(packet, graph, ctx)

        role_reports = []
        if tier != "tier0":
            role_reports = self.ensemble_runtime.run(
                evidence_packet=packet,
                argument_graph=graph,
                context=ctx,
                tier=tier,
            )

        decision = synthesize_decision(
            packet=packet,
            graph=graph,
            role_reports=role_reports,
            tier=tier,
            context=ctx,
        )

        artifact = {
            "decision_id": decision.decision_id,
            "session_id": decision.session_id,
            "tenant_id": decision.tenant_id,
            "surface": decision.surface,
            "tier_path": decision.tier_path,
            "reason_codes": decision.reason_codes,
            "state": decision.state,
            "recommended_enforcement": decision.recommended_enforcement,
            "confidence": decision.confidence,
            "risk_level": decision.risk_level,
            "evidence_packet_id": packet.packet_id,
            "argument_graph_id": decision.argument_graph_id,
            "role_report_ids": decision.role_report_ids,
            "role_reports": role_reports,
            "reasoning_trace": {
                "tier": tier,
                "state": decision.state,
                "reason_codes": list(decision.reason_codes),
            },
            "threat_categories": packet.risk_context.get("threats_detected", []),
            "block_reason": "Deterministic policy violation" if tier == "tier0" else "",
            "metadata": decision.metadata,
        }

        self.artifact_store.store_evidence_packet(packet)
        self.artifact_store.store_argument_graph(graph)
        self.artifact_store.store_role_reports(role_reports)
        self.artifact_store.store_decision_artifact(artifact)

        return DecisionResult(
            decision=decision,
            evidence_packet=packet,
            argument_graph=graph,
            decision_artifact=artifact,
        )
