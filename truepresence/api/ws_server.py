from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import defaultdict
from typing import Dict, List
import json
import uuid
import time
from truepresence.ese_runtime import ESEEnsembleRuntime
from truepresence.challenges.validator import ChallengeValidator
from truepresence.redteam.evaluate import RedTeamEvaluator

router = APIRouter()

# Initialize Core Components
ensemble = ESEEnsembleRuntime()
validator = ChallengeValidator()
redteam_evaluator = RedTeamEvaluator()

connections: Dict[str, List[WebSocket]] = defaultdict(list)
session_events: Dict[str, List[dict]] = defaultdict(list)
session_modes: Dict[str, str] = defaultdict(str)

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
    
    # Get session mode (default to "production" if not set)
    session_mode = session_modes.get(session_id, "production")
    
    await websocket.send_json({
        "type": "welcome",
        "data": {"session_id": session_id, "message": "TruePresence Connected to ESE Ensemble", "mode": session_mode}
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                event = json.loads(data)
            except json.JSONDecodeError as e:
                await websocket.send_json({"type": "error", "message": f"Invalid JSON: {e}"})
                continue
            
            # Handle mode setting (for test/gatekeeper modes)
            if event.get("event_type") == "set_mode":
                session_mode = event.get("payload", {}).get("mode", "production")
                session_modes[session_id] = session_mode
                continue
            
            # 1. Handle Challenge Responses (Phase 2)
            if event.get("event_type") == "challenge_response":
                response_text = event.get("payload", {}).get("text", "")
                val_result = validator.validate_response(session_id, response_text)
                
                event = {
                    "event_type": "challenge_result",
                    "payload": val_result
                }

            # 2. Store and Evaluate via Ensemble (Phase 1)
            session_events[session_id].append(event)
            result = ensemble.evaluate(session_id, session_events[session_id])
            
            # 3. Self-Evaluation for Test Mode (Red Team Integration)
            if session_mode == "test" and event.get("attack_type"):
                # Evaluate as attack and compute reward
                attack_result = redteam_evaluator.run_attack(
                    test_name=f"ws_attack_{session_id}",
                    events=[event],
                    ground_truth=True  # Known attack in test mode
                )
                
                # Send reward feedback to client for monitoring
                await websocket.send_json({
                    "type": "reward_update",
                    "data": {
                        "reward": attack_result.get("reward", 0.0),
                        "performance": redteam_evaluator.get_performance()
                    }
                })
            
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

