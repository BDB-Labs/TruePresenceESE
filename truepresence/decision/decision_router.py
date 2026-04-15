from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from truepresence.decision.decision_object import DecisionState
from truepresence.decision.tier_router import choose_tier


@dataclass
class DecisionRoute:
    state: str
    confidence: float
    reason_codes: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)


class DecisionRouter:
    """Compatibility shim over the canonical tier router."""

    def route(self, packet, argument_graph, context: Dict[str, Any] | None = None) -> DecisionRoute | None:
        tier = choose_tier(packet, argument_graph, context or {})
        if tier != "tier0":
            return None
        return DecisionRoute(
            state=DecisionState.EJECT.value,
            confidence=0.99,
            reason_codes=[],
            details={"tier": tier},
        )
