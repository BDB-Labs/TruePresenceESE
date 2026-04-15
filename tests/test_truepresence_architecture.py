from __future__ import annotations

from importlib import import_module
from pathlib import Path

import tomllib

from truepresence.adapters.telegram import TelegramAdapter
from truepresence.decision.decision_object import DecisionState
from truepresence.decision.engine import TruePresenceDecisionEngine


def test_truepresence_console_entrypoint_is_callable() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    script_target = pyproject["project"]["scripts"]["truepresence"]
    module_name, attr_name = script_target.split(":", 1)

    module = import_module(module_name)
    entrypoint = getattr(module, attr_name)

    assert callable(entrypoint)


def test_decision_engine_returns_contract_objects() -> None:
    engine = TruePresenceDecisionEngine()

    result = engine.evaluate(
        session_id="session-allow",
        surface="web_guard",
        session={"session_id": "session-allow", "mode": "sdk"},
        event={
            "session_id": "session-allow",
            "event_type": "key_timing",
            "timestamp": 123.0,
            "payload": {"response_time_ms": 900},
            "signals": {"liveness": 0.9, "relay_risk": 0.1, "ai_mediation": 0.1},
            "context": {"platform": "web_guard"},
        },
    )

    assert result.decision_object.state is DecisionState.ALLOW
    assert result.evidence_packet.surface == "web_guard"
    assert result.decision_artifact.argument_graph["claim_count"] >= 1

    response = result.to_response()
    assert response["decision"] == "allow"
    assert response["state"] == "ALLOW"
    assert "decision_object" in response
    assert "evidence_packet" in response
    assert "decision_artifact" in response


def test_telegram_policy_violation_maps_to_ban() -> None:
    engine = TruePresenceDecisionEngine()
    adapter = TelegramAdapter()

    result = engine.evaluate(
        session_id="telegram-eject",
        surface="telegram",
        session={"session_id": "telegram-eject", "tenant_id": "default"},
        event={
            "session_id": "telegram-eject",
            "event_type": "message",
            "timestamp": 123.0,
            "payload": {"text": "buy drugs now"},
            "signals": {"illegal_indicators": 1.0},
            "context": {"platform": "telegram"},
            "threat_analysis": {"threats_detected": ["illegal_content"]},
        },
    )

    assert result.decision_object.state is DecisionState.EJECT

    action = adapter.build_response(result.to_response()["final"], tenant_id="default")
    assert action["action"] == "ban"
