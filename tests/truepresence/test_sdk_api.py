"""
Tests for the TruePresence SDK evaluation API endpoint.

Covers standard contracts plus renamed-raw-content rejection at the HTTP layer.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from truepresence.api.server import app as rest_app
from truepresence.api.server import get_dashboard_user
from truepresence.evidence.sdk_artifacts import sdk_evidence_store

pytestmark = pytest.mark.sdk


@pytest.fixture(autouse=True)
def _clear_dashboard_auth_override() -> None:
    rest_app.dependency_overrides.pop(get_dashboard_user, None)
    yield
    rest_app.dependency_overrides.pop(get_dashboard_user, None)


def _client(current_user: dict | None = None) -> TestClient:
    rest_app.dependency_overrides.pop(get_dashboard_user, None)
    if current_user is not None:
        rest_app.dependency_overrides[get_dashboard_user] = lambda: current_user
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


def _dashboard_user(
    *,
    tenant_id: str = "default",
    role: str = "reviewer",
) -> dict:
    return {
        "id": 1,
        "email": f"{role}@example.test",
        "name": role,
        "role": role,
        "tenant_id": tenant_id,
        "active": True,
    }


def _payload_for_tenant(tenant_id: str, session_id: str) -> dict:
    payload = deepcopy(_valid_payload())
    payload["session_id"] = session_id
    payload["tenant_id"] = tenant_id
    return payload


def _create_sdk_evidence(client: TestClient, *, tenant_id: str, session_id: str) -> str:
    response = client.post(
        "/api/v1/truepresence/evaluate-interaction",
        json=_payload_for_tenant(tenant_id, session_id),
    )
    assert response.status_code == 200
    return response.json()["evidence_packet_id"]


# ---------------------------------------------------------------------------
# Original contract tests
# ---------------------------------------------------------------------------

def test_evaluate_interaction_accepts_valid_derived_feature_payload() -> None:
    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=_valid_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["human_presence_likelihood"] > payload["automation_likelihood"]
    assert payload["enforcement_mode"] == "observe"


def test_evaluate_interaction_accepts_browser_sdk_aggregate_metadata() -> None:
    payload = _valid_payload()
    payload["feature_packet"]["typing"]["last_input_to_submit_ms"] = 140
    payload["feature_packet"]["typing"]["typing_duration_ms"] = 2100
    payload["feature_packet"]["challenge"].update({
        "challenge_type": "typing_cadence",
        "correction_count": 1,
        "paste_count": 0,
        "typing_duration_ms": 1700,
        "submitted_exactly": True,
    })
    payload["feature_packet"]["metadata"] = {
        "mode": "privacy_preserving",
        "sdk_version": "0.2.0",
        "tracked_field_count": 1,
        "typing_summary": {
            "delete_key_count": 1,
            "input_event_count": 8,
            "last_input_to_submit_ms": 140,
            "max_inter_key_interval_ms": 260,
            "min_inter_key_interval_ms": 75,
            "tracked_field_count": 1,
        },
    }

    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=payload)

    assert response.status_code == 200


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


def test_dashboard_evidence_cards_endpoint_returns_minimized_sdk_fields() -> None:
    sdk_evidence_store.clear()
    client = _client()
    evaluation = client.post("/api/v1/truepresence/evaluate-interaction", json=_valid_payload())
    assert evaluation.status_code == 200

    client = _client(_dashboard_user(tenant_id="default"))
    response = client.get("/api/v1/truepresence/evidence/cards?tenant=default")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    card = payload["evidence_cards"][0]
    assert {
        "surface",
        "risk_level",
        "human_presence_likelihood",
        "automation_likelihood",
        "agentic_control_likelihood",
        "confidence",
        "reason_codes",
        "evidence_packet_id",
        "decision_id",
        "recommended_action",
        "timestamp",
    }.issubset(card)
    assert card["surface"] == "web"
    assert card["evidence_packet_id"] == evaluation.json()["evidence_packet_id"]

    body = json.dumps(payload)
    assert "feature_summaries" not in body
    assert "detector_signals" not in body
    assert "typed_text" not in body
    assert "message_text" not in body
    assert "caption" not in body
    assert "file_url" not in body


def test_dashboard_evidence_cards_reject_unauthenticated_requests() -> None:
    response = _client().get("/api/v1/truepresence/evidence/cards")

    assert response.status_code in {401, 403}


def test_dashboard_evidence_artifact_rejects_unauthenticated_requests() -> None:
    response = _client().get("/api/v1/truepresence/evidence/ep_unknown")

    assert response.status_code in {401, 403}


def test_dashboard_tenant_user_cannot_list_other_tenant_evidence() -> None:
    sdk_evidence_store.clear()
    public_client = _client()
    _create_sdk_evidence(public_client, tenant_id="tenant-b", session_id="tenant-b-session")

    response = _client(_dashboard_user(tenant_id="tenant-a")).get(
        "/api/v1/truepresence/evidence/cards?tenant=tenant-b"
    )

    assert response.status_code == 403


def test_dashboard_tenant_user_cannot_retrieve_other_tenant_evidence_without_existence_leak() -> None:
    sdk_evidence_store.clear()
    public_client = _client()
    evidence_id = _create_sdk_evidence(
        public_client,
        tenant_id="tenant-b",
        session_id="tenant-b-session",
    )
    tenant_a_client = _client(_dashboard_user(tenant_id="tenant-a"))

    forbidden = tenant_a_client.get(f"/api/v1/truepresence/evidence/{evidence_id}")
    missing = tenant_a_client.get("/api/v1/truepresence/evidence/ep_missing")

    assert forbidden.status_code == 404
    assert missing.status_code == 404
    assert forbidden.json() == missing.json()


def test_dashboard_tenant_user_can_access_own_evidence() -> None:
    sdk_evidence_store.clear()
    public_client = _client()
    own_evidence_id = _create_sdk_evidence(
        public_client,
        tenant_id="tenant-a",
        session_id="tenant-a-session",
    )
    other_evidence_id = _create_sdk_evidence(
        public_client,
        tenant_id="tenant-b",
        session_id="tenant-b-session",
    )

    tenant_a_client = _client(_dashboard_user(tenant_id="tenant-a"))
    cards_response = tenant_a_client.get("/api/v1/truepresence/evidence/cards")
    artifact_response = tenant_a_client.get(f"/api/v1/truepresence/evidence/{own_evidence_id}")

    assert cards_response.status_code == 200
    cards_payload = cards_response.json()
    assert cards_payload["tenant_id"] == "tenant-a"
    returned_ids = {card["evidence_packet_id"] for card in cards_payload["evidence_cards"]}
    assert own_evidence_id in returned_ids
    assert other_evidence_id not in returned_ids

    assert artifact_response.status_code == 200
    artifact = artifact_response.json()
    assert artifact["tenant_id"] == "tenant-a"
    assert artifact["evidence_packet_id"] == own_evidence_id
    artifact_body = json.dumps(artifact)
    assert "typed_text" not in artifact_body
    assert "message_text" not in artifact_body
    assert "caption" not in artifact_body
    assert "file_url" not in artifact_body


def test_dashboard_super_admin_can_access_tenant_evidence() -> None:
    sdk_evidence_store.clear()
    public_client = _client()
    evidence_id = _create_sdk_evidence(
        public_client,
        tenant_id="tenant-b",
        session_id="tenant-b-session",
    )
    admin_client = _client(_dashboard_user(tenant_id="admin-tenant", role="super_admin"))

    cards_response = admin_client.get("/api/v1/truepresence/evidence/cards?tenant=tenant-b")
    artifact_response = admin_client.get(f"/api/v1/truepresence/evidence/{evidence_id}")

    assert cards_response.status_code == 200
    assert cards_response.json()["tenant_id"] == "tenant-b"
    assert cards_response.json()["evidence_cards"][0]["evidence_packet_id"] == evidence_id
    assert artifact_response.status_code == 200
    assert artifact_response.json()["tenant_id"] == "tenant-b"


# ---------------------------------------------------------------------------
# Renamed raw-content field rejection at the API layer
# ---------------------------------------------------------------------------

def _payload_with_typing_field(key: str, value: object) -> dict:
    import copy
    payload = copy.deepcopy(_valid_payload())
    payload["feature_packet"]["typing"][key] = value
    return payload


def _payload_with_challenge_field(key: str, value: object) -> dict:
    import copy
    payload = copy.deepcopy(_valid_payload())
    payload["feature_packet"]["challenge"][key] = value
    return payload


def test_api_rejects_answer_in_typing() -> None:
    response = _client().post(
        "/api/v1/truepresence/evaluate-interaction",
        json=_payload_with_typing_field("answer", "the user answer"),
    )
    assert response.status_code == 422
    assert "answer" in response.text
    assert "the user answer" not in response.text


def test_api_rejects_response_in_typing() -> None:
    response = _client().post(
        "/api/v1/truepresence/evaluate-interaction",
        json=_payload_with_typing_field("response", "user response text"),
    )
    assert response.status_code == 422
    assert "response" in response.text
    assert "user response text" not in response.text


def test_api_rejects_comment_in_typing() -> None:
    response = _client().post(
        "/api/v1/truepresence/evaluate-interaction",
        json=_payload_with_typing_field("comment", "a comment"),
    )
    assert response.status_code == 422
    assert "comment" in response.text


def test_api_rejects_description_in_typing() -> None:
    response = _client().post(
        "/api/v1/truepresence/evaluate-interaction",
        json=_payload_with_typing_field("description", "a description"),
    )
    assert response.status_code == 422
    assert "description" in response.text


def test_api_rejects_message_in_challenge() -> None:
    response = _client().post(
        "/api/v1/truepresence/evaluate-interaction",
        json=_payload_with_challenge_field("message", "raw user message"),
    )
    assert response.status_code == 422
    assert "message" in response.text
    assert "raw user message" not in response.text


def test_api_rejects_content_in_typing() -> None:
    response = _client().post(
        "/api/v1/truepresence/evaluate-interaction",
        json=_payload_with_typing_field("content", "user content here"),
    )
    assert response.status_code == 422
    assert "content" in response.text


@pytest.mark.parametrize("field_name,field_value", [
    ("caption", "private image caption"),
    ("media_url", "https://private.example/media.png"),
    ("file_url", "https://private.example/file.pdf"),
])
def test_api_rejects_media_like_raw_fields_before_evidence_artifact(
    field_name: str,
    field_value: str,
) -> None:
    sdk_evidence_store.clear()
    payload = _valid_payload()
    payload["feature_packet"]["metadata"] = {field_name: field_value}

    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=payload)

    assert response.status_code == 422
    assert field_name in response.text
    assert field_value not in response.text
    assert sdk_evidence_store.count() == 0


def test_api_rejects_unknown_section_field_in_typing() -> None:
    """A field not on the typing allowlist is rejected even if it sounds benign."""
    response = _client().post(
        "/api/v1/truepresence/evaluate-interaction",
        json=_payload_with_typing_field("raw_event_log", [1, 2, 3]),
    )
    assert response.status_code == 422
    assert "raw_event_log" in response.text


def test_api_rejects_unknown_section_field_in_pointer() -> None:
    import copy
    payload = copy.deepcopy(_valid_payload())
    payload["feature_packet"]["pointer"]["raw_coordinates"] = [[0, 0], [1, 1]]
    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=payload)
    assert response.status_code == 422
    assert "raw_coordinates" in response.text


def test_api_rejects_unknown_top_level_field_without_echoing_value() -> None:
    payload = _valid_payload()
    payload["client_trace_id"] = "trace value should not be echoed"

    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=payload)

    assert response.status_code == 422
    assert "client_trace_id" in response.text
    assert "trace value should not be echoed" not in response.text


def test_api_rejects_legacy_flow_id_feature_packet_field() -> None:
    payload = _valid_payload()
    payload["feature_packet"]["flow_id"] = "signup-flow"

    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=payload)

    assert response.status_code == 422
    assert "flow_id" in response.text


def test_api_rejects_arbitrary_metadata_field_without_echoing_value() -> None:
    payload = _valid_payload()
    payload["feature_packet"]["metadata"] = {"arbitrary_note": "private note"}

    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=payload)

    assert response.status_code == 422
    assert "arbitrary_note" in response.text
    assert "private note" not in response.text


def test_api_validation_errors_do_not_echo_bad_field_values() -> None:
    payload = _valid_payload()
    payload["feature_packet"]["typing"]["mean_inter_key_interval_ms"] = "private text value"

    response = _client().post("/api/v1/truepresence/evaluate-interaction", json=payload)

    assert response.status_code == 422
    assert "mean_inter_key_interval_ms" in response.text
    assert "private text value" not in response.text
