import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Challenge:
    challenge_id: str
    challenge_type: str
    payload: Dict[str, Any]
    created_at: float
    ttl: float = 10.0

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl


def create_challenge(challenge_type: str, payload: Dict[str, Any], ttl: float = 10.0) -> Challenge:
    return Challenge(
        challenge_id=str(uuid.uuid4()),
        challenge_type=challenge_type,
        payload=payload,
        created_at=time.time(),
        ttl=ttl,
    )
