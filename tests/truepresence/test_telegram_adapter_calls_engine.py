from dataclasses import dataclass

from truepresence.decision.decision_object import DecisionObject
from truepresence.decision.engine import DecisionResult
from truepresence.evidence.argument_graph import ArgumentGraph
from truepresence.evidence.packet import EvidencePacket
from truepresence.surfaces.telegram.adapter import TelegramGuardAdapter


@dataclass
class FakeEngine:
    last_call: dict | None = None

    def evaluate(self, **kwargs):
        self.last_call = kwargs
        decision = DecisionObject(
            decision_id="decision-1",
            session_id=kwargs["session_id"],
            tenant_id=kwargs["tenant_id"],
            surface=kwargs["surface"],
            state="ALLOW",
            recommended_enforcement="allow",
            confidence=0.8,
            risk_level="low",
        )
        packet = EvidencePacket(
            packet_id="packet-1",
            session_id=kwargs["session_id"],
            tenant_id=kwargs["tenant_id"],
            surface=kwargs["surface"],
            actor_id=None,
            received_at="2026-01-01T00:00:00+00:00",
            event_window_start=None,
            event_window_end=None,
        )
        return DecisionResult(
            decision=decision,
            evidence_packet=packet,
            argument_graph=ArgumentGraph(),
            decision_artifact={},
        )


def test_telegram_adapter_calls_canonical_engine() -> None:
    engine = FakeEngine()
    adapter = TelegramGuardAdapter(engine)

    result = adapter.evaluate_event(
        session_id="tg-session",
        tenant_id="tenant-1",
        event={"event_type": "message", "payload": {}},
        context={"session": {"session_id": "tg-session", "tenant_id": "tenant-1"}},
    )

    assert engine.last_call is not None
    assert engine.last_call["surface"] == "telegram"
    assert engine.last_call["session_id"] == "tg-session"
    assert engine.last_call["tenant_id"] == "tenant-1"
    assert result.decision.session_id == "tg-session"
