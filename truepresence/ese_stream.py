import statistics
from collections import deque
from typing import Any, Deque, Dict

rolling_window: Dict[str, Deque[Dict[str, Any]]] = {}


def update_window(session_id: str, event: Dict[str, Any]) -> None:
    if session_id not in rolling_window:
        rolling_window[session_id] = deque(maxlen=50)
    rolling_window[session_id].append(event)


def evaluate_incremental(session_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    update_window(session_id, event)
    window = list(rolling_window[session_id])
    
    # 1. Liveness signal (Quantity of interaction)
    key_timing = [e for e in window if e["event_type"] == "key_timing"]
    liveness = min(1.0, len(key_timing) / 20.0)
    
    # 2. AI Mediation signal (Tool-based interaction)
    paste = [e for e in window if e["event_type"] == "clipboard"]
    ai_mediation = min(1.0, len(paste) / 5.0)
    
    # 3. Relay Risk (Temporal gaps/latency)
    relay_risk = 0.8 if 0 < len(window) < 3 else 0.3
    
    # 4. Optimization Risk ("Too Perfect" signal)
    # Detects bots with unnaturally consistent typing intervals
    optimization_risk = 0.3
    if len(key_timing) >= 5:
        intervals = [e["payload"].get("interval_ms", 0) for e in key_timing]
        jitter = statistics.pstdev(intervals) if len(intervals) > 1 else 0.0
        # Very low jitter (< 15ms) is a strong indicator of automation
        if jitter < 15:
            optimization_risk = 0.9
        elif jitter > 50:
            optimization_risk = 0.1
        else:
            # Linear mapping between 15ms and 50ms
            optimization_risk = 0.9 - ((jitter - 15) / 35 * 0.8)

    # Ensemble Scoring
    # We weigh liveness and AI mediation highest, then relay and optimization
    score = (
        (liveness * 0.4) + 
        ((1 - ai_mediation) * 0.3) + 
        ((1 - relay_risk) * 0.2) + 
        ((1 - optimization_risk) * 0.1)
    )
    
    decision = "allow"
    if score < 0.4:
        decision = "reject"
    elif score < 0.65:
        decision = "step_up"

    return {
        "session_id": session_id,
        "live_score": round(score, 3),
        "decision": decision,
        "signals": {
            "liveness": liveness,
            "ai_mediation": ai_mediation,
            "relay_risk": relay_risk,
            "optimization_risk": round(optimization_risk, 3),
        },
    }
