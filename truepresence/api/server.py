from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import sys
import os
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.session import Session
from truepresence.exceptions import TruePresenceError, OrchestratorError, RoleError

# Configure logging - CRITICAL systems must log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TruePresence ESE API", version="1.0.0")
SESSIONS = {}

# Orchestrator factory - creates per-session orchestrators
_orchestrators = {}


# Exception handlers - CRITICAL: System does NOT fail silently
@app.exception_handler(TruePresenceError)
async def truepresence_exception_handler(request, exc: TruePresenceError):
    """Handle TruePresence errors with full context."""
    logger.error(f"TruePresence error: {exc.message}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Catch-all for unexpected errors - MUST be visible."""
    logger.critical(f"UNHANDLED EXCEPTION: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": f"Unexpected error: {str(exc)}",
            "details": {"exception_type": type(exc).__name__}
        }
    )


def get_orchestrator(session_id: str):
    """Get or create orchestrator for a specific session."""
    if session_id not in _orchestrators:
        from truepresence.core.orchestrator_v3 import TruePresenceOrchestratorV3
        _orchestrators[session_id] = TruePresenceOrchestratorV3()
    return _orchestrators[session_id]


# Request Models
class EventSignals(BaseModel):
    """Event signals from client SDK."""
    event_type: str
    timestamp: float
    payload: Dict[str, Any]
    features: Optional[Dict[str, float]] = None


class ChallengeResponse(BaseModel):
    """Challenge response from client."""
    challenge_id: str
    response: str
    response_time_ms: float


class EvaluateRequest(BaseModel):
    """Request model for /v1/evaluate endpoint."""
    mode: str = Field(default="sdk", description="Mode: sdk or gatekeeper")
    session_id: str
    event: EventSignals
    context: Optional[Dict[str, Any]] = Field(default=None, description="Context like platform, IP, etc.")
    challenge_responses: Optional[List[ChallengeResponse]] = None


# Response Models
class RoleReasoning(BaseModel):
    """Reasoning trace for a role."""
    role: str
    reasoning: str


class TemporalSignals(BaseModel):
    """Temporal analysis signals."""
    drift: float
    cross_session_risk: float


class EvaluateResponse(BaseModel):
    """Response model for /v1/evaluate endpoint."""
    human_probability: float
    bot_probability: float
    confidence: float
    decision: str  # allow|challenge|block|review
    risk_factors: List[str]
    reasoning_trace: Dict[str, str]
    temporal_signals: TemporalSignals
    session_id: str


@app.post("/session/create")
def create_session(assurance_level: str = "A1"):
    """Create a new session."""
    session_id = str(uuid.uuid4())
    session = Session(
        session_id=session_id,
        created_at=datetime.utcnow(),
        assurance_level=assurance_level,
    )
    SESSIONS[session_id] = session
    return {"session_id": session_id, "assurance_level": assurance_level}


@app.post("/v1/evaluate", response_model=EvaluateResponse)
def evaluate(request: EvaluateRequest):
    """
    Unified API endpoint for TruePresence evaluation.
    
    Accepts:
    - mode: sdk (normal) or gatekeeper (high security)
    - session_id: Unique session identifier
    - event.signals: Event data with type, timestamp, payload, features
    - context.platform: Platform information (web, mobile, etc.)
    - challenge_responses: Optional challenge responses
    
    Returns:
    - human_probability: Probability user is human (0-1)
    - bot_probability: Probability user is bot (0-1)  
    - confidence: Confidence in the decision (0-1)
    - decision: allow|challenge|block|review
    - risk_factors: List of detected risk factors
    - reasoning_trace: Per-role reasoning
    - temporal_signals: Drift and cross-session risk
    """
    # Get or create session
    session = SESSIONS.get(request.session_id)
    if not session:
        # Create new session if doesn't exist
        session = Session(
            session_id=request.session_id,
            created_at=datetime.utcnow(),
            assurance_level="A1"
        )
        SESSIONS[request.session_id] = session
    
    # Build event dict from request
    event_dict = {
        "event_type": request.event.event_type,
        "timestamp": request.event.timestamp,
        "payload": request.event.payload,
        "session_id": request.session_id
    }
    
    if request.event.features:
        event_dict["features"] = request.event.features
    
    # Add context if provided
    if request.context:
        event_dict["context"] = request.context
    
    # Handle challenge responses
    if request.challenge_responses:
        for challenge in request.challenge_responses:
            event_dict["challenge_response"] = {
                "challenge_id": challenge.challenge_id,
                "response": challenge.response,
                "response_time_ms": challenge.response_time_ms
            }
    
    # Get per-session orchestrator and evaluate
    orchestrator = get_orchestrator(request.session_id)
    result = orchestrator.evaluate(
        session_id=request.session_id,
        session={"session_id": request.session_id, "mode": request.mode},
        event=event_dict
    )
    
    # Build response
    return EvaluateResponse(
        human_probability=result.get("human_probability", 0.5),
        bot_probability=result.get("bot_probability", 0.5),
        confidence=result.get("confidence", 0.5),
        decision=result.get("decision", "review"),
        risk_factors=result.get("risk_factors", []),
        reasoning_trace=result.get("reasoning_trace", {}),
        temporal_signals=TemporalSignals(
            drift=result.get("temporal_signals", {}).get("drift", 0.0),
            cross_session_risk=result.get("temporal_signals", {}).get("cross_session_risk", 0.0)
        ),
        session_id=request.session_id
    )


@app.get("/health")
def health_check():
    """Health check endpoint - aggregates across all session orchestrators."""
    # Aggregate health from all orchestrators
    total_sessions = len(_orchestrators)
    orchestrator_health = {}
    
    for sid, orch in _orchestrators.items():
        try:
            orchestrator_health[sid] = orch.health_check()
        except:
            orchestrator_health[sid] = {"error": "unavailable"}
    
    return {
        "status": "healthy",
        "total_sessions": total_sessions,
        "orchestrators": orchestrator_health
    }


@app.get("/v1/sessions/{session_id}/cluster")
def get_session_cluster(session_id: str):
    """Get connected sessions in the identity graph."""
    orchestrator = get_orchestrator(session_id)
    cluster = orchestrator.get_session_cluster(session_id)
    return {"session_id": session_id, "cluster": list(cluster)}


@app.post("/v1/sessions/{session_id}/reset")
def reset_session(session_id: str):
    """Reset session memory."""
    orchestrator = get_orchestrator(session_id)
    orchestrator.memory.clear()
    return {"session_id": session_id, "status": "reset"}