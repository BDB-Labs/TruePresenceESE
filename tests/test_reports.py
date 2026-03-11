from __future__ import annotations

import os
from pathlib import Path

from ese.reports import collect_run_report, list_recent_runs, load_artifact_view
from ese.pipeline import run_pipeline


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
            "scope": "Build a safer deployment checklist",
        },
    }


def test_collect_run_report_summarizes_pipeline_outputs(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    run_pipeline(_cfg(), artifacts_dir=str(artifacts_dir))

    report = collect_run_report(str(artifacts_dir))

    assert report["status"] == "completed"
    assert report["finding_count"] == 0
    assert len(report["roles"]) == 3
    assert report["roles"][0]["role"] == "architect"
    assert report["config_snapshot"] == str(artifacts_dir / "ese_config.snapshot.yaml")
    assert report["documents"][0]["key"] == "summary"
    assert report["updated_at"]


def test_list_recent_runs_discovers_sibling_runs(tmp_path: Path) -> None:
    run_one = tmp_path / "runs" / "20260308-task-run"
    run_two = tmp_path / "runs" / "20260309-pr-review"
    run_pipeline(_cfg(), artifacts_dir=str(run_one))
    run_pipeline(_cfg(), artifacts_dir=str(run_two))

    os.utime(run_one / "pipeline_state.json", (1, 1))
    os.utime(run_two / "pipeline_state.json", (2, 2))

    runs = list_recent_runs(str(run_one))

    assert [item["artifacts_dir"] for item in runs] == [str(run_two), str(run_one)]
    assert runs[0]["status"] == "completed"
    assert runs[0]["role_count"] == 3


def test_load_artifact_view_supports_role_and_document_targets(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    run_pipeline(_cfg(), artifacts_dir=str(artifacts_dir))

    role_view = load_artifact_view(str(artifacts_dir), role="architect")
    summary_view = load_artifact_view(str(artifacts_dir), document="summary")

    assert role_view["kind"] == "role"
    assert role_view["key"] == "architect"
    assert "summary" in role_view["content"]
    assert summary_view["kind"] == "document"
    assert summary_view["key"] == "summary"
    assert "# ESE Summary" in summary_view["content"]
