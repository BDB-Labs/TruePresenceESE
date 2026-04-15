from truepresence.evidence.argument_graph import build_argument_graph
from truepresence.evidence.packet import EvidencePacket


def _packet(**overrides):
    packet = EvidencePacket(
        packet_id="packet-1",
        session_id="session-1",
        tenant_id="tenant-1",
        surface="web_guard",
        actor_id=None,
        received_at="2026-01-01T00:00:00+00:00",
        event_window_start=None,
        event_window_end=None,
    )
    for key, value in overrides.items():
        setattr(packet, key, value)
    return packet


def test_build_argument_graph_has_base_claims_and_edges() -> None:
    graph = build_argument_graph(_packet())

    assert "human_presence_supported" in graph.claims
    assert "automation_pattern_supported" in graph.claims
    assert ("challenge_success_supported", "human_presence_supported") in graph.support_edges
    assert ("challenge_failure_supported", "human_presence_supported") in graph.attack_edges


def test_challenge_status_updates_evidence_refs() -> None:
    passed_graph = build_argument_graph(_packet(challenge_data={"status": "passed"}))
    failed_graph = build_argument_graph(_packet(challenge_data={"status": "failed"}))

    assert "challenge_data" in passed_graph.claims["challenge_success_supported"].evidence_refs
    assert "challenge_data" in failed_graph.claims["challenge_failure_supported"].evidence_refs
