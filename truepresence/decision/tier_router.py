from __future__ import annotations

from truepresence.evidence.argument_graph import ArgumentGraph
from truepresence.evidence.packet import EvidencePacket


def choose_tier(packet: EvidencePacket, graph: ArgumentGraph, context: dict) -> str:
    threats_detected = set(packet.risk_context.get("threats_detected", []))

    # Tier 0 = deterministic or policy-hardcoded blatant cases
    if packet.provenance.get("invalid_attestation"):
        return "tier0"
    if packet.behavioral_features.get("known_automation_fingerprint"):
        return "tier0"
    if packet.risk_context.get("impossible_event_sequence"):
        return "tier0"
    if packet.challenge_data.get("status") == "deterministic_failure":
        return "tier0"
    if threats_detected.intersection({"illegal_content", "child_exploitation"}):
        return "tier0"

    # Tier 2 = ambiguous/high-risk/high-value
    if packet.policy_context.get("high_value_flow"):
        return "tier2"
    if packet.identity_refs.get("cluster_risk") == "high":
        return "tier2"
    if context.get("force_tier2"):
        return "tier2"

    return "tier1"
