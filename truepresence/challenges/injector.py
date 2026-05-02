from __future__ import annotations

import uuid
from typing import Any

RISK_LEVELS = {
    "none": 0.0,
    "low": 0.25,
    "medium": 0.55,
    "high": 0.85,
    "critical": 1.0,
}


def _risk_score(result: dict[str, Any]) -> float:
    raw = result.get("risk_score", result.get("risk_level", 0.0))
    if isinstance(raw, str):
        return RISK_LEVELS.get(raw.lower(), 0.0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


class ChallengeInjector:
    def should_inject(self, result: dict[str, Any]) -> bool:
        if result.get("challenge_required") is True:
            return True
        risk_score = _risk_score(result)
        return 0.3 < risk_score < 0.8

    def create_challenge(self) -> dict[str, str]:
        return {
            "id": str(uuid.uuid4()),
            "prompt": "Re-enter last word typed",
        }
