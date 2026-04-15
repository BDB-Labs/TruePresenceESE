from typing import List
from truepresence.core.events import Event


def compute_relay_risk(events: List[Event]) -> float:
    responses = [e for e in events if e.event_type == "challenge_response"]
    if not responses:
        return 0.1
    latencies = [
        e.payload.get("response_time", 0.0)
        for e in responses
    ]
    if not latencies:
        return 0.5
    avg = sum(latencies) / len(latencies)
    if avg < 0.3:
        return 0.9
    if avg > 8.0:
        return 0.7
    return 0.3
