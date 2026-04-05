"""Scaffolding and validation helpers for external ESE config packs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ese.config import ConfigValidationError, validate_config
from ese.config_packs import (
    CONFIG_PACK_CONTRACT_VERSION,
    ConfigPackDefinition,
    normalize_config_pack_definition,
)
from ese.framework_defaults import (
    GOAL_PROFILES,
    PRESET_TO_GOAL_PROFILE,
    RECOMMENDED_MODEL_BY_PROVIDER_GOAL,
    apply_simple_mode_model_diversity,
    ensemble_constraints,
)

PACK_MANIFEST_NAME = "ese_pack.yaml"
DEFAULT_SMOKE_TEST_SCOPE = "Smoke test the external ESE pack for portability and config compatibility."
_SKIP_DISCOVERY_PARTS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}


class PackProjectError(ValueError):
    """Raised when an external pack project is malformed."""


@dataclass(frozen=True)
class PackProject:
    manifest_path: Path
    contract_version: int
    pack: ConfigPackDefinition
    prompt_files: tuple[Path, ...]


def _clean_pack_key(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    if not collapsed:
        raise PackProjectError("Pack key must contain at least one ASCII letter or digit.")
    return collapsed


def default_pack_title(pack_key: str) -> str:
    clean_key = _clean_pack_key(pack_key)
    return " ".join(part.capitalize() for part in clean_key.split("-"))


def default_python_package_name(pack_key: str) -> str:
    package = _clean_pack_key(pack_key).replace("-", "_")
    if package[0].isdigit():
        package = f"ese_pack_{package}"
    if not package.endswith("_pack"):
        package = f"{package}_pack"
    return package


def _validate_python_package_name(value: str) -> str:
    clean_value = (value or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", clean_value):
        raise PackProjectError(
            "Python package names must start with a letter or underscore and contain only letters, digits, and underscores."
        )
    return clean_value


def default_distribution_name(pack_key: str) -> str:
    return f"{_clean_pack_key(pack_key)}-ese-pack"


def default_pack_summary(title: str) -> str:
    clean_title = (title or "").strip() or "External"
    return f"External ESE pack for {clean_title.lower()} workflows."


def _default_role_specs(pack_key: str, title: str) -> list[dict[str, Any]]:
    prefix = default_python_package_name(pack_key).removesuffix("_pack")
    return [
        {
            "key": f"{prefix}_analyst",
            "responsibility": f"Analyze the scoped work from the {title} perspective.",
            "prompt_file": "prompts/analyst.md",
            "temperature": 0.2,
            "prompt": (
                f"You are the primary analyst for the {title} pack.\n\n"
                "Focus on the scoped task, identify the critical workstreams, list assumptions, "
                "and call out the highest-risk unknowns before implementation starts."
            ),
        },
        {
            "key": f"{prefix}_reviewer",
            "responsibility": f"Challenge the {title} analysis for gaps, risks, and missing evidence.",
            "prompt_file": "prompts/reviewer.md",
            "temperature": 0.2,
            "prompt": (
                f"You are the adversarial reviewer for the {title} pack.\n\n"
                "Inspect the scoped task and the analyst output, highlight weak assumptions, "
                "missing evidence, and operational or delivery blockers that would prevent safe execution."
            ),
        },
    ]


def _manifest_candidates(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob(PACK_MANIFEST_NAME))
        if not any(part in _SKIP_DISCOVERY_PARTS for part in path.relative_to(root).parts)
    ]


def resolve_pack_manifest(path: str | Path | None = None) -> Path:
    candidate = Path(path or ".").expanduser()
    if not candidate.exists():
        raise PackProjectError(f"Pack path does not exist: {candidate}")
    if candidate.is_file():
        return candidate.resolve()
    if not candidate.is_dir():
        raise PackProjectError(f"Pack path must be a directory or manifest file: {candidate}")

    matches = _manifest_candidates(candidate)
    if not matches:
        raise PackProjectError(
            f"No {PACK_MANIFEST_NAME} manifest found under {candidate.resolve()}."
        )
    if len(matches) > 1:
        joined = ", ".join(str(item) for item in matches)
        raise PackProjectError(
            f"Multiple {PACK_MANIFEST_NAME} manifests found under {candidate.resolve()}: {joined}"
        )
    return matches[0].resolve()


def _require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PackProjectError(f"{label} must be a mapping")
    return value


def _require_non_empty_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PackProjectError(f"{label} must be a non-empty string")
    return value.strip()


def _read_manifest_yaml(manifest_path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except OSError as err:
        raise PackProjectError(f"Could not read manifest {manifest_path}: {err}") from err
    except yaml.YAMLError as err:
        raise PackProjectError(f"Manifest {manifest_path} is not valid YAML: {err}") from err

    return _require_mapping(loaded, label=f"manifest {manifest_path}")


def _validate_pack_compatibility(pack: ConfigPackDefinition) -> None:
    if pack.goal_profile not in GOAL_PROFILES:
        supported = ", ".join(GOAL_PROFILES)
        raise PackProjectError(
            f"Unsupported goal_profile '{pack.goal_profile}'. Expected one of: {supported}"
        )
    expected_goal = PRESET_TO_GOAL_PROFILE.get(pack.preset)
    if expected_goal is None:
        supported = ", ".join(sorted(PRESET_TO_GOAL_PROFILE))
        raise PackProjectError(
            f"Unsupported preset '{pack.preset}'. Expected one of: {supported}"
        )
    if pack.goal_profile != expected_goal:
        raise PackProjectError(
            f"Pack preset '{pack.preset}' expects goal_profile '{expected_goal}', "
            f"but manifest declares '{pack.goal_profile}'."
        )


def load_pack_project(path: str | Path | None = None) -> PackProject:
    manifest_path = resolve_pack_manifest(path)
    manifest = _read_manifest_yaml(manifest_path)

    raw_contract_version = manifest.get("contract_version", CONFIG_PACK_CONTRACT_VERSION)
    roles_payload = manifest.get("roles")
    if not isinstance(roles_payload, list) or not roles_payload:
        raise PackProjectError("manifest roles must be a non-empty list")

    prompt_files: list[Path] = []
    roles: list[dict[str, Any]] = []
    for index, raw_role in enumerate(roles_payload):
        role = _require_mapping(raw_role, label=f"roles[{index}]")
        prompt_file = _require_non_empty_text(
            role.get("prompt_file"),
            label=f"roles[{index}].prompt_file",
        )
        prompt_path = (manifest_path.parent / prompt_file).resolve()
        if not prompt_path.exists():
            raise PackProjectError(
                f"roles[{index}].prompt_file points to a missing file: {prompt_path}"
            )
        try:
            prompt_text = prompt_path.read_text(encoding="utf-8").strip()
        except OSError as err:
            raise PackProjectError(f"Could not read prompt file {prompt_path}: {err}") from err
        if not prompt_text:
            raise PackProjectError(f"Prompt file must not be empty: {prompt_path}")

        prompt_files.append(prompt_path)
        roles.append(
            {
                "key": role.get("key"),
                "responsibility": role.get("responsibility"),
                "prompt": prompt_text,
                "temperature": role.get("temperature", 0.2),
            }
        )

    try:
        pack = normalize_config_pack_definition(
            {
                "contract_version": raw_contract_version,
                "key": manifest.get("key"),
                "title": manifest.get("title"),
                "summary": manifest.get("summary"),
                "preset": manifest.get("preset"),
                "goal_profile": manifest.get("goal_profile"),
                "roles": roles,
            }
        )
    except (TypeError, ValueError) as err:
        raise PackProjectError(str(err)) from err

    _validate_pack_compatibility(pack)
    return PackProject(
        manifest_path=manifest_path,
        contract_version=pack.contract_version,
        pack=pack,
        prompt_files=tuple(prompt_files),
    )


def load_pack_definition_from_manifest(path: str | Path) -> ConfigPackDefinition:
    return load_pack_project(path).pack


def describe_pack_project(path: str | Path | None = None) -> dict[str, Any]:
    project = load_pack_project(path)
    return {
        "manifest_path": str(project.manifest_path),
        "pack_key": project.pack.key,
        "title": project.pack.title,
        "summary": project.pack.summary,
        "preset": project.pack.preset,
        "goal_profile": project.pack.goal_profile,
        "contract_version": project.contract_version,
        "role_count": len(project.pack.roles),
        "roles": [role.key for role in project.pack.roles],
        "prompt_files": [str(path) for path in project.prompt_files],
    }


def smoke_test_pack_project(
    path: str | Path | None = None,
    *,
    provider: str = "openai",
    model: str | None = None,
) -> dict[str, Any]:
    project = load_pack_project(path)
    clean_provider = _require_non_empty_text(provider, label="provider").lower()
    default_model = model
    if not default_model:
        default_model = RECOMMENDED_MODEL_BY_PROVIDER_GOAL.get(clean_provider, {}).get(
            project.pack.goal_profile
        )
    if not default_model:
        raise PackProjectError(
            f"No default smoke-test model is known for provider '{clean_provider}'. Pass --model explicitly."
        )

    role_order = [role.key for role in project.pack.roles]
    cfg: dict[str, Any] = {
        "version": 1,
        "mode": "ensemble",
        "provider": {
            "name": clean_provider,
            "model": default_model,
        },
        "preset": project.pack.preset,
        "role_order": role_order,
        "roles": {
            role.key: {
                "temperature": role.temperature,
                "prompt": role.prompt,
            }
            for role in project.pack.roles
        },
        "input": {
            "scope": DEFAULT_SMOKE_TEST_SCOPE,
        },
        "output": {
            "artifacts_dir": "artifacts",
            "enforce_json": True,
        },
        "gating": {
            "fail_on_high": True,
        },
        "runtime": {
            "adapter": "dry-run",
            "timeout_seconds": 60,
            "max_retries": 2,
            "retry_backoff_seconds": 1.0,
        },
        "install_profile": {
            "kind": "pack",
            "pack": project.pack.key,
        },
        "constraints": ensemble_constraints(selected_roles=role_order),
    }
    apply_simple_mode_model_diversity(
        cfg,
        provider=clean_provider,
        selected_roles=role_order,
    )

    try:
        validated_cfg = validate_config(cfg, source=str(project.manifest_path))
    except ConfigValidationError as err:
        raise PackProjectError(f"Generated smoke-test config is invalid: {err}") from err

    summary = describe_pack_project(project.manifest_path)
    summary.update(
        {
            "provider": clean_provider,
            "model": default_model,
            "config": validated_cfg,
        }
    )
    return summary


def scaffold_pack_project(
    target_dir: str | Path,
    *,
    pack_key: str,
    title: str | None = None,
    summary: str | None = None,
    package_name: str | None = None,
    preset: str = "balanced",
    goal_profile: str | None = None,
    force: bool = False,
) -> PackProject:
    clean_key = _clean_pack_key(pack_key)
    clean_title = (title or "").strip() or default_pack_title(clean_key)
    clean_summary = (summary or "").strip() or default_pack_summary(clean_title)
    clean_package_name = _validate_python_package_name(
        (package_name or "").strip() or default_python_package_name(clean_key)
    )
    clean_preset = _require_non_empty_text(preset, label="preset")
    clean_goal_profile = (goal_profile or "").strip() or PRESET_TO_GOAL_PROFILE.get(clean_preset, "")
    if not clean_goal_profile:
        supported = ", ".join(sorted(PRESET_TO_GOAL_PROFILE))
        raise PackProjectError(f"Unsupported preset '{clean_preset}'. Expected one of: {supported}")

    target = Path(target_dir).expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise PackProjectError(f"Target path is not a directory: {target}")
    if target.exists() and any(target.iterdir()) and not force:
        raise PackProjectError(f"Target directory is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)

    package_dir = target / "src" / clean_package_name
    prompts_dir = package_dir / "prompts"
    package_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    role_specs = _default_role_specs(clean_key, clean_title)
    manifest_payload = {
        "contract_version": CONFIG_PACK_CONTRACT_VERSION,
        "key": clean_key,
        "title": clean_title,
        "summary": clean_summary,
        "preset": clean_preset,
        "goal_profile": clean_goal_profile,
        "roles": [
            {
                "key": role["key"],
                "responsibility": role["responsibility"],
                "prompt_file": role["prompt_file"],
                "temperature": role["temperature"],
            }
            for role in role_specs
        ],
    }

    pyproject_text = "\n".join(
        [
            "[build-system]",
            'requires = ["setuptools>=69", "wheel"]',
            'build-backend = "setuptools.build_meta"',
            "",
            "[project]",
            f'name = "{default_distribution_name(clean_key)}"',
            'version = "0.1.0"',
            f'description = "{clean_summary}"',
            'readme = "README.md"',
            'requires-python = ">=3.10"',
            'dependencies = ["ese-cli>=1.0.0"]',
            "",
            '[project.entry-points."ese.config_packs"]',
            f'{clean_key.replace("-", "_")} = "{clean_package_name}.pack:load_pack"',
            "",
            "[tool.setuptools.packages.find]",
            'where = ["src"]',
            "",
            "[tool.setuptools.package-data]",
            f'"{clean_package_name}" = ["{PACK_MANIFEST_NAME}", "prompts/*.md"]',
            "",
        ]
    )
    readme_text = "\n".join(
        [
            f"# {clean_title}",
            "",
            clean_summary,
            "",
            "## Development",
            "",
            "```bash",
            "pip install -e .",
            "ese pack validate .",
            "ese pack test .",
            "```",
            "",
            "Install the project into an environment with `ese-cli` to expose the pack through `ese packs`.",
            "",
        ]
    )
    init_text = "\n".join(
        [
            '"""External ESE config pack."""',
            "",
            "from .pack import load_pack",
            "",
            '__all__ = ["load_pack"]',
            "",
        ]
    )
    pack_loader_text = "\n".join(
        [
            '"""Entry point for the external ESE pack."""',
            "",
            "from pathlib import Path",
            "",
            "from ese.pack_sdk import load_pack_definition_from_manifest",
            "",
            "",
            "def load_pack():",
            '    """Return the ConfigPackDefinition exported by this package."""',
            f'    return load_pack_definition_from_manifest(Path(__file__).with_name("{PACK_MANIFEST_NAME}"))',
            "",
        ]
    )

    (target / "pyproject.toml").write_text(pyproject_text, encoding="utf-8")
    (target / "README.md").write_text(readme_text, encoding="utf-8")
    (package_dir / "__init__.py").write_text(init_text, encoding="utf-8")
    (package_dir / "pack.py").write_text(pack_loader_text, encoding="utf-8")
    (package_dir / PACK_MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest_payload, sort_keys=False),
        encoding="utf-8",
    )
    for role in role_specs:
        prompt_name = Path(role["prompt_file"]).name
        (prompts_dir / prompt_name).write_text(f"{role['prompt']}\n", encoding="utf-8")

    return load_pack_project(package_dir / PACK_MANIFEST_NAME)
