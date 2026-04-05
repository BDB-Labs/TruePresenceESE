from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from ese.config_packs import ConfigPackDefinition, PackRoleDefinition
from ese.init_wizard import (
    LIVE_EXECUTION_MODE,
    _apply_simple_mode_model_diversity,
    _ensemble_constraints,
    _provider_default_from_env,
    _select_execution_mode,
    run_wizard,
)


class _FakePrompt:
    def __init__(self, answer) -> None:  # noqa: ANN001
        self._answer = answer

    def ask(self):  # noqa: ANN201
        return self._answer


def _patch_questionary(monkeypatch, *, selects, texts, confirms, checkboxes=None, packs=None) -> None:
    select_answers = iter(selects)
    text_answers = iter(texts)
    confirm_answers = iter(confirms)
    checkbox_answers = iter(checkboxes or [])

    monkeypatch.setattr("ese.init_wizard.questionary.select", lambda *args, **kwargs: _FakePrompt(next(select_answers)))
    monkeypatch.setattr("ese.init_wizard.questionary.text", lambda *args, **kwargs: _FakePrompt(next(text_answers)))
    monkeypatch.setattr("ese.init_wizard.questionary.confirm", lambda *args, **kwargs: _FakePrompt(next(confirm_answers)))
    monkeypatch.setattr("ese.init_wizard.questionary.checkbox", lambda *args, **kwargs: _FakePrompt(next(checkbox_answers)))
    monkeypatch.setattr("ese.init_wizard.questionary.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("ese.init_wizard.list_config_packs", lambda: list(packs or []))


def test_ensemble_constraints_filters_to_selected_roles() -> None:
    constraints = _ensemble_constraints(["architect", "implementer", "release_manager"])

    assert constraints["disallow_same_model_pairs"] == [
        ["architect", "implementer"],
        ["implementer", "release_manager"],
    ]


def test_simple_mode_model_diversity_overrides_implementer() -> None:
    cfg: dict[str, Any] = {
        "provider": {"name": "openai", "model": "gpt-5"},
        "roles": {
            "architect": {},
            "implementer": {},
        },
    }

    _apply_simple_mode_model_diversity(
        cfg,
        provider="openai",
        selected_roles=["architect", "implementer"],
    )

    implementer_cfg = cfg["roles"]["implementer"]
    assert isinstance(implementer_cfg, dict)
    assert implementer_cfg["model"] != "gpt-5"


def test_provider_default_from_env_prefers_local_without_hosted_credentials(monkeypatch) -> None:
    for env_name in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "XAI_API_KEY",
        "OPENROUTER_API_KEY",
        "HF_TOKEN",
        "CUSTOM_API_KEY",
        "LOCAL_MODEL",
    ]:
        monkeypatch.delenv(env_name, raising=False)

    assert _provider_default_from_env() == "local"


def test_select_execution_mode_defaults_local_to_live(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def _fake_select(message, **kwargs):  # noqa: ANN001
        captured["default"] = kwargs["default"]
        return _FakePrompt(kwargs["default"])

    monkeypatch.setattr("ese.init_wizard.questionary.select", _fake_select)

    selected = _select_execution_mode("local", advanced=False)

    assert selected == LIVE_EXECUTION_MODE
    assert captured["default"] == LIVE_EXECUTION_MODE


def test_run_wizard_writes_scope_and_demo_config(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "ese.config.yaml"
    _patch_questionary(
        monkeypatch,
        selects=[
            "ensemble",
            "anthropic",
            "demo",
            "balanced",
            "recommended (claude-sonnet-4)",
        ],
        texts=[
            "Document the deployment workflow for the new auth system",
            "2",
            "workflow_architect",
            "Design the deployment workflow and produce the implementation plan and checklist.",
            "release_reviewer",
            "Review rollback evidence and release risks using the plan, checklist, and deployment docs.",
        ],
        confirms=[True, True, True],
    )

    written = run_wizard(str(config_path), advanced=False)

    assert written == str(config_path)
    cfg = cast(dict[str, Any], yaml.safe_load(config_path.read_text(encoding="utf-8")))
    assert cfg["input"]["scope"] == "Document the deployment workflow for the new auth system"
    assert cfg["runtime"]["adapter"] == "dry-run"
    assert cfg["install_profile"]["kind"] == "framework"
    assert cfg["role_order"] == ["workflow_architect", "release_reviewer"]
    assert "Primary responsibility:" in cfg["roles"]["workflow_architect"]["prompt"]


def test_run_wizard_rejects_invalid_custom_adapter_before_write(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "ese.config.yaml"
    _patch_questionary(
        monkeypatch,
        selects=[
            "ensemble",
            "openai",
            "custom_module",
            "fast",
            "recommended (gpt-5-mini)",
        ],
        texts=[
            "Ship a demo safely",
            "2",
            "delivery_planner",
            "Plan the delivery sequence and produce the rollout checklist and handoff notes.",
            "risk_reviewer",
            "Review rollout risks, rollback evidence, and release blockers using the checklist and notes.",
            "invalid-adapter",
        ],
        confirms=[False, True, True, False],
    )

    written = run_wizard(str(config_path), advanced=True)

    assert written is None
    assert not config_path.exists()


def test_run_wizard_advanced_supports_per_role_model_overrides(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "ese.config.yaml"
    _patch_questionary(
        monkeypatch,
        selects=[
            "ensemble",
            "openai",
            "demo",
            "fast",
            "recommended (gpt-5-mini)",
            "inherit global default (gpt-5-mini)",
            "choose another common model",
            "gpt-5",
        ],
        texts=[
            "Harden the release checklist for a staged rollout",
            "2",
            "design_critic",
            "Review the rollout design and produce implementation guidance with clear handoff boundaries.",
            "verification_lead",
            "Validate rollout risks and tests using the guidance, release notes, and deployment checklist.",
        ],
        confirms=[True, True, True, True],
    )

    written = run_wizard(str(config_path), advanced=True)

    assert written == str(config_path)
    cfg = cast(dict[str, Any], yaml.safe_load(config_path.read_text(encoding="utf-8")))
    assert cfg["provider"]["model"] == "gpt-5-mini"
    assert cfg["roles"]["design_critic"].get("model") is None
    assert cfg["roles"]["verification_lead"]["model"] == "gpt-5"
    assert cfg["install_profile"]["kind"] == "framework"


def test_run_wizard_pack_config_uses_fixed_pack_roles(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "ese.config.yaml"
    pack = ConfigPackDefinition(
        key="release-ops",
        title="Release Operations",
        summary="Reusable release-review pack",
        preset="strict",
        goal_profile="high-quality",
        roles=(
            PackRoleDefinition(
                key="release_planner",
                responsibility="Plan release sequencing.",
                prompt="Plan the release sequence and required checkpoints.",
            ),
            PackRoleDefinition(
                key="release_reviewer",
                responsibility="Review rollout and rollback readiness.",
                prompt="Review rollout and rollback readiness.",
            ),
        ),
    )
    monkeypatch.setattr(
        "ese.init_wizard.get_config_pack",
        lambda key: pack if key == pack.key else (_ for _ in ()).throw(KeyError(key)),
    )
    _patch_questionary(
        monkeypatch,
        selects=[
            "ensemble",
            "openai",
            "demo",
            "pack",
            "release-ops",
            "recommended (gpt-5)",
        ],
        texts=[
            "Review the production rollout plan before approval",
        ],
        confirms=[True, True, True],
        packs=[pack],
    )

    written = run_wizard(str(config_path), advanced=False)

    assert written == str(config_path)
    cfg = cast(dict[str, Any], yaml.safe_load(config_path.read_text(encoding="utf-8")))
    assert cfg["install_profile"]["kind"] == "pack"
    assert cfg["install_profile"]["pack"] == "release-ops"
    assert cfg["role_order"][0] == "release_planner"
    assert "release_reviewer" in cfg["roles"]
