from __future__ import annotations

import time
from collections import deque
from typing import Any


class SessionTimeline:
    """Temporal memory with rolling windows and drift calculation."""

    def __init__(self, maxlen: int = 1000):
        self.events = deque(maxlen=maxlen)

    def add_event(self, event: dict[str, Any]) -> None:
        event_copy = dict(event)
        event_copy.setdefault("ts", time.time())
        self.events.append(event_copy)

    def add(self, event: dict[str, Any]) -> None:
        self.add_event(event)

    def window(self, count: int = 50) -> list[dict[str, Any]]:
        return list(self.events)[-count:]

    def drift(self) -> float:
        if len(self.events) < 2:
            return 0.0

        intervals = []
        events = list(self.events)
        for index in range(1, len(events)):
            intervals.append(events[index]["ts"] - events[index - 1]["ts"])

        if len(intervals) < 2:
            return 0.0

        mean_interval = sum(intervals) / len(intervals)
        variance = sum((interval - mean_interval) ** 2 for interval in intervals) / len(intervals)
        return float(variance)

    def clear(self) -> None:
        self.events.clear()

    def __len__(self) -> int:
        return len(self.events)
