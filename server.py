#!/usr/bin/env python3
"""TruePresence Server - Minimal working version"""
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict
import json
import uuid
import random

app = FastAPI(title="TruePresence")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory state
sessions = defaultdict(list)
event_history = defaultdict(list)
active_challenges = {}

CHALLENGES = [
    "Without pausing, type the last word you just read.",
    "Say 'orange' out loud, then type it.",
    "Type the third letter of what you see on screen.",
    "Describe your environment in one sentence.",
]

def evaluate(session_id: str, event: dict) -> dict:
    events = list(event_history[session_id])
    key_events = [e for e in events if e.get("event_type") == "key_timing"]
    pastes = [e for e in events if e.get("event_type") == "clipboard"]
    
    liveness = min(1.0, len(key_events) / 20.0)
    ai_med = min(1.0, len(pastes) / 5.0)
    relay = 0.8 if 0 < len(events) < 3 else 0.3
    
    score = (liveness * 0.5) + ((1 - ai_med) * 0.3) + ((1 - relay) * 0.2)
    
    if score < 0.4:
        decision = "reject"
    elif score < 0.65:
        decision = "step_up"
    else:
        decision = "allow"
    
    return {
        "session_id": session_id,
        "live_score": round(score, 3),
        "decision": decision,
        "signals": {"liveness": liveness, "ai_mediation": ai_med, "relay_risk": relay}
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"TruePresence": "online", "endpoint": "ws://host:8000/ws/{session_id}"}

@app.websocket("/ws/{session_id}")
async def ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    sessions[session_id].append(websocket)
    
    await websocket.send_json({"type": "welcome", "data": {"session_id": session_id}})
    
    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)
            
            if event.get("event_type") == "challenge_response":
                if session_id in active_challenges:
                    del active_challenges[session_id]
            
            event_history[session_id].append(event)
            result = evaluate(session_id, event)
            
            await websocket.send_json({"type": "trust_update", "data": result})
            
            # Challenge injection
            if 0.35 < result["live_score"] < 0.75 and session_id not in active_challenges:
                ch = {"id": str(uuid.uuid4()), "prompt": random.choice(CHALLENGES)}
                active_challenges[session_id] = ch
                await websocket.send_json({"type": "challenge", "challenge": ch})
    
    except WebSocketDisconnect:
        if session_id in sessions:
            sessions[session_id].remove(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)