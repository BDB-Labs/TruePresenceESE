from typing import List
from core.events import Event


def compute_ai_mediation(events: List[Event]) -> float:
    text_events = [e for e in events if e.event_type in ("challenge_response", "clipboard")]
    if not text_events:
        return 0.1
    copy_paste = sum(
        1 for e in text_events
        if e.payload.get("pasted") or e.payload.get("paste", False)
    )
    ratio = copy_paste / len(text_events)
    return min(1.0, max(0.0, ratio * 2.0))
