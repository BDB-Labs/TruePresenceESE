from typing import List, Dict, Any
from core.events import Event
from core.evidence import EvidenceBundle
from signals.liveness import compute_liveness
from signals.relay import compute_relay_risk
from signals.ai_mediation import compute_ai_mediation


def build_evidence(session_id: str, events: List[Event]) -> EvidenceBundle:
    return EvidenceBundle(
        session_id=session_id,
        signals={
            "liveness_score": compute_liveness(events),
            "relay_risk": compute_relay_risk(events),
            "ai_mediation_score": compute_ai_mediation(events),
        },
        raw_features={"event_count": len(events)},
    )
