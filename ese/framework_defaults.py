"""Shared framework defaults used by config builders and the setup wizard."""

from __future__ import annotations

from typing import Any

GOAL_PROFILES = [
    "fast",
    "balanced",
    "high-quality",
    "security-heavy",
]

GOAL_TO_PRESET = {
    "fast": "fast",
    "balanced": "balanced",
    "high-quality": "strict",
    "security-heavy": "paranoid",
}

PRESET_TO_GOAL_PROFILE = {
    "fast": "fast",
    "balanced": "balanced",
    "strict": "high-quality",
    "paranoid": "security-heavy",
}

GOAL_DEFAULT_ROLES: dict[str, list[str]] = {
    "fast": [
        "architect",
        "implementer",
        "adversarial_reviewer",
        "test_generator",
    ],
    "balanced": [
        "architect",
        "implementer",
        "adversarial_reviewer",
        "security_auditor",
        "test_generator",
        "performance_analyst",
    ],
    "high-quality": [
        "architect",
        "implementer",
        "adversarial_reviewer",
        "security_auditor",
        "test_generator",
        "performance_analyst",
        "documentation_writer",
    ],
    "security-heavy": [
        "architect",
        "implementer",
        "adversarial_reviewer",
        "security_auditor",
        "test_generator",
        "performance_analyst",
        "devops_sre",
        "database_engineer",
        "release_manager",
    ],
}

COMMON_MODELS_BY_PROVIDER: dict[str, list[str]] = {
    "openai": [
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "o3",
    ],
    "anthropic": [
        "claude-sonnet-4",
        "claude-opus-4",
    ],
    "google": [
        "gemini-2.0-flash",
        "gemini-2.0-pro",
    ],
    "xai": [
        "grok-3",
        "grok-3-mini",
    ],
    "openrouter": [
        "openai/gpt-5",
        "anthropic/claude-sonnet-4",
        "google/gemini-2.0-pro",
    ],
    "huggingface": [
        "meta-llama/Llama-3.3-70B-Instruct",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
    ],
    "local": [
        "llama3.1:8b",
        "qwen2.5-coder:14b",
    ],
}

RECOMMENDED_MODEL_BY_PROVIDER_GOAL: dict[str, dict[str, str]] = {
    "openai": {
        "fast": "gpt-5-mini",
        "balanced": "gpt-5",
        "high-quality": "gpt-5",
        "security-heavy": "o3",
    },
    "anthropic": {
        "fast": "claude-sonnet-4",
        "balanced": "claude-sonnet-4",
        "high-quality": "claude-opus-4",
        "security-heavy": "claude-opus-4",
    },
    "google": {
        "fast": "gemini-2.0-flash",
        "balanced": "gemini-2.0-pro",
        "high-quality": "gemini-2.0-pro",
        "security-heavy": "gemini-2.0-pro",
    },
    "xai": {
        "fast": "grok-3-mini",
        "balanced": "grok-3",
        "high-quality": "grok-3",
        "security-heavy": "grok-3",
    },
    "openrouter": {
        "fast": "openai/gpt-5",
        "balanced": "anthropic/claude-sonnet-4",
        "high-quality": "google/gemini-2.0-pro",
        "security-heavy": "anthropic/claude-opus-4",
    },
    "huggingface": {
        "fast": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "balanced": "meta-llama/Llama-3.3-70B-Instruct",
        "high-quality": "meta-llama/Llama-3.3-70B-Instruct",
        "security-heavy": "meta-llama/Llama-3.3-70B-Instruct",
    },
    "local": {
        "fast": "llama3.1:8b",
        "balanced": "qwen2.5-coder:14b",
        "high-quality": "qwen2.5-coder:14b",
        "security-heavy": "qwen2.5-coder:14b",
    },
}

DEFAULT_DISALLOW_SAME_MODEL_PAIRS = [
    ("architect", "implementer"),
    ("implementer", "adversarial_reviewer"),
    ("implementer", "security_auditor"),
    ("adversarial_reviewer", "security_auditor"),
    ("implementer", "release_manager"),
]

ROLE_DEFAULTS_BY_PRESET: dict[str, dict[str, dict[str, Any]]] = {
    "fast": {
        "architect": {"temperature": 0.2},
        "implementer": {"temperature": 0.1},
        "adversarial_reviewer": {"temperature": 0.6},
        "security_auditor": {"temperature": 0.2},
        "test_generator": {"temperature": 0.2},
        "performance_analyst": {"temperature": 0.2},
        "documentation_writer": {"temperature": 0.3},
        "devops_sre": {"temperature": 0.2},
        "database_engineer": {"temperature": 0.2},
        "release_manager": {"temperature": 0.2},
    },
    "balanced": {
        "architect": {"temperature": 0.2},
        "implementer": {"temperature": 0.1},
        "adversarial_reviewer": {"temperature": 0.7},
        "security_auditor": {"temperature": 0.2},
        "test_generator": {"temperature": 0.2},
        "performance_analyst": {"temperature": 0.2},
        "documentation_writer": {"temperature": 0.2},
        "devops_sre": {"temperature": 0.2},
        "database_engineer": {"temperature": 0.2},
        "release_manager": {"temperature": 0.2},
    },
    "strict": {
        "architect": {"temperature": 0.1},
        "implementer": {"temperature": 0.05},
        "adversarial_reviewer": {"temperature": 0.6},
        "security_auditor": {"temperature": 0.1},
        "test_generator": {"temperature": 0.1},
        "performance_analyst": {"temperature": 0.1},
        "documentation_writer": {"temperature": 0.15},
        "devops_sre": {"temperature": 0.1},
        "database_engineer": {"temperature": 0.1},
        "release_manager": {"temperature": 0.1},
    },
    "paranoid": {
        "architect": {"temperature": 0.1},
        "implementer": {"temperature": 0.05},
        "adversarial_reviewer": {"temperature": 0.8},
        "security_auditor": {"temperature": 0.1},
        "test_generator": {"temperature": 0.1},
        "performance_analyst": {"temperature": 0.1},
        "documentation_writer": {"temperature": 0.15},
        "devops_sre": {"temperature": 0.1},
        "database_engineer": {"temperature": 0.1},
        "release_manager": {"temperature": 0.1},
    },
}


def roles_for_preset(preset: str, selected_roles: list[str]) -> dict[str, dict[str, Any]]:
    defaults = ROLE_DEFAULTS_BY_PRESET.get(preset, {})
    return {role: dict(defaults.get(role, {"temperature": 0.2})) for role in selected_roles}


def ensemble_constraints(selected_roles: list[str]) -> dict[str, Any]:
    selected = set(selected_roles)
    pairs = [
        [left, right]
        for left, right in DEFAULT_DISALLOW_SAME_MODEL_PAIRS
        if left in selected and right in selected
    ]
    return {"disallow_same_model_pairs": pairs}


def apply_simple_mode_model_diversity(
    cfg: dict[str, Any],
    *,
    provider: str,
    selected_roles: list[str],
) -> None:
    common_models = COMMON_MODELS_BY_PROVIDER.get(provider, [])
    if len(common_models) < 2:
        return

    provider_cfg = cfg.get("provider") or {}
    base_model = provider_cfg.get("model")
    alternatives = [model for model in common_models if model != base_model]
    if not alternatives:
        return

    roles_cfg = cfg.get("roles") or {}
    if not isinstance(roles_cfg, dict):
        return

    assigned_models: dict[str, str] = {
        role: str((role_cfg or {}).get("model") or base_model)
        for role, role_cfg in roles_cfg.items()
    }

    def assign_distinct(role: str, *, disallow_with: list[str]) -> None:
        if role not in selected_roles:
            return
        banned = {
            assigned_models.get(other)
            for other in disallow_with
            if assigned_models.get(other)
        }
        for candidate in alternatives:
            if candidate not in banned:
                role_cfg = roles_cfg.get(role) or {}
                role_cfg["model"] = candidate
                roles_cfg[role] = role_cfg
                assigned_models[role] = candidate
                return

    assign_distinct("implementer", disallow_with=["architect"])
    assign_distinct("adversarial_reviewer", disallow_with=["implementer", "security_auditor"])
    assign_distinct("security_auditor", disallow_with=["implementer", "adversarial_reviewer"])
    assign_distinct("release_manager", disallow_with=["implementer"])
    cfg["roles"] = roles_cfg
