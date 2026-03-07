from __future__ import annotations

from ese.templates import build_task_config


def test_build_task_config_uses_template_defaults() -> None:
    cfg = build_task_config(
        scope="Prepare a safer staged rollout",
        template_key="release-readiness",
        provider="openai",
        execution_mode="demo",
        artifacts_dir="custom-artifacts",
    )

    assert cfg["runtime"]["adapter"] == "dry-run"
    assert cfg["output"]["artifacts_dir"] == "custom-artifacts"
    assert "release_manager" in cfg["roles"]
    assert cfg["gating"]["fail_on_high"] is True


def test_build_task_config_supports_local_live_runs() -> None:
    cfg = build_task_config(
        scope="Review a local-only codegen workflow",
        template_key="feature-delivery",
        provider="local",
        execution_mode="auto",
        artifacts_dir="artifacts-local",
    )

    assert cfg["runtime"]["adapter"] == "local"
    assert cfg["runtime"]["local"]["base_url"] == "http://localhost:11434/v1"
