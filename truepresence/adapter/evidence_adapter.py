import statistics
from typing import Any, Dict, List

from truepresence.core.events import Event
from truepresence.core.evidence import EvidenceBundle


class EvidenceAdapter:
    """
    Translates raw event streams into structured Evidence Bundles for the ESE core.
    This decouples raw data collection from cognitive reasoning.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def transform(self, session_id: str, events: List[Event]) -> EvidenceBundle:
        # 1. Extract relevant event types
        key_timing = [e for e in events if e.event_type == "key_timing"]
        pastes = [e for e in events if e.event_type == "clipboard"]
        mouse_moves = [e for e in events if e.event_type == "cursor_move"]
        
        # 2. Compute low-level features
        # Typing Liveness
        liveness_score = min(1.0, len(key_timing) / 20.0)
        
        # AI Mediation (Paste ratio)
        paste_ratio = len(pastes) / len(events) if events else 0.0
        
        # Relay Risk (Event density)
        relay_risk = 0.8 if 0 < len(events) < 3 else 0.3
        
        # Optimization Risk (Timing Jitter)
        optimization_risk = 0.3
        if len(key_timing) >= 5:
            intervals = [e.payload.get("interval_ms", 0) for e in key_timing]
            jitter = statistics.pstdev(intervals) if len(intervals) > 1 else 0.0
            if jitter < 15:
                optimization_risk = 0.9
            elif jitter > 50:
                optimization_risk = 0.1
            else:
                optimization_risk = 0.9 - ((jitter - 15) / 35 * 0.8)
        
        # Mouse Entropy (The "Human Hand" signal)
        # Simple entropy check: variance in mouse movement deltas
        mouse_entropy = 0.0
        if len(mouse_moves) > 5:
            dx_vals = [e.payload.get("dx", 0) for e in mouse_moves]
            mouse_entropy = statistics.pstdev(dx_vals) / 100.0 # Normalized
            mouse_entropy = min(1.0, mouse_entropy)

        return EvidenceBundle(
            session_id=session_id,
            signals={
                "liveness": liveness_score,
                "ai_mediation": paste_ratio,
                "relay_risk": relay_risk,
                "optimization_risk": optimization_risk,
                "mouse_entropy": mouse_entropy
            },
            raw_features={
                "event_count": len(events),
                "key_count": len(key_timing),
                "paste_count": len(pastes),
                "mouse_count": len(mouse_moves)
            }
        )
