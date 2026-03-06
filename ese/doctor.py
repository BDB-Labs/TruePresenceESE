"""ESE doctor checks.

Validates config and enforces ensemble role separation constraints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ese.config import ConfigValidationError, load_config, resolve_role_model, resolve_scope_text


def _collect_role_names(cfg: Dict[str, Any]) -> List[str]:
    roles: List[str] = []
    seen: set[str] = set()

    def add(role: Any) -> None:
        if not isinstance(role, str):
            return
        cleaned = role.strip()
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        roles.append(cleaned)

    for role in (cfg.get("roles") or {}).keys():
        add(role)

    constraints = cfg.get("constraints") or {}
    for pair in constraints.get("disallow_same_model_pairs") or []:
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            add(pair[0])
            add(pair[1])

    return roles


def evaluate_doctor(cfg: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, str]]:
    mode = (cfg.get("mode") or "ensemble").strip().lower()

    role_names = _collect_role_names(cfg)
    role_models = {r: resolve_role_model(cfg, r) for r in role_names}

    constraints = cfg.get("constraints") or {}
    pairs = constraints.get("disallow_same_model_pairs") or []

    violations: List[str] = []
    if not resolve_scope_text(cfg):
        violations.append("No project scope supplied. Set input.scope in the config or pass --scope.")

    for a, b in pairs:
        if role_models.get(a) == role_models.get(b):
            violations.append(f"{a} and {b} share model {role_models[a]}")

    if violations:
        return False, violations, role_models

    if mode == "solo":
        return True, ["SOLO MODE: reduced independence; higher self-confirmation risk."], role_models

    return True, [], role_models


def run_doctor(config_path: str) -> Tuple[bool, List[str], Dict[str, str]]:
    try:
        cfg = load_config(config_path)
    except ConfigValidationError as err:
        return False, [str(err)], {}

    return evaluate_doctor(cfg)
