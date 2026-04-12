from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any


class ChallengeResponse(BaseModel):
    challenge_id: str
    session_id: str
    timestamp: datetime
    response: Dict[str, Any]
    client_latency_ms: float
