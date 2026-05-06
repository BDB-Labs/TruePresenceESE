from __future__ import annotations

import copy
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from truepresence.api.server import app as rest_app
from truepresence.evidence.sdk_artifacts import sdk_evidence_store


def _client() -> TestClient:
    app = FastAPI()
    app.mount("/api", rest_app)
    return TestClient(app)


def _payload() -> dict:
    return {
        "session_id": "sdk-evidence-session",
        "tenant_id": "default",
        "feature_packet": {
            "surface": "web",
            "site_id": "site_123",
            "typing": {
                "mean_inter_key_interval_ms": 12,
                "inter_key_interval_stddev_ms": 1,
                "characters_per_minute": 920,
                "correction_count": 0,
                "correction_rate": 0,
                "paste_count": 1,
                "focus_to_first_input_ms": 12,
                "prompt_render_to_first_input_ms": 24,
                "typing_duration_ms": 80,
                "last_input_to_submit_ms": 15,
            },
            "challenge": {
                "challenge_type": "typing_cadence",
                "response_latency_ms": 150,
                "expected_reading_time_ms": 1800,
                "prompt_render_to_first_input_ms": 24,
                "correction_count": 0,
                "paste_count": 1,
                "typing_duration_ms": 80,
                "submitted_exactly": True,
            },
            "pointer": {
                "pointer_entropy": 0.04,
                "pointer_movement_count": 1,
                "click_count": 1,
                "click_hesitation_ms": 0,
                "scroll_cadence_score": 0.02,
            },
            "agentic": {
                "action_burst_count": 4,
                "mean_burst_interval_ms": 2600,
                "burst_interval_stddev_ms": 80,
                "idle_to_action_latency_ms": 2500,
                "exploratory_action_count": 0,
                "route_directness_score": 0.96,
                "large_instant_delta_count": 2,
                "submit_after_instant_input_ms": 180,
                "structured_retry_count": 2,
                "validation_repair_count": 3,
            },
        },
    }


def setup_function() -> None:
    sdk_evidence_store.clear()


def test_evidence_packet_id_maps_to_retrievable_artifact() -> None:
    client = _client()
    response = client.post("/api/v1/truepresence/evaluate-interaction", json=_payload())
    assert response.status_code == 200
    evidence_packet_id = response.json()["evidence_packet_id"]

    stored = sdk_evidence_store.get(evidence_packet_id)

    assert stored is not None
    assert stored.evidence_packet_id == evidence_packet_id
    assert stored.session_id == "sdk-evidence-session"
    assert stored.tenant_id == "default"
    assert stored.surface == "web"


def test_artifact_can_be_retrieved_by_api() -> None:
    client = _client()
    response = client.post("/api/v1/truepresence/evaluate-interaction", json=_payload())
    evidence_packet_id = response.json()["evidence_packet_id"]

    retrieved = client.get(f"/api/v1/truepresence/evidence/{evidence_packet_id}")

    assert retrieved.status_code == 200
    artifact = retrieved.json()
    assert artifact["evidence_packet_id"] == evidence_packet_id
    assert artifact["feature_summaries"]["typing"]["characters_per_minute"] == 920
    assert "uniform_typing_cadence" in artifact["reason_codes"]
    assert artifact["likelihoods"]["automation_likelihood"] > 0
    assert artifact["confidence"] == response.json()["confidence"]
    assert artifact["recommended_action"] == response.json()["recommended_action"]
    assert artifact["scoring_metadata"]["model"] == "deterministic_probabilistic_v1"


def test_artifact_contains_derived_metrics_and_detector_signals_only() -> None:
    client = _client()
    response = client.post("/api/v1/truepresence/evaluate-interaction", json=_payload())
    evidence_packet_id = response.json()["evidence_packet_id"]
    artifact = client.get(f"/api/v1/truepresence/evidence/{evidence_packet_id}").json()

    assert artifact["feature_summaries"]["agentic"]["large_instant_delta_count"] == 2
    assert artifact["detector_signals"]
    assert all(
        signal["contribution_target"] in {"automation", "agentic_control"}
        for signal in artifact["detector_signals"]
    )
    assert "model_thinking_cadence" in artifact["reason_codes"]


def test_artifact_contains_no_raw_content() -> None:
    client = _client()
    response = client.post("/api/v1/truepresence/evaluate-interaction", json=_payload())
    evidence_packet_id = response.json()["evidence_packet_id"]
    artifact = client.get(f"/api/v1/truepresence/evidence/{evidence_packet_id}").json()
    serialized = json.dumps(artifact).lower()

    forbidden_fragments = [
        "typed_text",
        "key_values",
        "password",
        "payment",
        "private message",
        "raw_pointer_trail",
        "clientx",
        "media_preview",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in serialized


def test_unsafe_payload_rejected_before_evidence_storage() -> None:
    client = _client()
    payload = copy.deepcopy(_payload())
    payload["feature_packet"]["typing"]["typed_text"] = "SECRET RAW CONTENT"

    response = client.post("/api/v1/truepresence/evaluate-interaction", json=payload)

    assert response.status_code == 422
    assert "SECRET RAW CONTENT" not in response.text
    assert sdk_evidence_store.count() == 0


def test_unknown_evidence_artifact_returns_404() -> None:
    response = _client().get("/api/v1/truepresence/evidence/ep_missing")

    assert response.status_code == 404
