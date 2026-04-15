from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvidencePacket:
    packet_id: str
    session_id: str
    tenant_id: str
    surface: str
    actor_id: Optional[str]
    received_at: str
    event_window_start: Optional[str]
    event_window_end: Optional[str]
    raw_events: List[Dict[str, Any]] = field(default_factory=list)
    challenge_data: Dict[str, Any] = field(default_factory=dict)
    timing_features: Dict[str, Any] = field(default_factory=dict)
    behavioral_features: Dict[str, Any] = field(default_factory=dict)
    identity_refs: Dict[str, Any] = field(default_factory=dict)
    session_history: List[Dict[str, Any]] = field(default_factory=list)
    policy_context: Dict[str, Any] = field(default_factory=dict)
    risk_context: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    session_context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"

    @property
    def latest_event(self) -> Dict[str, Any]:
        if not self.raw_events:
            return {}
        return self.raw_events[-1]

    @property
    def events(self) -> List[Dict[str, Any]]:
        return self.raw_events

    @property
    def challenge_results(self) -> List[Dict[str, Any]]:
        return [dict(self.challenge_data)] if self.challenge_data else []

    def as_role_evidence(self, argument_graph: Any | None = None) -> Dict[str, Any]:
        signals = {}
        signals.update(self.timing_features)
        signals.update(self.behavioral_features)
        if self.challenge_data.get("status") == "passed":
            signals.setdefault("challenge_verified", 1.0)
        if self.identity_refs.get("cluster_risk") is not None:
            signals.setdefault("cluster_risk", self.identity_refs.get("cluster_risk"))

        return {
            "signals": signals,
            "features": dict(self.behavioral_features),
            "session": {
                **dict(self.session_context),
                "session_id": self.session_id,
                "tenant_id": self.tenant_id,
                "surface": self.surface,
                "actor_id": self.actor_id,
            },
            "event": dict(self.latest_event),
            "historical": list(self.session_history),
            "challenge_results": list(self.challenge_results),
            "identity_refs": dict(self.identity_refs),
            "policy_context": dict(self.policy_context),
            "risk_context": dict(self.risk_context),
            "surface": self.surface,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
            "role_input": {
                "evidence_packet": self.model_dump(),
                "argument_graph": argument_graph.model_dump() if hasattr(argument_graph, "model_dump") else argument_graph,
                "session_history": list(self.session_history),
            },
        }

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)
