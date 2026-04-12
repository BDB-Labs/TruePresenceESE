from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import defaultdict
from typing import Dict, List
import json
import uuid
from truepresence.ese_runtime import ESEEnsembleRuntime
from truepresence.challenges.validator import ChallengeValidator

router = APIRouter()

# Initialize Core Components
ensemble = ESEEnsembleRuntime()
validator = ChallengeValidator()

connections: Dict[str, List[WebSocket]] = defaultdict(list)
session_events: Dict[str, List[dict]] = defaultdict(list)

CHALLENGE_PROMPTS = [
    "Without pausing, type the last word you just read.",
    "Say the word 'orange' out loud, then type it.",
    "Type the third letter of what you see on screen.",
    "Immediately describe your environment in one sentence.",
]

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    connections[session_id].append(websocket)
    
    await websocket.send_json({
        "type": "welcome",
        "data": {"session_id": session_id, "message": "TruePresence Connected to ESE Ensemble"}
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)
            
            # 1. Handle Challenge Responses (Phase 2)
            if event.get("event_type") == "challenge_response":
                response_text = event.get("payload", {}).get("text", "")
                val_result = validator.validate_response(session_id, response_text)
                
                # Feed challenge result back as a special event for ESE to analyze
                event = {
                    "event_type": "challenge_result",
                    "payload": val_result
                }

            # 2. Store and Evaluate via Ensemble (Phase 1)
            session_events[session_id].append(event)
            # Convert dict events to Pydantic Event objects if necessary, 
            # but ensemble_runtime handles them as a list for now.
            result = ensemble.evaluate(session_id, session_events[session_id])
            
            # 3. Trust Update
            await websocket.send_json({"type": "trust_update", "data": result})
            
            # 4. Adaptive Challenge Injection (Uncertainty Zone)
            score = result["trust_score"]
            if 0.35 < score < 0.75:
                challenge = {
                    "id": str(uuid.uuid4()),
                    "prompt": CHALLENGE_PROMPTS[hash(session_id) % len(CHALLENGE_PROMPTS)],
                    "created_at": __import__("time").time()
                }
                # Track in validator
                validator.issue_challenge(session_id, challenge["prompt"])
                await websocket.send_json({
                    "type": "challenge",
                    "challenge": challenge
                })
                
    except WebSocketDisconnect:
        if session_id in connections:
            connections[session_id].remove(websocket)

