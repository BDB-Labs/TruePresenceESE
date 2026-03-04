"""ESE configuration loading and helpers."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def load_config(path: str) -> Dict[str, Any]:
    """Load YAML config into a dict.

    Returns an empty dict if the file does not exist.
    """
    p = Path(path)
    if not p.exists():
        return {}

    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_config(path: str, cfg: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


def resolve_role_model(cfg: Dict[str, Any], role: str) -> str:
    """Resolve effective model identifier for a role.

    Supports:
      - global provider.model
      - per-role overrides: roles.<role>.model
      - per-role provider override: roles.<role>.provider

    Returns a string like "openai:gpt-5".
    """

    roles_cfg: Dict[str, Any] = cfg.get("roles", {}) or {}
    role_cfg: Dict[str, Any] = roles_cfg.get(role, {}) or {}

    provider_cfg: Dict[str, Any] = cfg.get("provider", {}) or {}
    provider = provider_cfg.get("name", "unknown")

    model = provider_cfg.get("model", "unknown")

    if "provider" in role_cfg and role_cfg.get("provider"):
        provider = role_cfg["provider"]

    if "model" in role_cfg and role_cfg.get("model"):
        model = role_cfg["model"]

    return f"{provider}:{model}"
