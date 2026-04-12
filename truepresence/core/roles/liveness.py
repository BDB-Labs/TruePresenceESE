from typing import Dict, Any

class LivenessAnalyst:
    def analyze(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        score = evidence["signals"].get("liveness", 0.0)
        return {
            "role": "liveness_analyst",
            "confidence": score,
            "finding": "presence_confirmed" if score > 0.6 else "presence_uncertain",
            "impact": "positive" if score > 0.6 else "neutral"
        }
