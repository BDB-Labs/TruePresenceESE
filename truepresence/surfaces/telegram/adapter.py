from __future__ import annotations

from typing import Any, Dict, Optional

from truepresence.adapters.telegram import TelegramAdapter as LegacyTelegramAdapter
from truepresence.decision.decision_object import DecisionObject
from truepresence.decision.engine import DecisionResult, TruePresenceDecisionEngine


class TelegramGuardAdapter:
    def __init__(
        self,
        decision_engine: TruePresenceDecisionEngine,
        response_adapter: Optional[LegacyTelegramAdapter] = None,
    ):
        self.decision_engine = decision_engine
        self.response_adapter = response_adapter or LegacyTelegramAdapter()

    def evaluate_event(
        self,
        *,
        session_id: str,
        tenant_id: str,
        event: dict,
        context: dict | None = None,
    ) -> DecisionResult:
        ctx = dict(context or {})
        session = dict(ctx.get("session", {}))
        session.setdefault("session_id", session_id)
        session.setdefault("tenant_id", tenant_id)
        ctx["session"] = session

        return self.decision_engine.evaluate(
            surface="telegram",
            session_id=session_id,
            tenant_id=tenant_id,
            event=event,
            context=ctx,
            session=session,
        )

    def enforce(self, decision: DecisionObject) -> Dict[str, Any]:
        return self.response_adapter.build_response(
            {
                "state": decision.state,
                "decision": decision.recommended_enforcement,
                "confidence": decision.confidence,
                "human_probability": decision.human_probability,
                "reason_codes": list(decision.reason_codes),
                "risk_factors": list(decision.reason_codes),
            },
            tenant_id=decision.tenant_id,
        )


TelegramAdapter = LegacyTelegramAdapter
