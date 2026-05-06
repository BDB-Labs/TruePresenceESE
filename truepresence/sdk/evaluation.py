from __future__ import annotations

from truepresence.detectors.human_plausibility import run_human_plausibility_detectors
from truepresence.evidence.sdk_artifacts import persist_sdk_evidence_artifact
from truepresence.scoring.model import score_interaction
from truepresence.sdk.contracts import (
    TruePresenceEvaluationRequest,
    TruePresenceEvaluationResponse,
)
from truepresence.sdk.privacy import ensure_privacy_safe_payload


def evaluate_interaction_request(
    request: TruePresenceEvaluationRequest,
) -> TruePresenceEvaluationResponse:
    ensure_privacy_safe_payload(request.model_dump())
    packet = request.feature_packet.model_copy(
        update={
            "tenant_id": request.feature_packet.tenant_id or request.tenant_id,
            "session_id": request.feature_packet.session_id or request.session_id,
        }
    )
    signals = run_human_plausibility_detectors(packet)
    response = score_interaction(
        signals=signals,
        feature_packet=packet,
        enforcement_mode=request.enforcement_mode,
    )
    persist_sdk_evidence_artifact(
        packet=packet,
        response=response,
        signals=signals,
        enforcement_mode=request.enforcement_mode,
    )
    return response
