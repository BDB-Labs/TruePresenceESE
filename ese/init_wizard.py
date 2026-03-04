"""Interactive wizard for creating ese.config.yaml."""

from __future__ import annotations

from typing import Any, Dict

import questionary

from ese.config import resolve_role_model, write_config

ROLE_DEFAULTS_BY_PRESET: Dict[str, Dict[str, Dict[str, Any]]] = {
    "fast": {
        "architect": {"temperature": 0.2},
        "implementer": {"temperature": 0.1},
        "adversarial_reviewer": {"temperature": 0.6},
        "security_auditor": {"temperature": 0.2},
        "test_generator": {"temperature": 0.2},
        "performance_analyst": {"temperature": 0.2},
    },
    "balanced": {
        "architect": {"temperature": 0.2},
        "implementer": {"temperature": 0.1},
        "adversarial_reviewer": {"temperature": 0.7},
        "security_auditor": {"temperature": 0.2},
        "test_generator": {"temperature": 0.2},
        "performance_analyst": {"temperature": 0.2},
    },
    "strict": {
        "architect": {"temperature": 0.1},
        "implementer": {"temperature": 0.05},
        "adversarial_reviewer": {"temperature": 0.6},
        "security_auditor": {"temperature": 0.1},
        "test_generator": {"temperature": 0.1},
        "performance_analyst": {"temperature": 0.1},
    },
    "paranoid": {
        "architect": {"temperature": 0.1},
        "implementer": {"temperature": 0.05},
        "adversarial_reviewer": {"temperature": 0.8},
        "security_auditor": {"temperature": 0.1},
        "test_generator": {"temperature": 0.1},
        "performance_analyst": {"temperature": 0.1},
    },
}


def _default_api_key_env(provider: str) -> str:
    if provider == "openai":
        return "OPENAI_API_KEY"
    if provider == "huggingface":
        return "HF_TOKEN"
    if provider == "local":
        return "LOCAL_MODEL"
    return "MODEL_TOKEN"


def run_wizard(config_path: str = "ese.config.yaml") -> str:
    mode = questionary.select("Setup mode:", choices=["ensemble", "solo"]).ask()
    provider = questionary.select(
        "Provider:", choices=["openai", "huggingface", "local"],
    ).ask()

    model = questionary.text("Default model name (e.g., gpt-5, meta-llama/…):").ask()
    preset = questionary.select(
        "Preset:", choices=["fast", "balanced", "strict", "paranoid"],
    ).ask()

    enforce_json = questionary.confirm(
        "Enforce JSON-only outputs for role reports?",
        default=True,
    ).ask()

    fail_on_high = questionary.confirm(
        "Fail pipeline on HIGH severity findings?",
        default=True,
    ).ask()

    cfg: Dict[str, Any] = {
        "version": 1,
        "mode": mode,
        "provider": {
            "name": provider,
            "model": model,
            "api_key_env": _default_api_key_env(provider),
        },
        "preset": preset,
        "roles": ROLE_DEFAULTS_BY_PRESET[preset],
        "output": {
            "artifacts_dir": "artifacts",
            "enforce_json": enforce_json,
        },
        "gating": {
            "fail_on_high": fail_on_high,
        },
    }

    if mode == "ensemble":
        cfg["constraints"] = {
            "disallow_same_model_pairs": [
                ["architect", "implementer"],
                ["implementer", "adversarial_reviewer"],
                ["implementer", "security_auditor"],
            ]
        }

    write_config(config_path, cfg)
    return config_path
