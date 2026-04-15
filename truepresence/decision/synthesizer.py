from __future__ import annotations

from typing import Any

from truepresence.evidence.argument_graph import ArgumentGraph
from truepresence.evidence.packet_builder import EvidencePacket

from .decision_object import DecisionObject, DecisionState
from .decision_router import DecisionRoute
from .reason_codes import ReasonCode


def _score(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        return 1.0 if value else 0.0
    return 0.0


class DecisionSynthesizer:
    """Translate evidence, debate, and router output into a product decision."""

    def synthesize(
        self,
        *,
        packet: EvidencePacket,
        argument_graph: ArgumentGraph,
        ensemble_result: dict[str, Any] | None,
        route: DecisionRoute | None = None,
    ) -> DecisionObject:
        reason_codes = self._reason_codes(packet, argument_graph, ensemble_result, route)

        if route is not None:
            human_probability = 0.05 if route.state in {DecisionState.BLOCK, DecisionState.EJECT} else 0.3
            return DecisionObject(
                state=route.state,
                confidence=route.confidence,
                reason_codes=reason_codes,
                human_probability=human_probability,
                bot_probability=1.0 - human_probability,
                explanation=self._explanation_for_state(route.state),
                metadata={"router": route.model_dump()},
            )

        synthesis = ensemble_result or {}
        state = self._map_state(synthesis, packet)
        confidence = float(synthesis.get("confidence", 0.5))
        human_probability = float(synthesis.get("human_probability", synthesis.get("combined_score", 0.5)))
        bot_probability = float(synthesis.get("bot_probability", 1.0 - human_probability))

        return DecisionObject(
            state=state,
            confidence=confidence,
            reason_codes=reason_codes,
            human_probability=human_probability,
            bot_probability=bot_probability,
            explanation=self._explanation_for_state(state),
            metadata={
                "ensemble_decision": synthesis.get("decision"),
                "combined_score": synthesis.get("combined_score"),
            },
        )

    def _map_state(self, synthesis: dict[str, Any], packet: EvidencePacket) -> DecisionState:
        decision = synthesis.get("decision", "review")
        confidence = float(synthesis.get("confidence", 0.5))
        threat_categories = synthesis.get("threat_categories", [])

        if threat_categories and confidence >= 0.6:
            return DecisionState.RESTRICT

        if decision == "allow":
            if confidence < 0.55:
                return DecisionState.OBSERVE
            return DecisionState.ALLOW
        if decision == "challenge":
            return DecisionState.CHALLENGE
        if decision == "block":
            return DecisionState.BLOCK

        cross_session_risk = _score(packet.identity_refs.get("cluster_risk"))
        if cross_session_risk >= 0.7:
            return DecisionState.STEP_UP_AUTH
        return DecisionState.OBSERVE

    def _reason_codes(
        self,
        packet: EvidencePacket,
        argument_graph: ArgumentGraph,
        ensemble_result: dict[str, Any] | None,
        route: DecisionRoute | None,
    ) -> list[str]:
        codes: list[str] = []
        if packet.surface == "telegram":
            codes.append(ReasonCode.SURFACE_TELEGRAM.value)
        elif packet.surface == "web_guard":
            codes.append(ReasonCode.SURFACE_WEB_GUARD.value)

        if any(claim.type.value == "human_present" for claim in argument_graph.claims.values()):
            if _score(packet.signals.get("liveness")) >= 0.55:
                codes.append(ReasonCode.LIVENESS_CONFIRMED.value)
        if any(result.get("verified") for result in packet.challenge_results):
            codes.append(ReasonCode.VERIFIED_CHALLENGE.value)
        if _score(packet.signals.get("ai_mediation")) >= 0.4:
            codes.append(ReasonCode.AI_MEDIATION_RISK.value)
        if _score(packet.signals.get("relay_risk")) >= 0.4:
            codes.append(ReasonCode.RELAY_RISK.value)
        if _score(packet.metadata.get("temporal_drift")) >= 0.2:
            codes.append(ReasonCode.TEMPORAL_DRIFT.value)
        if _score(packet.identity_refs.get("cluster_risk")) >= 0.4:
            codes.append(ReasonCode.CROSS_SESSION_RISK.value)
        if route is not None:
            codes.extend(code for code in route.reason_codes if code not in codes)
        if ensemble_result:
            disagreement = float(ensemble_result.get("disagreement", 0.0))
            if disagreement >= 0.3:
                codes.append(ReasonCode.REVIEW_DISAGREEMENT.value)
            if float(ensemble_result.get("confidence", 0.5)) < 0.55:
                codes.append(ReasonCode.LOW_CONFIDENCE.value)

        return list(dict.fromkeys(codes))

    def _explanation_for_state(self, state: DecisionState) -> str:
        explanations = {
            DecisionState.ALLOW: "Signals are coherent enough to allow the session.",
            DecisionState.OBSERVE: "Signals are mixed; allow the session but keep it under observation.",
            DecisionState.CHALLENGE: "The session should complete an active challenge before proceeding.",
            DecisionState.STEP_UP_AUTH: "The session should be stepped up for stronger verification.",
            DecisionState.RESTRICT: "Limit high-risk actions while the session is evaluated further.",
            DecisionState.BLOCK: "The session should be blocked based on ensemble risk.",
            DecisionState.EJECT: "Deterministic policy violations require immediate removal.",
        }
        return explanations[state]
