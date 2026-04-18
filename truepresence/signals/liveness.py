import statistics
from typing import List

from truepresence.core.events import Event


def compute_liveness(events: List[Event]) -> float:
    key_events = [e for e in events if e.event_type == "key_timing"]
    if len(key_events) < 5:
        return 0.2
    intervals = [
        key_events[i + 1].timestamp.timestamp() - key_events[i].timestamp.timestamp()
        for i in range(len(key_events) - 1)
    ]
    jitter = statistics.pstdev(intervals) if len(intervals) > 1 else 0.0
    score = min(1.0, max(0.0, jitter * 10.0))
    return score
