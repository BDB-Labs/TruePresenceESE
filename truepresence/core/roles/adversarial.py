from typing import Dict, Any, List

class AdversarialReviewer:
    """
    The most critical role: specifically hunts for 'Too Perfect' signals
    and contradictory evidence to challenge optimistic scores.
    """
    def analyze(self, evidence: Dict[str, Any], analyst_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        risks = []
        
        # 1. Check for the 'Too Perfect' optimization signal
        opt_risk = evidence["signals"].get("optimization_risk", 0.0)
        if opt_risk > 0.7:
            risks.append("unnaturally_consistent_timing")
        
        # 2. Check for contradiction (e.g. High liveness but high mediation)
        liveness = evidence["signals"].get("liveness", 0.0)
        mediation = evidence["signals"].get("ai_mediation", 0.0)
        if liveness > 0.8 and mediation > 0.5:
            risks.append("contradictory_presence_signals")
        
        # 3. Check for lack of entropy
        mouse_entropy = evidence["signals"].get("mouse_entropy", 0.0)
        if mouse_entropy < 0.1:
            risks.append("low_interaction_entropy")

        severity = 0.0
        if risks:
            severity = min(1.0, len(risks) * 0.3)
            
        return {
            "role": "adversarial_reviewer",
            "findings": risks,
            "severity": severity,
            "impact": "negative" if risks else "neutral"
        }
