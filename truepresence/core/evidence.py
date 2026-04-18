from typing import Any, Dict

from pydantic import BaseModel


class EvidenceBundle(BaseModel):
    session_id: str
    signals: Dict[str, float]
    raw_features: Dict[str, Any]
