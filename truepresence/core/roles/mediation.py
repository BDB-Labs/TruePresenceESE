from typing import Dict, Any

class MediationAnalyst:
    def analyze(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        mediation = evidence["signals"].get("ai_mediation", 0.0)
        return {
            "role": "mediation_analyst",
            "confidence": 1.0 - mediation,
            "finding": "ai_mediated" if mediation > 0.4 else "human_direct",
            "impact": "negative" if mediation > 0.4 else "neutral"
        }
