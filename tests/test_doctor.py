from __future__ import annotations

import yaml

from ese.doctor import evaluate_doctor, run_doctor


def _write_cfg(path, cfg: dict) -> str:
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return str(path)


def _base_cfg() -> dict:
    return {
        "version": 1,
        "mode": "ensemble",
        "provider": {
            "name": "openai",
            "model": "gpt-5-mini",
            "api_key_env": "OPENAI_API_KEY",
        },
        "roles": {
            "architect": {"model": "gpt-5"},
            "implementer": {"model": "gpt-5-mini"},
        },
        "constraints": {
            "disallow_same_model_pairs": [["architect", "implementer"]],
        },
        "runtime": {
            "adapter": "dry-run",
        },
        "input": {
            "scope": "Review release readiness for a service hardening change",
        },
    }


def test_doctor_detects_shared_model_violation(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["roles"]["implementer"]["model"] = "gpt-5"
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, role_models = run_doctor(path)

    assert not ok
    assert "architect and implementer share model openai:gpt-5" in violations
    assert role_models["architect"] == "openai:gpt-5"


def test_doctor_uses_dynamic_role_list(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["roles"] = {
        "architect": {"model": "gpt-5"},
        "documentation_writer": {"model": "gpt-5-mini"},
    }
    cfg["constraints"]["disallow_same_model_pairs"] = [["architect", "documentation_writer"]]
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, role_models = run_doctor(path)

    assert ok
    assert violations == []
    assert set(role_models.keys()) == {"architect", "documentation_writer"}


def test_doctor_reports_config_validation_error(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["version"] = 9
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, role_models = run_doctor(path)

    assert not ok
    assert role_models == {}
    assert len(violations) == 1
    assert "unsupported version 9; expected 1" in violations[0]


def test_doctor_fails_when_scope_is_missing(tmp_path) -> None:
    cfg = _base_cfg()
    cfg.pop("input", None)
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, role_models = run_doctor(path)

    assert not ok
    assert "No project scope supplied. Set input.scope in the config or pass --scope." in violations
    assert set(role_models.keys()) == {"architect", "implementer"}


def test_doctor_enforces_baseline_architect_implementer_separation_without_explicit_constraints(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["constraints"] = {}
    cfg["roles"]["implementer"]["model"] = "gpt-5"
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, _role_models = run_doctor(path)

    assert not ok
    assert "architect and implementer share model openai:gpt-5" in violations


def test_doctor_skips_missing_roles_in_disallow_lists_safely() -> None:
    cfg = _base_cfg()
    cfg["constraints"]["disallow_same_model_pairs"] = [["architect", "missing_role"]]

    ok, violations, role_models = evaluate_doctor(cfg)

    assert ok
    assert violations == []
    assert role_models["architect"] == "openai:gpt-5"
    assert role_models["missing_role"] == "openai:gpt-5-mini"


def test_doctor_returns_solo_mode_warning(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["mode"] = "solo"
    cfg["constraints"] = {}
    cfg["roles"]["implementer"]["model"] = "gpt-5"
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, _role_models = run_doctor(path)

    assert ok
    assert violations == ["SOLO MODE: degraded independence; lower assurance and higher self-confirmation risk."]


def test_doctor_enforces_minimum_distinct_models(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["roles"]["security_auditor"] = {"model": "gpt-5-mini"}
    cfg["constraints"]["minimum_distinct_models"] = 3
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, _role_models = run_doctor(path)

    assert not ok
    assert "Ensemble mode requires at least 3 distinct role models, found 2" in violations


def test_doctor_enforces_disallow_same_provider_pairs(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["roles"]["security_auditor"] = {"provider": "openrouter", "model": "openai/gpt-5"}
    cfg["roles"]["implementer"] = {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"}
    cfg["constraints"]["disallow_same_provider_pairs"] = [["implementer", "security_auditor"]]
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, _role_models = run_doctor(path)

    assert not ok
    assert "implementer and security_auditor share provider openrouter" in violations


def test_doctor_enforces_require_json_for_roles(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["output"] = {"artifacts_dir": "artifacts", "enforce_json": False}
    cfg["gating"] = {"fail_on_high": False}
    cfg["constraints"]["require_json_for_roles"] = ["architect"]
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, _role_models = run_doctor(path)

    assert not ok
    assert "constraints.require_json_for_roles requires output.enforce_json=true" in violations[0]
