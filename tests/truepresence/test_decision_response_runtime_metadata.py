from truepresence.decision.engine import TruePresenceDecisionEngine


class DummyEnsembleRuntime:
    mode = "fallback"
    degraded_reason = "ImportError"

    class _Memory:
        def window(self, session_id: str, count: int):
            return []

    class _Identity:
        def get_connected_sessions(self, session_id: str):
            return set()

        def get_session_risk(self, session_id: str) -> float:
            return 0.0

    memory = _Memory()
    identity_graph = _Identity()

    def run(self, **kwargs):
        return []


def test_decision_response_exposes_runtime_metadata() -> None:
    engine = TruePresenceDecisionEngine(ensemble_runtime=DummyEnsembleRuntime())

    result = engine.evaluate(
        surface="web_guard",
        session_id="session-runtime",
        tenant_id="tenant-1",
        event={"event_type": "click", "payload": {}},
    ).to_response()

    assert result["runtime"]["mode"] == "fallback"
    assert result["runtime"]["degraded_reason"] == "ImportError"
