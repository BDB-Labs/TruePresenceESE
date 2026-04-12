from fastapi import FastAPI
from datetime import datetime
import uuid
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.session import Session

app = FastAPI()
SESSIONS = {}


@app.post("/session/create")
def create_session(assurance_level: str = "A1"):
    session_id = str(uuid.uuid4())
    session = Session(
        session_id=session_id,
        created_at=datetime.utcnow(),
        assurance_level=assurance_level,
    )
    SESSIONS[session_id] = session
    return {"session_id": session_id, "assurance_level": assurance_level}
