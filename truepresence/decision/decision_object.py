from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DecisionState(str, Enum):
    ALLOW = "ALLOW"
    OBSERVE = "OBSERVE"
    ELEVATED_OBSERVE = "ELEVATED_OBSERVE"
    CHALLENGE = "CHALLENGE"
    STEP_UP_AUTH = "STEP_UP_AUTH"
    RESTRICT = "RESTRICT"
    BLOCK = "BLOCK"
    EJECT = "EJECT"


@dataclass
class DecisionObject:
    decision_id: str
    session_id: str
    tenant_id: str
    surface: str
    state: str
    recommended_enforcement: str
    confidence: float
    risk_level: str
    reason_codes: List[str] = field(default_factory=list)
    challenge_required: bool = False
    step_up_required: bool = False
    human_review_required: bool = False
    evidence_packet_id: Optional[str] = None
    argument_graph_id: Optional[str] = None
    role_report_ids: List[str] = field(default_factory=list)
    decision_trace_id: Optional[str] = None
    tier_path: str = "tier1"
    metadata: Dict[str, Any] = field(default_factory=dict)
    human_probability: float = 0.5
    bot_probability: float = 0.5
    explanation: str = ""

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)
