from truepresence.memory.session_timeline import SessionTimeline


def test_session_memory_isolation() -> None:
    timeline = SessionTimeline()
    timeline.add_event("session-a", {"session_id": "session-a", "event_type": "a"})
    timeline.add_event("session-b", {"session_id": "session-b", "event_type": "b"})

    assert [event["event_type"] for event in timeline.window("session-a", 10)] == ["a"]
    assert [event["event_type"] for event in timeline.window("session-b", 10)] == ["b"]
