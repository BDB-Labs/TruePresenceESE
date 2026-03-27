from __future__ import annotations

import json
from pathlib import Path

import pytest

from ese.pipeline import (
    PROMPT_TRUNCATION_MARKER,
    PipelineError,
    _normalize_json_report,
    _role_context,
    _role_prompt,
    run_pipeline,
)


def _cfg() -> dict:
    return {
        "version": 1,
        "mode": "ensemble",
        "provider": {
            "name": "openai",
            "model": "gpt-5-mini",
            "api_key_env": "OPENAI_API_KEY",
        },
        "roles": {
            "architect": {},
            "implementer": {},
            "adversarial_reviewer": {},
        },
        "runtime": {
            "adapter": "dry-run",
        },
        "input": {
            "scope": "Harden the release workflow",
        },
    }


def _report_payload(**overrides) -> str:
    payload = {
        "summary": "Completed review.",
        "confidence": "MEDIUM",
        "assumptions": [],
        "unknowns": [],
        "findings": [],
        "artifacts": [],
        "next_steps": [],
        "code_suggestions": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_confidence_is_required() -> None:
    with pytest.raises(PipelineError) as exc:
        _normalize_json_report(
            role="architect",
            model="openai:gpt-5-mini",
            output=json.dumps(
                {
                    "summary": "Missing confidence.",
                    "assumptions": [],
                    "unknowns": [],
                    "findings": [],
                    "artifacts": [],
                    "next_steps": [],
                    "code_suggestions": [],
                },
            ),
        )

    assert "confidence" in str(exc.value)


def test_invalid_confidence_is_rejected() -> None:
    with pytest.raises(PipelineError) as exc:
        _normalize_json_report(
            role="architect",
            model="openai:gpt-5-mini",
            output=_report_payload(confidence="certain"),
        )

    assert "invalid confidence" in str(exc.value)


def test_assumptions_must_be_string_list() -> None:
    with pytest.raises(PipelineError) as exc:
        _normalize_json_report(
            role="architect",
            model="openai:gpt-5-mini",
            output=_report_payload(assumptions="not-a-list"),
        )

    assert "assumptions" in str(exc.value)


def test_unknowns_must_be_string_list() -> None:
    with pytest.raises(PipelineError) as exc:
        _normalize_json_report(
            role="architect",
            model="openai:gpt-5-mini",
            output=_report_payload(unknowns=[1]),
        )

    assert "unknowns" in str(exc.value)


def test_valid_json_report_with_new_fields_passes() -> None:
    report = _normalize_json_report(
        role="architect",
        model="openai:gpt-5-mini",
        output=_report_payload(
            confidence="high",
            assumptions=["The schema stays stable."],
            unknowns=["Production traffic shape is unknown."],
        ),
    )

    assert report["confidence"] == "HIGH"
    assert report["assumptions"] == ["The schema stays stable."]
    assert report["unknowns"] == ["Production traffic shape is unknown."]


def test_evidence_basis_is_preserved_when_present() -> None:
    report = _normalize_json_report(
        role="architect",
        model="openai:gpt-5-mini",
        output=_report_payload(evidence_basis=["Read pipeline_state.json", "Reviewed release checklist"]),
    )

    assert report["evidence_basis"] == ["Read pipeline_state.json", "Reviewed release checklist"]


def test_run_pipeline_writes_run_id_and_assurance_level(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    run_pipeline(_cfg(), artifacts_dir=str(artifacts_dir))

    state = json.loads((artifacts_dir / "pipeline_state.json").read_text(encoding="utf-8"))
    assert state["run_id"]
    assert state["assurance_level"] == "standard"
    assert state["state_contract_version"] == 2
    assert state["report_contract_version"] == 2


def test_rerun_writes_parent_run_id(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    run_pipeline(_cfg(), artifacts_dir=str(artifacts_dir))
    original_state = json.loads((artifacts_dir / "pipeline_state.json").read_text(encoding="utf-8"))

    run_pipeline(_cfg(), artifacts_dir=str(artifacts_dir), start_role="implementer")
    rerun_state = json.loads((artifacts_dir / "pipeline_state.json").read_text(encoding="utf-8"))

    assert rerun_state["parent_run_id"] == original_state["run_id"]
    assert rerun_state["start_role"] == "implementer"


def test_review_isolation_modes_change_prompt_and_context() -> None:
    outputs = {
        "architect": "Define the rollout plan.",
        "implementer": "Implemented the feature flag path.",
        "custom_previous": "Prior custom artifact.",
    }

    framed_context = _role_context("adversarial_reviewer", outputs, review_isolation="framed")
    assert framed_context == {
        "architect": "Define the rollout plan.",
        "implementer": "Implemented the feature flag path.",
    }
    framed_prompt = _role_prompt(
        role="adversarial_reviewer",
        scope="Review the rollout",
        outputs=outputs,
        enforce_json=True,
        review_isolation="framed",
    )
    assert "Architect Plan" in framed_prompt
    assert "Implementer Output" in framed_prompt

    scope_only_context = _role_context("adversarial_reviewer", outputs, review_isolation="scope_only")
    assert scope_only_context == {}
    scope_only_prompt = _role_prompt(
        role="adversarial_reviewer",
        scope="Review the rollout",
        outputs=outputs,
        enforce_json=True,
        review_isolation="scope_only",
    )
    assert "Architect Plan" not in scope_only_prompt
    assert "Implementer Output" not in scope_only_prompt

    fallback_context = _role_context(
        "custom_role",
        outputs,
        review_isolation="scope_and_implementation",
    )
    assert fallback_context == {"implementer": "Implemented the feature flag path.", "custom_previous": "Prior custom artifact."}
    fallback_prompt = _role_prompt(
        role="custom_role",
        scope="Review the rollout",
        outputs=outputs,
        enforce_json=True,
        review_isolation="scope_and_implementation",
    )
    assert "Architect Plan" not in fallback_prompt
    assert "Upstream Artifact (custom_previous)" in fallback_prompt


def test_prompt_truncation_marker_appears_for_large_upstream_context() -> None:
    huge_output = "A" * 20_000
    prompt = _role_prompt(
        role="adversarial_reviewer",
        scope="Review the implementation",
        outputs={"implementer": huge_output},
        enforce_json=True,
        review_isolation="scope_and_implementation",
    )

    assert PROMPT_TRUNCATION_MARKER in prompt
