from typing import Dict, Any, List

class TrustSynthesizer:
    """
    Combines analyst findings and adversarial review into a final trust score.
    """
    def synthesize(self, analysts: List[Dict[str, Any]], adversary: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        # Weights from config
        weights = config.get("signals", {})
        
        # Calculate base score from analysts
        # We map the findings to confidence levels
        base_score = 0.0
        count = 0
        
        for a in analysts:
            base_score += a.get("confidence", 0.5)
            count += 1
            
        avg_confidence = base_score / count if count > 0 else 0.5
        
        # Apply adversarial penalty
        penalty = adversary.get("severity", 0.0) * 0.5
        final_score = max(0.0, min(1.0, avg_confidence - penalty))
        
        # Decision mapping
        thresholds = config.get("thresholds", {})
        if final_score < thresholds.get("reject", 0.35):
            decision = "reject"
        elif final_score < thresholds.get("step_up", 0.4):
            decision = "step_up"
        else:
            decision = "allow"
            
        return {
            "trust_score": round(final_score, 3),
            "decision": decision,
            "confidence": round(avg_confidence, 3),
            "adversarial_impact": round(penalty, 3)
        }
