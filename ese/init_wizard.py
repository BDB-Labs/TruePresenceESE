"""Interactive wizard for creating ese.config.yaml."""

from __future__ import annotations

import os
from typing import Any, Dict, TypeVar

import questionary

from ese.config import (
    ConfigValidationError,
    resolve_role_model,
    validate_config,
    write_config,
)
from ese.config_packs import ConfigPackDefinition, get_config_pack, list_config_packs
from ese.framework_defaults import (
    COMMON_MODELS_BY_PROVIDER,
    GOAL_PROFILES,
    GOAL_TO_PRESET,
    PRESET_TO_GOAL_PROFILE,
    RECOMMENDED_MODEL_BY_PROVIDER_GOAL,
)
from ese.framework_defaults import (
    apply_simple_mode_model_diversity as _apply_simple_mode_model_diversity,
)
from ese.framework_defaults import (
    ensemble_constraints as _ensemble_constraints,
)
from ese.framework_defaults import (
    roles_for_preset as _framework_roles_for_preset,
)
from ese.provider_runtime import (
    PROVIDER_CHOICES,
    builtin_runtime_adapter,
    provider_runtime_capability,
)
from ese.provider_runtime import (
    default_api_key_env as _default_api_key_env,
)
from ese.provider_runtime import (
    default_provider_from_env as _provider_default_from_env,
)
from ese.role_drafting import (
    FrameworkRoleInput,
    draft_framework_roles,
)

DEMO_EXECUTION_MODE = "demo"
LIVE_EXECUTION_MODE = "live"
CUSTOM_MODULE_EXECUTION_MODE = "custom_module"
FRAMEWORK_CONFIG_TYPE = "framework"
PACK_CONFIG_TYPE = "pack"

MODEL_ALIASES_BY_PROVIDER: Dict[str, Dict[str, str]] = {
    "openai": {
        "g5": "gpt-5",
        "g5mini": "gpt-5-mini",
        "g5nano": "gpt-5-nano",
        "reasoning": "o3",
    },
    "anthropic": {
        "sonnet": "claude-sonnet-4",
        "opus": "claude-opus-4",
    },
    "google": {
        "flash": "gemini-2.0-flash",
        "pro": "gemini-2.0-pro",
    },
    "xai": {
        "grok": "grok-3",
        "grok-mini": "grok-3-mini",
    },
    "openrouter": {
        "or-g5": "openai/gpt-5",
        "or-sonnet": "anthropic/claude-sonnet-4",
        "or-pro": "google/gemini-2.0-pro",
    },
}

CUSTOM_MODEL_CHOICE = "custom (type model id)"
RECOMMENDED_MODEL_CHOICE = "recommended"
COMMON_MODEL_CHOICE = "choose common model"
CUSTOM_OR_ALIAS_MODEL_CHOICE = "custom or alias"
INHERIT_GLOBAL_MODEL_CHOICE = "inherit global default"
ROLE_COMMON_MODEL_CHOICE = "choose another common model"
ROLE_CUSTOM_MODEL_CHOICE = "custom or alias"
ROLE_RECOMMENDED_MODEL_CHOICE = "use recommended model"

ROLE_DESCRIPTIONS: Dict[str, str] = {
    "architect": "System design, decomposition, and interface contracts.",
    "implementer": "Code changes and refactors.",
    "adversarial_reviewer": "Bug/risk hunting and regression checks.",
    "security_auditor": "Threat modeling and vulnerability review.",
    "test_generator": "Unit/integration/e2e test generation.",
    "performance_analyst": "Latency, memory, and scalability analysis.",
    "documentation_writer": "README, API docs, and migration notes.",
    "devops_sre": "CI/CD, deploy safety, and observability.",
    "database_engineer": "Schema/index/migration correctness.",
    "release_manager": "Go/no-go risk assessment and rollout checks.",
}

DEFAULT_SELECTED_ROLES = [
    "architect",
    "implementer",
    "adversarial_reviewer",
    "security_auditor",
    "test_generator",
    "performance_analyst",
]

T = TypeVar("T")


class WizardCanceled(RuntimeError):
    """Raised when the interactive wizard is canceled."""


def _provider_choices(*, advanced: bool) -> list[questionary.Choice]:
    choices: list[questionary.Choice] = []
    for provider in PROVIDER_CHOICES:
        capability = provider_runtime_capability(provider)
        if capability.supports_builtin_live or advanced:
            title = capability.live_title
        else:
            title = capability.demo_title
        choices.append(questionary.Choice(title=title, value=provider))
    return choices


def _validate_non_empty_text(label: str):
    def _validator(value: str | None) -> bool | str:
        if isinstance(value, str) and value.strip():
            return True
        return f"{label} is required."

    return _validator


def _validate_positive_int_text(label: str):
    def _validator(value: str | None) -> bool | str:
        raw = (value or "").strip()
        if raw.isdigit() and int(raw) > 0:
            return True
        return f"{label} must be a positive integer."

    return _validator


def _validate_adapter_reference(value: str | None) -> bool | str:
    raw = (value or "").strip()
    module_name, separator, object_name = raw.partition(":")
    if separator and module_name.strip() and object_name.strip():
        return True
    return "Enter adapter reference in 'module:function' format."


def _required_answer(value: T | None) -> T:
    if value is None:
        raise WizardCanceled("setup canceled")
    return value


def _ask_text(message: str, **kwargs: Any) -> str:
    return _required_answer(questionary.text(message, **kwargs).ask())


def _ask_select(message: str, *, choices: list[Any], default: Any | None = None) -> str:
    options: dict[str, Any] = {"choices": choices}
    if default is not None:
        options["default"] = default
    return _required_answer(questionary.select(message, **options).ask())


def _ask_confirm(message: str, *, default: bool) -> bool:
    return bool(_required_answer(questionary.confirm(message, default=default).ask()))


def _resolve_model_alias(provider: str, model_name: str) -> str:
    raw = (model_name or "").strip()
    if not raw:
        return raw
    aliases = MODEL_ALIASES_BY_PROVIDER.get(provider, {})
    return aliases.get(raw.lower(), raw)


def _input_model_id(provider: str, prompt: str) -> str:
    alias_help = ", ".join(sorted(MODEL_ALIASES_BY_PROVIDER.get(provider, {}).keys()))
    if alias_help:
        prompt = f"{prompt} (aliases: {alias_help})"
    typed = _ask_text(prompt)
    return _resolve_model_alias(provider, typed)


def _select_default_model(provider: str, goal_profile: str | None = None) -> str:
    common_models = COMMON_MODELS_BY_PROVIDER.get(provider, [])
    recommended = RECOMMENDED_MODEL_BY_PROVIDER_GOAL.get(provider, {}).get(goal_profile or "")

    if not common_models and recommended:
        return recommended

    if not common_models:
        return _input_model_id(provider, "Default model name (provider model id):")

    choices: list[str] = common_models + [CUSTOM_MODEL_CHOICE]
    default = common_models[0]
    if recommended:
        recommended_label = f"{RECOMMENDED_MODEL_CHOICE} ({recommended})"
        choices = [recommended_label, COMMON_MODEL_CHOICE, CUSTOM_OR_ALIAS_MODEL_CHOICE]
        default = recommended_label

    model_choice = _ask_select(
        "Default model:",
        choices=choices,
        default=default,
    )

    if model_choice == COMMON_MODEL_CHOICE:
        return _ask_select(
            "Choose common model:",
            choices=common_models,
            default=recommended if recommended in common_models else common_models[0],
        )

    if isinstance(model_choice, str) and model_choice.startswith(f"{RECOMMENDED_MODEL_CHOICE} (") and model_choice.endswith(")"):
        return model_choice[len(RECOMMENDED_MODEL_CHOICE) + 2 : -1]

    if model_choice in {CUSTOM_MODEL_CHOICE, CUSTOM_OR_ALIAS_MODEL_CHOICE}:
        return _input_model_id(provider, "Custom model id:")

    return model_choice


def _select_role_model_override(
    *,
    provider: str,
    role: str,
    default_model: str,
    goal_profile: str | None = None,
) -> str | None:
    common_models = COMMON_MODELS_BY_PROVIDER.get(provider, [])
    recommended = RECOMMENDED_MODEL_BY_PROVIDER_GOAL.get(provider, {}).get(goal_profile or "")
    inherit_choice = f"{INHERIT_GLOBAL_MODEL_CHOICE} ({default_model})"
    recommended_choice = f"{ROLE_RECOMMENDED_MODEL_CHOICE} ({recommended})" if recommended else None

    choices: list[str] = [inherit_choice]
    if recommended_choice and recommended != default_model:
        choices.append(recommended_choice)
    if common_models:
        choices.append(ROLE_COMMON_MODEL_CHOICE)
    choices.append(ROLE_CUSTOM_MODEL_CHOICE)

    selected = _ask_select(
        f"Model for role '{role}':",
        choices=choices,
        default=inherit_choice,
    )

    if selected in {default_model, inherit_choice}:
        return None

    if selected == ROLE_COMMON_MODEL_CHOICE:
        available_models = [model for model in common_models if model != default_model] or common_models
        return _ask_select(
            f"Choose common model for role '{role}':",
            choices=available_models,
            default=recommended if recommended in available_models else available_models[0],
        )

    if selected == ROLE_CUSTOM_MODEL_CHOICE:
        return _input_model_id(provider, f"Custom model id for role '{role}':")

    if recommended_choice and selected == recommended_choice:
        return recommended

    return selected


def _apply_advanced_role_model_overrides(
    roles_cfg: Dict[str, Dict[str, Any]],
    *,
    provider: str,
    selected_roles: list[str],
    default_model: str,
    goal_profile: str | None = None,
) -> None:
    if not _ask_confirm("Customize models for individual roles?", default=False):
        return

    for role in selected_roles:
        override_model = _select_role_model_override(
            provider=provider,
            role=role,
            default_model=default_model,
            goal_profile=goal_profile,
        )
        if not override_model or override_model == default_model:
            continue

        role_cfg = dict(roles_cfg.get(role) or {})
        role_cfg["model"] = override_model
        roles_cfg[role] = role_cfg


def _select_execution_mode(provider: str, *, advanced: bool) -> str:
    capability = provider_runtime_capability(provider)
    supports_live = capability.supports_builtin_live
    choices: list[questionary.Choice] = []

    if supports_live:
        live_title = "live - built-in runtime adapter"
        if provider == "custom_api":
            live_title = "live - Responses-compatible gateway adapter"
        choices.append(questionary.Choice(title=live_title, value=LIVE_EXECUTION_MODE))

    choices.append(
        questionary.Choice(
            title="demo - dry-run with provider/model defaults",
            value=DEMO_EXECUTION_MODE,
        ),
    )

    if advanced and not supports_live:
        choices.append(
            questionary.Choice(
                title="custom module - live execution via module:function",
                value=CUSTOM_MODULE_EXECUTION_MODE,
            ),
        )
    elif advanced and supports_live:
        choices.append(
            questionary.Choice(
                title="custom module - override built-in runtime",
                value=CUSTOM_MODULE_EXECUTION_MODE,
            ),
        )

    if capability.prefer_live_when_selected:
        default_mode = LIVE_EXECUTION_MODE
    elif supports_live and os.getenv(_default_api_key_env(provider)):
        default_mode = LIVE_EXECUTION_MODE
    else:
        default_mode = DEMO_EXECUTION_MODE
    if not supports_live:
        default_mode = DEMO_EXECUTION_MODE

    return _ask_select(
        "Execution mode:",
        choices=choices,
        default=default_mode,
    )


def _resolve_runtime_adapter(
    *,
    provider: str,
    execution_mode: str,
    advanced: bool,
) -> str:
    if execution_mode == DEMO_EXECUTION_MODE:
        return "dry-run"
    if execution_mode == LIVE_EXECUTION_MODE:
        builtin_adapter = builtin_runtime_adapter(provider)
        if builtin_adapter:
            return builtin_adapter
        if not advanced:
            return "dry-run"
    return _ask_text(
        "Custom adapter reference (module:function):",
        validate=_validate_adapter_reference,
    )


def _role_choices() -> list[questionary.Choice]:
    return [
        questionary.Choice(
            title=f"{role} - {description}",
            value=role,
            checked=role in DEFAULT_SELECTED_ROLES,
        )
        for role, description in ROLE_DESCRIPTIONS.items()
    ]


def _ordered_selected_roles(selected_roles: list[str]) -> list[str]:
    selected = set(selected_roles)
    return [role for role in ROLE_DESCRIPTIONS if role in selected]


def _config_type_choices(*, has_packs: bool) -> list[questionary.Choice]:
    choices = [
        questionary.Choice(
            title="framework - define your own role names and responsibilities",
            value=FRAMEWORK_CONFIG_TYPE,
        ),
    ]
    if has_packs:
        choices.append(
            questionary.Choice(
                title="pack - use an installed config pack",
                value=PACK_CONFIG_TYPE,
            ),
        )
    return choices


def _pack_choices(packs: list[ConfigPackDefinition]) -> list[questionary.Choice]:
    return [
        questionary.Choice(title=f"{pack.title} - {pack.summary}", value=pack.key)
        for pack in packs
    ]


def _roles_for_preset(preset: str, selected_roles: list[str]) -> Dict[str, Dict[str, Any]]:
    return _framework_roles_for_preset(preset, selected_roles)


def _build_pack_roles_cfg(pack: ConfigPackDefinition) -> Dict[str, Dict[str, Any]]:
    return {
        role.key: {
            "temperature": role.temperature,
            "prompt": role.prompt,
        }
        for role in pack.roles
    }


def _preview_config(cfg: Dict[str, Any]) -> None:
    roles = cfg.get("roles", {}) or {}
    role_models = {role: resolve_role_model(cfg, role) for role in roles}
    pairs = (cfg.get("constraints") or {}).get("disallow_same_model_pairs") or []
    scope = ((cfg.get("input") or {}).get("scope") or "").strip()
    install_profile = cfg.get("install_profile") or {}

    violations: list[str] = []
    for left, right in pairs:
        if role_models.get(left) == role_models.get(right):
            violations.append(f"{left} and {right} share {role_models.get(left)}")

    lines = [
        "",
        "Configuration preview:",
        f"  mode: {cfg.get('mode')}",
        f"  scope: {scope}",
        f"  install_profile: {install_profile.get('kind', 'framework')}",
        f"  provider: {(cfg.get('provider') or {}).get('name')} / {(cfg.get('provider') or {}).get('model')}",
        f"  runtime.adapter: {(cfg.get('runtime') or {}).get('adapter')}",
        f"  output.artifacts_dir: {(cfg.get('output') or {}).get('artifacts_dir')}",
        "  role models:",
    ]
    if install_profile.get("pack"):
        lines.insert(4, f"  pack: {install_profile.get('pack')}")
    lines.extend(f"    - {role}: {model}" for role, model in role_models.items())
    if violations:
        lines.append("  doctor risk flags:")
        lines.extend(f"    - {item}" for item in violations)
    else:
        lines.append("  doctor risk flags: none")

    questionary.print("\n".join(lines))


def _render_framework_role_review(
    *,
    drafts,
    overlap_warnings: list[str],
) -> None:
    lines = ["", "Framework role review:"]
    for draft in drafts:
        lines.append(f"  - {draft.name} -> {draft.key}")
        lines.append(f"    responsibility: {draft.responsibility}")
        if draft.warnings:
            lines.extend(f"    warning: {item}" for item in draft.warnings)
        if draft.suggestions:
            lines.extend(f"    suggestion: {item}" for item in draft.suggestions)
    if overlap_warnings:
        lines.append("  overlap warnings:")
        lines.extend(f"    - {item}" for item in overlap_warnings)
    else:
        lines.append("  overlap warnings: none")
    questionary.print("\n".join(lines))


def _collect_framework_roles(*, scope: str) -> tuple[Dict[str, Dict[str, Any]], list[str]]:
    role_count = int(
        _ask_text(
            "How many ensemble members should this framework config start with?",
            default="3",
            validate=_validate_positive_int_text("Role count"),
        ),
    )

    role_inputs: list[FrameworkRoleInput] = []
    for index in range(role_count):
        role_number = index + 1
        role_name = _ask_text(
            f"Role {role_number} name:",
            validate=_validate_non_empty_text(f"Role {role_number} name"),
        )
        responsibility = _ask_text(
            f"What does '{role_name}' own?",
            validate=_validate_non_empty_text(f"Responsibility for {role_name}"),
        )
        role_inputs.append(
            FrameworkRoleInput(
                name=role_name,
                responsibility=responsibility,
            ),
        )

    review = draft_framework_roles(scope=scope, roles=role_inputs)
    _render_framework_role_review(
        drafts=list(review.drafts),
        overlap_warnings=list(review.overlap_warnings),
    )

    roles_cfg: Dict[str, Dict[str, Any]] = {}
    role_order: list[str] = []
    for draft in review.drafts:
        role_order.append(draft.key)
        role_cfg: Dict[str, Any] = {
            "temperature": 0.2,
            "prompt": draft.prompt,
        }
        roles_cfg[draft.key] = role_cfg
    return roles_cfg, role_order


def run_wizard(config_path: str = "ese.config.yaml", *, advanced: bool = False) -> str | None:
    while True:
        try:
            available_packs = list_config_packs()
            mode = _ask_select("Setup mode:", choices=["ensemble", "solo"])
            provider = _ask_select(
                "Provider:",
                choices=_provider_choices(advanced=advanced),
                default=_provider_default_from_env(),
            )
            execution_mode = _select_execution_mode(provider, advanced=advanced)
            config_type = FRAMEWORK_CONFIG_TYPE
            if available_packs:
                config_type = _ask_select(
                    "Configuration source:",
                    choices=_config_type_choices(has_packs=True),
                    default=FRAMEWORK_CONFIG_TYPE,
                )
        except WizardCanceled:
            return None

        provider_name = provider
        provider_cfg: Dict[str, Any] = {}

        if provider == "custom_api":
            try:
                provider_name = _ask_text(
                    "Custom provider name (e.g., my-gateway):",
                    validate=_validate_non_empty_text("Provider name"),
                )
            except WizardCanceled:
                return None

        selected_pack: ConfigPackDefinition | None = None
        goal_profile = None
        preset: str
        try:
            if config_type == PACK_CONFIG_TYPE:
                selected_pack = get_config_pack(
                    _ask_select(
                        "Installed pack:",
                        choices=_pack_choices(available_packs),
                    ),
                )
                goal_profile = selected_pack.goal_profile
                preset = selected_pack.preset
            elif advanced:
                preset = _ask_select(
                    "Preset:",
                    choices=["fast", "balanced", "strict", "paranoid"],
                )
                goal_profile = PRESET_TO_GOAL_PROFILE.get(preset)
            else:
                goal_profile = _ask_select(
                    "Goal profile:",
                    choices=GOAL_PROFILES,
                    default="balanced",
                )
                preset = GOAL_TO_PRESET[goal_profile]

            scope = _ask_text(
                "Project scope or task for this ensemble run:",
                validate=_validate_non_empty_text("Project scope"),
            )
            model = _select_default_model(provider=provider, goal_profile=goal_profile)
        except WizardCanceled:
            return None

        selected_roles: list[str]
        role_order: list[str]
        if selected_pack is not None:
            roles_cfg = _build_pack_roles_cfg(selected_pack)
            selected_roles = [role.key for role in selected_pack.roles]
            role_order = list(selected_roles)
        else:
            roles_cfg, role_order = _collect_framework_roles(scope=scope)
            selected_roles = list(role_order)

        if advanced:
            _apply_advanced_role_model_overrides(
                roles_cfg,
                provider=provider,
                selected_roles=selected_roles,
                default_model=model,
                goal_profile=goal_profile,
            )
        runtime_adapter = _resolve_runtime_adapter(
            provider=provider,
            execution_mode=execution_mode,
            advanced=advanced,
        )

        try:
            api_key_env = None
            if runtime_adapter in {"openai", "custom_api"}:
                api_key_env = _ask_text(
                    "API key environment variable:",
                    default=_default_api_key_env(provider),
                    validate=_validate_non_empty_text("API key environment variable"),
                )
            if runtime_adapter == "local":
                local_base_url = _ask_text(
                    "Local base URL (default Ollama OpenAI-compatible endpoint):",
                    default="http://localhost:11434/v1",
                    validate=_validate_non_empty_text("Local base URL"),
                )
                provider_cfg["base_url"] = local_base_url.strip()
            if runtime_adapter == "custom_api":
                custom_base_url = _ask_text(
                    "Custom API base URL (required, e.g., https://gateway.example/v1):",
                    validate=_validate_non_empty_text("Base URL"),
                )
                provider_cfg["base_url"] = custom_base_url.strip()

            enforce_json = _ask_confirm(
                "Enforce JSON-only outputs for role reports?",
                default=True,
            )

            fail_on_high = _ask_confirm(
                "Fail pipeline on HIGH severity findings?",
                default=True,
            )
        except WizardCanceled:
            return None

        cfg: Dict[str, Any] = {
            "version": 1,
            "mode": mode,
            "provider": {
                "name": provider_name,
                "model": model,
                **provider_cfg,
            },
            "preset": preset,
            "role_order": role_order,
            "roles": roles_cfg,
            "input": {
                "scope": scope.strip(),
            },
            "output": {
                "artifacts_dir": "artifacts",
                "enforce_json": enforce_json,
            },
            "gating": {
                "fail_on_high": fail_on_high,
            },
            "runtime": {
                "adapter": runtime_adapter,
                "timeout_seconds": 60,
                "max_retries": 2,
                "retry_backoff_seconds": 1.0,
            },
            "install_profile": {
                "kind": config_type,
            },
        }
        if selected_pack is not None:
            cfg["install_profile"]["pack"] = selected_pack.key
        if api_key_env:
            cfg["provider"]["api_key_env"] = api_key_env

        if runtime_adapter == "openai":
            cfg["runtime"]["openai"] = {
                "base_url": provider_cfg.get("base_url", "https://api.openai.com/v1"),
            }
        if runtime_adapter == "local":
            cfg["runtime"]["local"] = {
                "base_url": provider_cfg.get("base_url", "http://localhost:11434/v1"),
                "use_openai_compat_auth": True,
            }
        if runtime_adapter == "custom_api":
            cfg["runtime"]["custom_api"] = {
                "base_url": provider_cfg.get("base_url"),
            }

        if mode == "ensemble":
            cfg["constraints"] = _ensemble_constraints(selected_roles=selected_roles)
            if not advanced:
                _apply_simple_mode_model_diversity(
                    cfg,
                    provider=provider,
                    selected_roles=selected_roles,
                )

        try:
            validated_cfg = validate_config(cfg, source=config_path)
        except ConfigValidationError as err:
            questionary.print(f"\nConfiguration error:\n  {err}\n")
            try:
                if not _ask_confirm("Restart setup?", default=True):
                    return None
            except WizardCanceled:
                return None
            continue

        _preview_config(validated_cfg)
        try:
            if _ask_confirm("Write this config?", default=True):
                write_config(config_path, validated_cfg)
                return config_path

            if not _ask_confirm("Restart setup?", default=True):
                return None
        except WizardCanceled:
            return None
