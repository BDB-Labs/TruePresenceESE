from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from truepresence.api.server import app as rest_app


def _client() -> TestClient:
    app = FastAPI()
    app.mount("/api", rest_app)
    return TestClient(app)


def _valid_payload() -> dict:
    return {
        "session_id": "sdk-api-session",
        "tenant_id": "default",
        "feature_packet": {
            "surface": "web",
            "site_id": "site_123",
            "typing": {
                "mean_inter_key_interval_ms": 180,
                "inter_key_interval_stddev_ms": 64,
                "characters_per_minute": 205,
                "correction_count": 2,
                "correction_rate": 0.04,
                "paste_count": 0,
                "focus_to_first_input_ms": 410,
                "prompt_render_to_first_input_ms": 1050,
            },
            "challenge": {
                "response_latency_ms": 3400,
                "expected_reading_time_ms": 1500,
            },
            "pointer": {
                "pointer_entropy": 0.7,
                "click_hesitation_ms": 220,
                "scroll_cadence_score": 0.62,
            },
        },
    }


def test_evaluate_interaction_accepts_valid_derived_feature_payload() -> None:
    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=_valid_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["human_presence_likelihood"] > payload["automation_likelihood"]
    assert payload["enforcement_mode"] == "observe"


def test_evaluate_interaction_rejects_raw_content_payload() -> None:
    payload = _valid_payload()
    payload["feature_packet"]["typing"]["typed_text"] = "secret private phrase"

    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=payload)

    assert response.status_code == 422
    assert "typed_text" in response.text
    assert "secret private phrase" not in response.text


def test_evaluate_interaction_response_includes_required_fields() -> None:
    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=_valid_payload())

    assert response.status_code == 200
    payload = response.json()
    assert {
        "human_presence_likelihood",
        "automation_likelihood",
        "agentic_control_likelihood",
        "confidence",
        "reason_codes",
        "evidence_packet_id",
        "recommended_action",
        "enforcement_mode",
    }.issubset(payload)


def test_evaluate_interaction_response_does_not_include_raw_content() -> None:
    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=_valid_payload())

    assert response.status_code == 200
    body = json.dumps(response.json())
    assert "typed_text" not in body
    assert "raw_text" not in body
    assert "value" not in body
