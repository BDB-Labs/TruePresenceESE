from __future__ import annotations

from fastapi.testclient import TestClient

from truepresence.api.server import app


def test_create_session_accepts_json_body_assurance_level() -> None:
    client = TestClient(app)

    response = client.post("/session/create", json={"assurance_level": "A4"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["assurance_level"] == "A4"


def test_create_session_query_assurance_level_still_supported() -> None:
    client = TestClient(app)

    response = client.post("/session/create?assurance_level=A2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["assurance_level"] == "A2"


def test_evaluate_accepts_engine_reasoning_trace_contract() -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/evaluate",
        json={
            "mode": "sdk",
            "session_id": "api-contract-session",
            "event": {
                "event_type": "message",
                "timestamp": 1710000000.0,
                "payload": {"text": "hello"},
                "features": {},
            },
            "context": {"platform": "web_guard", "tenant_id": "default"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "api-contract-session"
    assert isinstance(payload["reasoning_trace"]["reason_codes"], list)
