from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Session(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    created_at: datetime
    assurance_level: str  # e.g. A0, A1, A2, A3
    status: str = "active"
