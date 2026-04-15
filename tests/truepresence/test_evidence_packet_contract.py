from truepresence.evidence.packet import EvidencePacket


def test_evidence_packet_can_be_constructed() -> None:
    packet = EvidencePacket(
        packet_id="packet-1",
        session_id="session-1",
        tenant_id="tenant-1",
        surface="telegram",
        actor_id="actor-1",
        received_at="2026-01-01T00:00:00+00:00",
        event_window_start=None,
        event_window_end=None,
    )

    assert packet.packet_id == "packet-1"
    assert packet.session_id == "session-1"
    assert packet.tenant_id == "tenant-1"
    assert packet.surface == "telegram"
    assert packet.schema_version == "1.0"
    assert packet.raw_events == []
    assert packet.challenge_data == {}
