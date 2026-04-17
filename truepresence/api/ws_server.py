import json
import time
import uuid
from collections import defaultdict
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from truepresence.challenges.deterministic import stable_index
from truepresence.challenges.validator import ChallengeValidator
from truepresence.core.runtime import decision_engine as shared_decision_engine
from truepresence.redteam.evaluate import RedTeamEvaluator

router = APIRouter()

# Shared orchestrator — same instance as Telegram and REST API
validator = ChallengeValidator()
redteam_evaluator = RedTeamEvaluator()

connections: Dict[str, List[WebSocket]] = defaultdict(list)
session_events: Dict[str, List[dict]] = defaultdict(list)
session_modes: Dict[str, str] = defaultdict(str)
challenge_last_issued: Dict[str, float] = {}  # Track last challenge time per session
SESSION_EVENT_CAP = 500  # Max events to retain per session
CHALLENGE_COOLDOWN_SECONDS = 30  # Minimum seconds between challenges

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

            # 2. Store and Evaluate via shared orchestrator
            session_events[session_id].append(event)
            # Cap session events to prevent unbounded memory growth
            if len(session_events[session_id]) > SESSION_EVENT_CAP:
                session_events[session_id] = session_events[session_id][-SESSION_EVENT_CAP:]
            result = shared_decision_engine.evaluate(
                surface="web_guard",
                session_id=session_id,
                tenant_id="default",
                session={"session_id": session_id, "mode": session_mode, "tenant_id": "default"},
                event=event,
            ).to_response()
            trust_score = result.get("human_probability", 0.5)
            
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

            # 4. Adaptive Challenge Injection (Uncertainty Zone) with cooldown
            score = trust_score
            current_time = time.time()
            last_challenge_time = challenge_last_issued.get(session_id, 0)
            time_since_last_challenge = current_time - last_challenge_time
            
            if 0.35 < score < 0.75 and time_since_last_challenge >= CHALLENGE_COOLDOWN_SECONDS:
                challenge = {
                    "id": str(uuid.uuid4()),
                    "prompt": CHALLENGE_PROMPTS[stable_index(session_id, len(CHALLENGE_PROMPTS))],
                    "created_at": current_time
                }
                challenge_last_issued[session_id] = current_time
                # Track in validator
                validator.issue_challenge(session_id, challenge["prompt"])
                await websocket.send_json({
                    "type": "challenge",
                    "challenge": challenge
                })
                
    except WebSocketDisconnect:
        if session_id in connections:
            connections[session_id].remove(websocket)
