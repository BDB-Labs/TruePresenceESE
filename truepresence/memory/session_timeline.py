from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any


class SessionTimeline:
    """Temporal memory keyed by session_id with rolling windows and drift calculation."""

    def __init__(self, maxlen: int = 1000):
        self.maxlen = maxlen
        self._events: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=maxlen))

    def _resolve_session_and_event(
        self,
        session_or_event: str | dict[str, Any],
        event: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        if event is None and isinstance(session_or_event, dict):
            event_dict = dict(session_or_event)
            session_id = str(event_dict.get("session_id") or "default")
            return session_id, event_dict
        if event is None:
            raise ValueError("event is required when session_id is provided explicitly")
        return str(session_or_event), dict(event)

    def add_event(self, session_or_event: str | dict[str, Any], event: dict[str, Any] | None = None) -> None:
        session_id, event_copy = self._resolve_session_and_event(session_or_event, event)
        event_copy.setdefault("ts", time.time())
        self._events[session_id].append(event_copy)

    def add(self, session_or_event: str | dict[str, Any], event: dict[str, Any] | None = None) -> None:
        self.add_event(session_or_event, event)

    def window(self, session_or_count: str | int, count: int | None = None) -> list[dict[str, Any]]:
        if isinstance(session_or_count, str):
            session_id = session_or_count
            limit = 50 if count is None else count
        else:
            session_id = "default"
            limit = session_or_count
        return list(self._events[session_id])[-limit:]

    def drift(self, session_id: str = "default") -> float:
        events = list(self._events[session_id])
        if len(events) < 2:
            return 0.0

        intervals = []
        for index in range(1, len(events)):
            intervals.append(events[index]["ts"] - events[index - 1]["ts"])

        if len(intervals) < 2:
            return 0.0

        mean_interval = sum(intervals) / len(intervals)
        variance = sum((interval - mean_interval) ** 2 for interval in intervals) / len(intervals)
        return float(variance)

    def clear(self, session_id: str = "default") -> None:
        self._events.pop(session_id, None)

    def clear_all(self) -> None:
        self._events.clear()

    def __len__(self) -> int:
        return sum(len(events) for events in self._events.values())
