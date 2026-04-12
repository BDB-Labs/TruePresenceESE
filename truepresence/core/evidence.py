from pydantic import BaseModel
from typing import Dict, Any


class EvidenceBundle(BaseModel):
    session_id: str
    signals: Dict[str, float]
    raw_features: Dict[str, Any]
