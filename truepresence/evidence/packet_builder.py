from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return dict(value)
    return {"value": value}


def _score(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        return 1.0 if value else 0.0
    return default


class EvidencePacket(BaseModel):
    session_id: str
    tenant_id: str | None = None
    surface: str
    events: list[dict[str, Any]] = Field(default_factory=list)
    signals: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, Any] = Field(default_factory=dict)
    challenge_results: list[dict[str, Any]] = Field(default_factory=list)
    session_history: list[dict[str, Any]] = Field(default_factory=list)
    identity_refs: dict[str, Any] = Field(default_factory=dict)
    session_context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def latest_event(self) -> dict[str, Any]:
        if not self.events:
            return {}
        return self.events[-1]

    def as_role_evidence(self, argument_graph: Any | None = None) -> dict[str, Any]:
        evidence = {
            "signals": dict(self.signals),
            "features": dict(self.features),
            "session": dict(self.session_context),
            "event": dict(self.latest_event),
            "historical": list(self.session_history),
            "challenge_results": list(self.challenge_results),
            "identity_refs": dict(self.identity_refs),
            "surface": self.surface,
            "tenant_id": self.tenant_id,
            "role_input": {
                "evidence_packet": self.model_dump(),
                "argument_graph": argument_graph.model_dump() if hasattr(argument_graph, "model_dump") else argument_graph,
                "session_history": list(self.session_history),
            },
        }
        evidence.update(self.metadata)
        return evidence


class EvidencePacketBuilder:
    """Normalizes surface events into a product-level evidence packet."""

    def build(
        self,
        *,
        session_id: str,
        surface: str,
        event: dict[str, Any] | Any,
        session: dict[str, Any] | Any | None = None,
        challenge_results: list[dict[str, Any]] | None = None,
        session_history: list[dict[str, Any]] | None = None,
        identity_refs: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> EvidencePacket:
        event_dict = _to_dict(event)
        session_dict = _to_dict(session)
        features = dict(event_dict.get("features", {}))
        signals = dict(features)
        signals.update(event_dict.get("signals", {}))

        derived = self._derive_signals(event_dict, challenge_results or [])
        for key, value in derived.items():
            signals.setdefault(key, value)

        tenant_id = tenant_id or session_dict.get("tenant_id")
        packet = EvidencePacket(
            session_id=session_id,
            tenant_id=tenant_id,
            surface=surface,
            events=[event_dict],
            signals=signals,
            features=features,
            challenge_results=list(challenge_results or self._extract_challenge_results(event_dict)),
            session_history=list(session_history or []),
            identity_refs=dict(identity_refs or {}),
            session_context=session_dict,
            metadata={
                "mode": session_dict.get("mode"),
                "event_type": event_dict.get("event_type"),
                "context": dict(event_dict.get("context", {})),
            },
        )
        return packet

    def _derive_signals(
        self,
        event: dict[str, Any],
        challenge_results: list[dict[str, Any]],
    ) -> dict[str, float]:
        context = event.get("context", {})
        payload = event.get("payload", {})
        threat_analysis = event.get("threat_analysis", {})

        verified_challenges = sum(1 for result in challenge_results if result.get("verified"))
        direct_interaction = 0.2
        if event.get("event_type") in {"cursor_move", "key_timing", "click"}:
            direct_interaction = 0.8
        elif event.get("event_type") in {"message", "member_join", "member_update"}:
            direct_interaction = 0.45

        if context.get("is_bot"):
            direct_interaction = 0.05

        liveness = min(1.0, direct_interaction + (0.2 * verified_challenges))

        pasted = payload.get("pasted") or payload.get("paste") or payload.get("is_paste")
        ai_mediation = 0.75 if pasted else 0.1
        if event.get("event_type") == "clipboard":
            ai_mediation = max(ai_mediation, 0.6)

        relay_risk = 0.1
        response_time_ms = payload.get("response_time_ms") or payload.get("response_time")
        if response_time_ms is not None:
            response_seconds = float(response_time_ms) / 1000 if response_time_ms > 10 else float(response_time_ms)
            if response_seconds < 0.3:
                relay_risk = 0.9
            elif response_seconds > 8.0:
                relay_risk = 0.7
            else:
                relay_risk = 0.3

        relay_risk = max(
            relay_risk,
            min(1.0, _score(event.get("signals", {}).get("content_similarity"))),
        )

        deterministic_policy_violation = 1.0 if threat_analysis.get("threats_detected") else 0.0

        return {
            "liveness": liveness,
            "ai_mediation": ai_mediation,
            "relay_risk": relay_risk,
            "deterministic_policy_violation": deterministic_policy_violation,
        }

    def _extract_challenge_results(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        challenge_result = event.get("challenge_result")
        if challenge_result:
            return [dict(challenge_result)]
        challenge_response = event.get("challenge_response")
        if challenge_response:
            return [dict(challenge_response)]
        return []
