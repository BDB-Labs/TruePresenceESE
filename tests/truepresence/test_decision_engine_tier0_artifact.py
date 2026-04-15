from truepresence.decision.decision_object import DecisionState
from truepresence.decision.engine import TruePresenceDecisionEngine


class DummyEnsembleRuntime:
    def run(self, **kwargs):  # pragma: no cover - tier0 should not call this
        raise AssertionError("tier0 must not call the ensemble runtime")


def test_tier0_deterministic_violation_still_emits_artifacts() -> None:
    engine = TruePresenceDecisionEngine(ensemble_runtime=DummyEnsembleRuntime())

    result = engine.evaluate(
        surface="web_guard",
        session_id="session-tier0",
        tenant_id="tenant-1",
        event={"event_type": "login", "payload": {}},
        context={"invalid_attestation": True},
    )

    assert result.decision.state == DecisionState.EJECT.value
    assert result.evidence_packet.packet_id
    assert result.argument_graph.claims
    assert result.decision_artifact["decision_id"] == result.decision.decision_id
    assert result.decision_artifact["evidence_packet_id"] == result.evidence_packet.packet_id
