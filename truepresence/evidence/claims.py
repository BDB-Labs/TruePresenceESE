from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ClaimType(str, Enum):
    PRESENCE = "presence"
    RISK = "risk"
    CHALLENGE = "challenge"
    IDENTITY = "identity"
    POLICY = "policy"


@dataclass
class Claim:
    claim_id: str
    claim_type: str
    label: str
    evidence_refs: List[str] = field(default_factory=list)
    confidence_hint: Optional[float] = None
    created_at: Optional[str] = None
    valid_window: Optional[Dict[str, str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def type(self) -> str:
        return self.claim_type

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)
