import random
import time
import uuid


def generate_bot_session(session_id: str):
    events = []
    for _ in range(30):
        events.append({
            "session_id": session_id,
            "event_type": "key_timing",
            "timestamp": time.time(),
            "payload": {"interval_ms": 120},
        })
    return events


def generate_llm_user(session_id: str):
    events = []
    for _ in range(20):
        events.append({
            "session_id": session_id,
            "event_type": "clipboard",
            "timestamp": time.time(),
            "payload": {"pasted": True},
        })
        events.append({
            "session_id": session_id,
            "event_type": "key_timing",
            "timestamp": time.time(),
            "payload": {"interval_ms": random.choice([80, 85, 90])},
        })
    return events


def generate_relay(session_id: str):
    events = []
    for _ in range(10):
        events.append({
            "session_id": session_id,
            "event_type": "challenge_response",
            "timestamp": time.time(),
            "payload": {"response_time": random.uniform(2.5, 6.0)},
        })
    return events
