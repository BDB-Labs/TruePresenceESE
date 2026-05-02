from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ese_core import ESEEngine

engine = ESEEngine()


def _as_events(event_batch: Any) -> list[dict[str, Any]]:
    if isinstance(event_batch, list):
        return [event for event in event_batch if isinstance(event, dict)]
    if not isinstance(event_batch, dict):
        return []
    raw_events = event_batch.get("events")
    if isinstance(raw_events, Iterable) and not isinstance(raw_events, (str, bytes, dict)):
        return [event for event in raw_events if isinstance(event, dict)]
    return [event_batch]


def _number_from(*values: Any, default: float = 0.0) -> float:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _build_evidence(event_batch: Any) -> dict[str, Any]:
    events = _as_events(event_batch)
    paste_behavior = False
    typing_entropy_values: list[float] = []
    message_velocity = 0.0
    content_similarity = 0.0

    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        features = event.get("features") if isinstance(event.get("features"), dict) else {}
        signals = event.get("signals") if isinstance(event.get("signals"), dict) else {}
        event_type = str(event.get("event_type") or "").lower()

        paste_behavior = paste_behavior or bool(
            event.get("clipboard")
            or event_type == "clipboard"
            or payload.get("clipboard")
            or payload.get("paste")
            or payload.get("action") == "paste"
        )
        typing_entropy_values.append(
            _number_from(
                event.get("entropy"),
                features.get("entropy"),
                features.get("typing_entropy"),
                signals.get("typing_entropy"),
                payload.get("entropy"),
                default=0.5,
            )
        )
        message_velocity = max(
            message_velocity,
            _number_from(features.get("message_velocity"), signals.get("message_velocity"), default=0.0),
        )
        content_similarity = max(
            content_similarity,
            _number_from(features.get("content_similarity"), signals.get("content_similarity"), default=0.0),
        )

    return {
        "event_count": len(events),
        "paste_behavior": paste_behavior,
        "typing_entropy": min(typing_entropy_values) if typing_entropy_values else 0.5,
        "message_velocity": message_velocity,
        "content_similarity": content_similarity,
    }


def evaluate_presence(event_batch: Any) -> dict[str, Any]:
    evidence = _build_evidence(event_batch)
    return engine.evaluate(evidence)
