from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple

from .claims import Claim, ClaimType
from .packet import EvidencePacket


@dataclass
class ArgumentGraph:
    claims: Dict[str, Claim] = field(default_factory=dict)
    support_edges: List[Tuple[str, str]] = field(default_factory=list)
    attack_edges: List[Tuple[str, str]] = field(default_factory=list)

    def add_claim(self, claim: Claim) -> None:
        self.claims[claim.claim_id] = claim

    def supports(self, source_claim_id: str, target_claim_id: str) -> None:
        self.support_edges.append((source_claim_id, target_claim_id))

    def attacks(self, source_claim_id: str, target_claim_id: str) -> None:
        self.attack_edges.append((source_claim_id, target_claim_id))

    def summary(self) -> Dict[str, Any]:
        return {
            "claim_count": len(self.claims),
            "support_edges": list(self.support_edges),
            "attack_edges": list(self.attack_edges),
            "claims": {
                claim_id: {
                    "claim_type": claim.claim_type,
                    "label": claim.label,
                    "evidence_refs": list(claim.evidence_refs),
                    "confidence_hint": claim.confidence_hint,
                }
                for claim_id, claim in self.claims.items()
            },
        }

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)


def build_argument_graph(packet: EvidencePacket) -> ArgumentGraph:
    """
    Build an initial temporal argument graph from an EvidencePacket.

    V1 goals:
    - minimal but canonical
    - deterministic
    - extensible
    """
    graph = ArgumentGraph()

    graph.add_claim(
        Claim(
            claim_id="human_presence_supported",
            claim_type=ClaimType.PRESENCE.value,
            label="Actor appears to be a legitimate human participant",
            evidence_refs=[],
        )
    )
    graph.add_claim(
        Claim(
            claim_id="automation_pattern_supported",
            claim_type=ClaimType.RISK.value,
            label="Observed patterns support automation or non-human behavior",
            evidence_refs=[],
        )
    )
    graph.add_claim(
        Claim(
            claim_id="challenge_success_supported",
            claim_type=ClaimType.CHALLENGE.value,
            label="Challenge result supports human continuity",
            evidence_refs=[],
        )
    )
    graph.add_claim(
        Claim(
            claim_id="challenge_failure_supported",
            claim_type=ClaimType.CHALLENGE.value,
            label="Challenge result undermines human continuity",
            evidence_refs=[],
        )
    )
    graph.add_claim(
        Claim(
            claim_id="identity_cluster_risk_supported",
            claim_type=ClaimType.IDENTITY.value,
            label="Cross-session identity graph indicates elevated cluster risk",
            evidence_refs=[],
        )
    )
    graph.add_claim(
        Claim(
            claim_id="policy_step_up_required",
            claim_type=ClaimType.POLICY.value,
            label="Tenant or flow policy requires step-up verification",
            evidence_refs=[],
        )
    )

    graph.supports("challenge_success_supported", "human_presence_supported")
    graph.attacks("challenge_failure_supported", "human_presence_supported")
    graph.attacks("automation_pattern_supported", "human_presence_supported")
    graph.supports("identity_cluster_risk_supported", "automation_pattern_supported")
    graph.attacks("policy_step_up_required", "human_presence_supported")

    status = packet.challenge_data.get("status")
    if status == "passed":
        graph.claims["challenge_success_supported"].evidence_refs.append("challenge_data")
    elif status in {"failed", "deterministic_failure"}:
        graph.claims["challenge_failure_supported"].evidence_refs.append("challenge_data")

    if packet.identity_refs.get("cluster_risk"):
        graph.claims["identity_cluster_risk_supported"].evidence_refs.append("identity_refs")

    if packet.policy_context.get("require_step_up"):
        graph.claims["policy_step_up_required"].evidence_refs.append("policy_context")

    evidence_refs = []
    if packet.timing_features.get("constant_latency_pattern"):
        evidence_refs.append("timing_features")
    if packet.behavioral_features.get("automation_pattern"):
        evidence_refs.append("behavioral_features")
    if evidence_refs:
        graph.claims["automation_pattern_supported"].evidence_refs.extend(evidence_refs)

    return graph


class ArgumentGraphBuilder:
    def build(self, packet: EvidencePacket) -> ArgumentGraph:
        return build_argument_graph(packet)
