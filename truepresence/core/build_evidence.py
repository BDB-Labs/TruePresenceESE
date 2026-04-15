from typing import List

from truepresence.core.events import Event
from truepresence.core.evidence import EvidenceBundle
from truepresence.signals.ai_mediation import compute_ai_mediation
from truepresence.signals.liveness import compute_liveness
from truepresence.signals.relay import compute_relay_risk


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
