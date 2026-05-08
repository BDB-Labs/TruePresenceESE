from __future__ import annotations

import copy
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from truepresence.api.server import app as rest_app
from truepresence.api.server import get_dashboard_user
from truepresence.evidence.sdk_artifacts import (
    SdkEvidenceArtifact,
    SqlSdkEvidenceArtifactStore,
    sdk_evidence_store,
)

pytestmark = pytest.mark.sdk


@pytest.fixture(autouse=True)
def _clear_dashboard_auth_override() -> None:
    rest_app.dependency_overrides.pop(get_dashboard_user, None)
    yield
    rest_app.dependency_overrides.pop(get_dashboard_user, None)


def _dashboard_user(
    *,
    tenant_id: str = "default",
    role: str = "super_admin",
) -> dict:
    return {
        "id": 1,
        "email": f"{role}@example.test",
        "name": role,
        "role": role,
        "tenant_id": tenant_id,
        "active": True,
    }


def _client(current_user: dict | None = None) -> TestClient:
    rest_app.dependency_overrides.pop(get_dashboard_user, None)
    if current_user is not None:
        rest_app.dependency_overrides[get_dashboard_user] = lambda: current_user
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

    client = _client(_dashboard_user())
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
    client = _client(_dashboard_user())
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
    client = _client(_dashboard_user())
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
    response = _client(_dashboard_user()).get("/api/v1/truepresence/evidence/ep_missing")

    assert response.status_code == 404


@contextmanager
def _sqlite_connection(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _sqlite_store(db_path: Path) -> SqlSdkEvidenceArtifactStore:
    return SqlSdkEvidenceArtifactStore(lambda: _sqlite_connection(db_path), dialect="sqlite")


def _artifact(
    evidence_packet_id: str,
    *,
    tenant_id: str = "default",
    session_id: str = "session-1",
    created_at: str = "2026-05-08T00:00:00+00:00",
) -> SdkEvidenceArtifact:
    return SdkEvidenceArtifact(
        evidence_packet_id=evidence_packet_id,
        session_id=session_id,
        tenant_id=tenant_id,
        surface="web",
        created_at=created_at,
        feature_summaries={
            "typing": {
                "characters_per_minute": 210,
                "mean_inter_key_interval_ms": 145,
            },
            "pointer": {
                "pointer_entropy": 0.71,
                "click_count": 2,
            },
        },
        detector_signals=[
            {
                "reason_code": "human_plausible_typing",
                "confidence": 0.72,
                "contribution_target": "automation",
            }
        ],
        reason_codes=["human_plausible_typing"],
        likelihoods={
            "human_presence_likelihood": 0.74,
            "automation_likelihood": 0.18,
            "agentic_control_likelihood": 0.1,
        },
        confidence=0.69,
        recommended_action="observe",
        scoring_metadata={
            "model": "deterministic_probabilistic_v1",
            "aggregation": "category_aware_product_of_complements",
        },
    )


def test_sql_store_persists_and_retrieves_artifact(tmp_path: Path) -> None:
    db_path = tmp_path / "sdk-evidence.sqlite"
    store = _sqlite_store(db_path)
    store.initialize_schema()
    artifact = _artifact("ep_sql_1", tenant_id="tenant-a", session_id="session-a")

    store.put(artifact)
    retrieved = store.get("ep_sql_1")

    assert retrieved == artifact


def test_sql_store_lists_recent_artifacts_with_tenant_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "sdk-evidence.sqlite"
    store = _sqlite_store(db_path)
    store.initialize_schema()
    store.put(_artifact("ep_old", tenant_id="tenant-a", created_at="2026-05-08T00:00:00+00:00"))
    store.put(_artifact("ep_new", tenant_id="tenant-a", created_at="2026-05-08T00:02:00+00:00"))
    store.put(_artifact("ep_other", tenant_id="tenant-b", created_at="2026-05-08T00:03:00+00:00"))

    tenant_a = store.list_recent(tenant_id="tenant-a", limit=10)
    all_recent = store.list_recent(limit=2)

    assert [artifact.evidence_packet_id for artifact in tenant_a] == ["ep_new", "ep_old"]
    assert [artifact.evidence_packet_id for artifact in all_recent] == ["ep_other", "ep_new"]


def test_sql_store_retrieves_after_store_reinitialization(tmp_path: Path) -> None:
    db_path = tmp_path / "sdk-evidence.sqlite"
    first_store = _sqlite_store(db_path)
    first_store.initialize_schema()
    first_store.put(_artifact("ep_restart", tenant_id="tenant-restart"))

    restarted_store = _sqlite_store(db_path)
    retrieved = restarted_store.get("ep_restart")

    assert retrieved is not None
    assert retrieved.evidence_packet_id == "ep_restart"
    assert retrieved.tenant_id == "tenant-restart"


def test_sql_store_rejects_raw_content_artifact(tmp_path: Path) -> None:
    db_path = tmp_path / "sdk-evidence.sqlite"
    store = _sqlite_store(db_path)
    store.initialize_schema()
    artifact = _artifact("ep_unsafe")
    artifact.feature_summaries["typing"]["typed_text"] = "SECRET RAW CONTENT"

    with pytest.raises(ValueError) as excinfo:
        store.put(artifact)

    assert "typed_text" in str(excinfo.value)
    assert "SECRET RAW CONTENT" not in str(excinfo.value)
    assert store.get("ep_unsafe") is None
