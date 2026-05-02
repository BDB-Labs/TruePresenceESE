from __future__ import annotations

from typing import Any


class ESEEngine:
    def evaluate(self, evidence: dict[str, Any]) -> dict[str, Any]:
        risk = 0.2

        if evidence.get("paste_behavior"):
            risk += 0.25
        if float(evidence.get("typing_entropy", 0.5)) < 0.3:
            risk += 0.2
        if float(evidence.get("message_velocity", 0.0)) > 20:
            risk += 0.15
        if float(evidence.get("content_similarity", 0.0)) > 0.6:
            risk += 0.15

        risk_score = round(min(max(risk, 0.0), 1.0), 3)
        if risk_score >= 0.75:
            risk_level = "high"
            classification = "bot_like"
            decision = "block"
        elif risk_score >= 0.45:
            risk_level = "medium"
            classification = "needs_review"
            decision = "challenge"
        else:
            risk_level = "low"
            classification = "human_like"
            decision = "allow"

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "classification": classification,
            "decision": decision,
            "evidence": dict(evidence),
        }
