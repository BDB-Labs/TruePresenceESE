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
