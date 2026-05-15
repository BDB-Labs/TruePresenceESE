from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from truepresence.api.legacy_rest_auth import require_legacy_rest_auth
from truepresence.api.rate_limit import limiter as http_limiter
from truepresence.core.runtime import (
    decision_engine as shared_decision_engine,
)
from truepresence.core.runtime import (
    orchestrator as shared_orchestrator,
)
from truepresence.core.session import Session
from truepresence.exceptions import TruePresenceError
from truepresence.evidence.sdk_artifacts import sdk_evidence_store
from truepresence.sdk.contracts import (
    TruePresenceEvaluationRequest,
    TruePresenceEvaluationResponse,
)
from truepresence.sdk.evaluation import evaluate_interaction_request
from truepresence.sdk.privacy import RawContentRejected, ensure_privacy_safe_payload
from truepresence.runtime.health import dependency_components_status

# Configure logging - CRITICAL systems must log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TruePresence ESE API", version="1.0.0")
app.state.limiter = http_limiter
app.add_middleware(SlowAPIMiddleware)

dashboard_bearer_scheme = HTTPBearer()
_DASHBOARD_ADMIN_ROLES = {"admin", "super_admin"}

# Sessions are now managed by the distributed runtime (Redis)
# removed: SESSIONS = {}


def _distributed_runtime():
    candidates = [
        shared_orchestrator,
        getattr(shared_orchestrator, "legacy_orchestrator", None),
    ]
    for candidate in candidates:
        distributed = getattr(candidate, "distributed", None)
        if distributed is not None and getattr(distributed, "available", False):
            return distributed
    return None


def _get_session_field(distributed, session_id: str, field: str):
    if hasattr(distributed, "get_session_field"):
        return distributed.get_session_field(session_id, field)
    if hasattr(distributed, "load_session"):
        session = distributed.load_session(session_id) or {}
        return session.get(field)
    return None


def _safe_validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    """Return validation error details without echoing submitted values."""
    return [
        {
            "loc": error.get("loc", ()),
            "msg": error.get("msg", "Invalid request payload"),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]


def _dashboard_risk_level(likelihoods: dict[str, float]) -> str:
    risk_score = max(
        float(likelihoods.get("automation_likelihood") or 0.0),
        float(likelihoods.get("agentic_control_likelihood") or 0.0),
    )
    if risk_score >= 0.75:
        return "high"
    if risk_score >= 0.5:
        return "medium"
    return "low"


def _sdk_dashboard_evidence_card(artifact) -> dict[str, Any]:
    likelihoods = dict(artifact.likelihoods)
    return {
        "event_type": "web_sdk",
        "surface": artifact.surface,
        "risk_level": _dashboard_risk_level(likelihoods),
        "human_presence_likelihood": likelihoods.get("human_presence_likelihood"),
        "automation_likelihood": likelihoods.get("automation_likelihood"),
        "agentic_control_likelihood": likelihoods.get("agentic_control_likelihood"),
        "confidence": artifact.confidence,
        "reason_codes": list(artifact.reason_codes),
        "evidence_packet_id": artifact.evidence_packet_id,
        "decision_id": artifact.scoring_metadata.get("decision_id"),
        "recommended_action": artifact.recommended_action,
        "timestamp": artifact.created_at,
    }


def get_dashboard_user(
    credentials: HTTPAuthorizationCredentials = Depends(dashboard_bearer_scheme),  # noqa: B008
) -> dict[str, Any]:
    """Authenticate dashboard evidence requests with the existing JWT user model."""
    from truepresence.api.auth import get_current_user

    return get_current_user(credentials)


def _is_dashboard_admin(user: dict[str, Any]) -> bool:
    return str(user.get("role") or "").lower() in _DASHBOARD_ADMIN_ROLES


def _requested_tenant_id(request: Request) -> str | None:
    return (
        request.query_params.get("tenant_id")
        or request.query_params.get("tenant")
        or None
    )


def _authorized_listing_tenant(
    *,
    request: Request,
    user: dict[str, Any],
) -> str | None:
    requested_tenant = _requested_tenant_id(request)
    if _is_dashboard_admin(user):
        return requested_tenant

    user_tenant = user.get("tenant_id")
    if not user_tenant:
        raise HTTPException(status_code=403, detail="Tenant access required")
    if requested_tenant and requested_tenant != user_tenant:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    return str(user_tenant)


def _can_access_artifact(user: dict[str, Any], artifact) -> bool:
    if _is_dashboard_admin(user):
        return True
    return bool(user.get("tenant_id")) and artifact.tenant_id == user.get("tenant_id")


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


# Exception handlers - CRITICAL: System does NOT fail silently
@app.exception_handler(TruePresenceError)
async def truepresence_exception_handler(request, exc: TruePresenceError):
    """Handle TruePresence errors with full context."""
    logger.error(f"TruePresence error: {exc.message}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": exc.__class__.__name__,
            "message": "TruePresence request failed",
            "details": {"error_type": exc.__class__.__name__},
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
            "message": "An internal server error occurred.",
            "details": {"exception_type": type(exc).__name__}
        }
    )


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


class CreateSessionRequest(BaseModel):
    assurance_level: str = "A1"


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
    state: str
    human_probability: float
    bot_probability: float
    confidence: float
    decision: str  # allow|challenge|block|review
    risk_factors: List[str]
    reason_codes: List[str]
    reasoning_trace: Dict[str, Any]
    temporal_signals: TemporalSignals
    session_id: str


@app.post("/session/create")
def create_session(
    request: Optional[CreateSessionRequest] = None,
    assurance_level: Optional[str] = None,
    _legacy: dict | None = Depends(require_legacy_rest_auth),
):
    """Create a new session."""
    resolved_assurance_level = assurance_level or (request.assurance_level if request else "A1")
    session_id = str(uuid.uuid4())
    session = Session(
        session_id=session_id,
        created_at=datetime.now(timezone.utc),
        assurance_level=resolved_assurance_level,
    )
    
    # Store session in distributed runtime (Redis)
    distributed = _distributed_runtime()
    if distributed is not None:
        distributed.update_session_field(
            session_id, "session_meta", session.model_dump()
        )
    
    return {"session_id": session_id, "assurance_level": resolved_assurance_level}


@app.post("/v1/evaluate", response_model=EvaluateResponse)
def evaluate(
    request: EvaluateRequest,
    _legacy: dict | None = Depends(require_legacy_rest_auth),
):
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
    session_data = None
    distributed = _distributed_runtime()
    if distributed is not None:
        session_data = _get_session_field(distributed, request.session_id, "session_meta")

    if not session_data:
        # Create new session if doesn't exist
        session = Session(
            session_id=request.session_id,
            created_at=datetime.now(timezone.utc),
            assurance_level="A1"
        )
        if distributed is not None:
            distributed.update_session_field(
                request.session_id, "session_meta", session.model_dump()
            )
        session_data = session.model_dump()
    
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
    
    result = shared_decision_engine.evaluate(
        surface=request.context.get("platform", "web_guard") if request.context else "web_guard",
        session_id=request.session_id,
        tenant_id=(request.context or {}).get("tenant_id", "default"),
        session={
            "session_id": request.session_id,
            "mode": request.mode,
            "tenant_id": (request.context or {}).get("tenant_id", "default"),
            **(session_data or {}),
            **(request.context or {}),
        },
        event=event_dict,
        challenge_results=[
            {
                "challenge_id": challenge.challenge_id,
                "response": challenge.response,
                "response_time_ms": challenge.response_time_ms,
            }
            for challenge in (request.challenge_responses or [])
        ],
    ).to_response()
    
    # Build response
    return EvaluateResponse(
        state=result.get("state", "OBSERVE"),
        human_probability=result.get("human_probability", 0.5),
        bot_probability=result.get("bot_probability", 0.5),
        confidence=result.get("confidence", 0.5),
        decision=result.get("decision", "review"),
        risk_factors=result.get("risk_factors", []),
        reason_codes=result.get("reason_codes", []),
        reasoning_trace=result.get("reasoning_trace", {}),
        temporal_signals=TemporalSignals(
            drift=result.get("temporal_signals", {}).get("drift", 0.0),
            cross_session_risk=result.get("temporal_signals", {}).get("cross_session_risk", 0.0)
        ),
        session_id=request.session_id
    )


@app.post(
    "/v1/truepresence/evaluate-interaction",
    response_model=TruePresenceEvaluationResponse,
)
@http_limiter.limit("240/minute")
async def evaluate_interaction(request: Request):
    """Evaluate privacy-preserving web interaction features without Telegram."""
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    try:
        ensure_privacy_safe_payload(payload)
        evaluation_request = TruePresenceEvaluationRequest.model_validate(payload)
    except RawContentRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_safe_validation_errors(exc)) from exc

    return evaluate_interaction_request(evaluation_request)


@app.get("/v1/truepresence/evidence/cards")
def list_sdk_dashboard_evidence_cards(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    user: dict[str, Any] = Depends(get_dashboard_user),  # noqa: B008
):
    """List content-minimized SDK evidence cards for the dashboard."""
    tenant_id = _authorized_listing_tenant(request=request, user=user)
    artifacts = sdk_evidence_store.list_recent(tenant_id=tenant_id, limit=limit)
    cards = [_sdk_dashboard_evidence_card(artifact) for artifact in artifacts]
    return {"tenant_id": tenant_id, "count": len(cards), "evidence_cards": cards}


@app.get("/v1/truepresence/evidence/{evidence_packet_id}")
def get_sdk_evidence_artifact(
    evidence_packet_id: str,
    user: dict[str, Any] = Depends(get_dashboard_user),  # noqa: B008
):
    """Retrieve a content-minimized SDK/web evaluation evidence artifact."""
    artifact = sdk_evidence_store.get(evidence_packet_id)
    if artifact is None or not _can_access_artifact(user, artifact):
        raise HTTPException(status_code=404, detail="Evidence artifact not found")
    return artifact.model_dump(mode="json")


@app.get("/health")
def health_check():
    """Runtime health plus dependency snapshot (database, Redis)."""
    deps = dependency_components_status()
    degraded = any(
        deps.get(k) not in {"ok", "unconfigured"}
        for k in ("database", "redis")
        if k in deps
    )
    try:
        orchestrator_type = type(shared_orchestrator).__name__
        has_health_check = hasattr(shared_orchestrator, "health_check")

        if has_health_check:
            shared_orchestrator.health_check()

        body: dict[str, Any] = {
            "status": "degraded" if degraded else "ok",
            "orchestrator": orchestrator_type,
            "has_health_check": has_health_check,
            "runtime_mode": getattr(shared_orchestrator, "mode", "full"),
            "runtime_degraded_reason": getattr(shared_orchestrator, "degraded_reason", None),
            "dependencies": deps,
        }
        if degraded:
            return JSONResponse(status_code=503, content=body)
        return body
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "error": "health_check_failed",
                "details": {"exception_type": type(e).__name__},
                "dependencies": deps,
            },
        )


@app.get("/v1/sessions/{session_id}/cluster")
def get_session_cluster(
    session_id: str,
    _legacy: dict | None = Depends(require_legacy_rest_auth),
):
    """Get connected sessions in the identity graph."""
    cluster = shared_orchestrator.get_session_cluster(session_id)
    return {"session_id": session_id, "cluster": list(cluster)}


@app.post("/v1/sessions/{session_id}/reset")
def reset_session(
    session_id: str,
    _legacy: dict | None = Depends(require_legacy_rest_auth),
):
    """Reset session memory."""
    shared_orchestrator.memory.clear(session_id)
    return {"session_id": session_id, "status": "reset"}
