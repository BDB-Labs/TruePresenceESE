from truepresence.api.server import reset_session, shared_orchestrator


def test_session_reset_isolated() -> None:
    shared_orchestrator.memory.clear_all()
    shared_orchestrator.memory.add_event("session-a", {"session_id": "session-a", "event_type": "a"})
    shared_orchestrator.memory.add_event("session-b", {"session_id": "session-b", "event_type": "b"})

    reset_session("session-a")

    assert shared_orchestrator.memory.window("session-a", 10) == []
    assert [event["event_type"] for event in shared_orchestrator.memory.window("session-b", 10)] == ["b"]
