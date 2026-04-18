from typing import Any, Dict


class RelayAnalyst:
    def analyze(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        risk = evidence["signals"].get("relay_risk", 0.0)
        return {
            "role": "relay_analyst",
            "confidence": 1.0 - risk,
            "finding": "relay_detected" if risk > 0.6 else "relay_unlikely",
            "impact": "negative" if risk > 0.6 else "neutral"
        }
