from __future__ import annotations

from enum import Enum


class ReasonCode(str, Enum):
    LIVENESS_CONFIRMED = "liveness_confirmed"
    VERIFIED_CHALLENGE = "verified_challenge"
    AI_MEDIATION_RISK = "ai_mediation_risk"
    RELAY_RISK = "relay_risk"
    TEMPORAL_DRIFT = "temporal_drift"
    CROSS_SESSION_RISK = "cross_session_risk"
    DETERMINISTIC_POLICY_VIOLATION = "deterministic_policy_violation"
    ILLEGAL_CONTENT = "illegal_content"
    REVIEW_DISAGREEMENT = "review_disagreement"
    LOW_CONFIDENCE = "low_confidence"
    SURFACE_TELEGRAM = "surface_telegram"
    SURFACE_WEB_GUARD = "surface_web_guard"
