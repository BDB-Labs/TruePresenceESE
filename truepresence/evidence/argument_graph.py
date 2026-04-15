from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .claims import Claim, ClaimType
from .packet_builder import EvidencePacket


def _score(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        return 1.0 if value else 0.0
    return 0.0


class ArgumentGraph(BaseModel):
    claims: dict[str, Claim] = Field(default_factory=dict)
    support_edges: list[tuple[str, str]] = Field(default_factory=list)
    attack_edges: list[tuple[str, str]] = Field(default_factory=list)

    def add_claim(self, claim: Claim) -> None:
        self.claims[claim.claim_id] = claim

    def supports(self, source: str, target: str) -> None:
        self.support_edges.append((source, target))

    def attacks(self, source: str, target: str) -> None:
        self.attack_edges.append((source, target))

    def summary(self) -> dict[str, Any]:
        return {
            "claim_count": len(self.claims),
            "support_edges": list(self.support_edges),
            "attack_edges": list(self.attack_edges),
            "claims": {
                claim_id: {
                    "type": claim.type.value,
                    "confidence": claim.confidence,
                    "detail": claim.detail,
                }
                for claim_id, claim in self.claims.items()
            },
        }


class ArgumentGraphBuilder:
    """Builds a lightweight argument graph from the evidence packet."""

    def build(self, packet: EvidencePacket) -> ArgumentGraph:
        graph = ArgumentGraph()
        human_claim = Claim(
            claim_id="human_present",
            type=ClaimType.HUMAN_PRESENT,
            evidence_refs=["signals:liveness"],
            confidence=_score(packet.signals.get("liveness", 0.5)),
            detail="Direct interaction signals support a human-present hypothesis.",
        )
        graph.add_claim(human_claim)

        if _score(packet.signals.get("liveness")) >= 0.55:
            claim = Claim(
                claim_id="liveness_signal",
                type=ClaimType.HUMAN_PRESENT,
                evidence_refs=["signals:liveness"],
                confidence=_score(packet.signals.get("liveness")),
                detail="Input timing or interaction cadence looks human.",
            )
            graph.add_claim(claim)
            graph.supports(claim.claim_id, human_claim.claim_id)

        if _score(packet.signals.get("ai_mediation")) >= 0.4:
            claim = Claim(
                claim_id="ai_mediation_risk",
                type=ClaimType.AI_MEDIATED,
                evidence_refs=["signals:ai_mediation"],
                confidence=_score(packet.signals.get("ai_mediation")),
                detail="Signals suggest AI-mediated content generation.",
            )
            graph.add_claim(claim)
            graph.attacks(claim.claim_id, human_claim.claim_id)

        if _score(packet.signals.get("relay_risk")) >= 0.4:
            claim = Claim(
                claim_id="relay_risk",
                type=ClaimType.RELAY_RISK,
                evidence_refs=["signals:relay_risk"],
                confidence=_score(packet.signals.get("relay_risk")),
                detail="Response timing suggests an automated relay or operator.",
            )
            graph.add_claim(claim)
            graph.attacks(claim.claim_id, human_claim.claim_id)

        temporal_drift = _score(packet.metadata.get("temporal_drift"))
        if temporal_drift >= 0.2:
            claim = Claim(
                claim_id="temporal_drift",
                type=ClaimType.TEMPORAL_DRIFT,
                evidence_refs=["metadata:temporal_drift"],
                confidence=temporal_drift,
                detail="Recent events show unstable behavior over time.",
            )
            graph.add_claim(claim)
            graph.attacks(claim.claim_id, human_claim.claim_id)

        cross_session_risk = _score(packet.identity_refs.get("cluster_risk"))
        if cross_session_risk >= 0.4:
            claim = Claim(
                claim_id="cross_session_risk",
                type=ClaimType.CROSS_SESSION_RISK,
                evidence_refs=["identity_refs:cluster_risk"],
                confidence=cross_session_risk,
                detail="Identity graph indicates related high-risk sessions.",
            )
            graph.add_claim(claim)
            graph.attacks(claim.claim_id, human_claim.claim_id)

        if any(result.get("verified") for result in packet.challenge_results):
            claim = Claim(
                claim_id="verified_challenge",
                type=ClaimType.VERIFIED_CHALLENGE,
                evidence_refs=["challenge_results"],
                confidence=0.85,
                detail="User passed an active challenge.",
            )
            graph.add_claim(claim)
            graph.supports(claim.claim_id, human_claim.claim_id)

        if packet.signals.get("deterministic_policy_violation"):
            claim = Claim(
                claim_id="policy_violation",
                type=ClaimType.POLICY_VIOLATION,
                evidence_refs=["signals:deterministic_policy_violation"],
                confidence=1.0,
                detail="Surface policy found a deterministic violation.",
            )
            graph.add_claim(claim)
            graph.attacks(claim.claim_id, human_claim.claim_id)

        return graph
