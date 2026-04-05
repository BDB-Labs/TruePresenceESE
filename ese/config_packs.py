"""Discovery helpers for externally installed ESE config packs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import metadata
from typing import Any

CONFIG_PACK_ENTRY_POINT_GROUP = "ese.config_packs"
CONFIG_PACK_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class PackRoleDefinition:
    key: str
    responsibility: str
    prompt: str
    temperature: float = 0.2


@dataclass(frozen=True)
class ConfigPackDefinition:
    key: str
    title: str
    summary: str
    preset: str
    goal_profile: str
    roles: tuple[PackRoleDefinition, ...]
    contract_version: int = CONFIG_PACK_CONTRACT_VERSION


def _config_pack_entry_points() -> list[Any]:
    discovered = metadata.entry_points()
    if hasattr(discovered, "select"):
        return list(discovered.select(group=CONFIG_PACK_ENTRY_POINT_GROUP))
    return list(discovered.get(CONFIG_PACK_ENTRY_POINT_GROUP, []))


def _normalize_non_empty(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _normalize_contract_version(value: Any) -> int:
    if value is None:
        return CONFIG_PACK_CONTRACT_VERSION
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("config pack contract_version must be an integer")
    if value != CONFIG_PACK_CONTRACT_VERSION:
        raise ValueError(
            "config pack contract_version "
            f"{value} is not supported by this ESE build; expected {CONFIG_PACK_CONTRACT_VERSION}"
        )
    return value


def _normalize_role_definition(value: Any) -> PackRoleDefinition:
    if isinstance(value, PackRoleDefinition):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("Pack roles must be PackRoleDefinition instances or mappings")
    return PackRoleDefinition(
        key=_normalize_non_empty(value.get("key"), label="pack role key"),
        responsibility=_normalize_non_empty(value.get("responsibility"), label="pack role responsibility"),
        prompt=_normalize_non_empty(value.get("prompt"), label="pack role prompt"),
        temperature=float(value.get("temperature", 0.2)),
    )


def normalize_config_pack_definition(value: Any) -> ConfigPackDefinition:
    if isinstance(value, ConfigPackDefinition):
        roles = value.roles
        contract_version = value.contract_version
        payload: Mapping[str, Any] = {
            "key": value.key,
            "title": value.title,
            "summary": value.summary,
            "preset": value.preset,
            "goal_profile": value.goal_profile,
            "roles": roles,
            "contract_version": contract_version,
        }
    elif isinstance(value, Mapping):
        payload = value
    else:
        raise TypeError("Config pack providers must return ConfigPackDefinition instances or mappings")

    raw_roles = payload.get("roles")
    if not isinstance(raw_roles, Iterable) or isinstance(raw_roles, (str, bytes)):
        raise ValueError("config pack roles must be an iterable of role definitions")

    normalized_roles = tuple(_normalize_role_definition(role) for role in raw_roles)
    if not normalized_roles:
        raise ValueError("config pack roles must not be empty")
    seen_role_keys: set[str] = set()
    for role in normalized_roles:
        if role.key in seen_role_keys:
            raise ValueError(f"config pack roles contain duplicate key '{role.key}'")
        seen_role_keys.add(role.key)

    return ConfigPackDefinition(
        key=_normalize_non_empty(payload.get("key"), label="config pack key").lower(),
        title=_normalize_non_empty(payload.get("title"), label="config pack title"),
        summary=_normalize_non_empty(payload.get("summary"), label="config pack summary"),
        preset=_normalize_non_empty(payload.get("preset"), label="config pack preset"),
        goal_profile=_normalize_non_empty(payload.get("goal_profile"), label="config pack goal profile"),
        roles=normalized_roles,
        contract_version=_normalize_contract_version(payload.get("contract_version")),
    )


def _iter_loaded_pack_definitions(value: Any) -> Iterable[ConfigPackDefinition]:
    if isinstance(value, (ConfigPackDefinition, Mapping)):
        yield normalize_config_pack_definition(value)
        return

    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        for item in value:
            yield normalize_config_pack_definition(item)
        return

    raise TypeError("Config pack providers must return a pack definition or an iterable of definitions")


def list_config_packs() -> list[ConfigPackDefinition]:
    packs_by_key: dict[str, ConfigPackDefinition] = {}
    for entry_point in _config_pack_entry_points():
        try:
            loaded = entry_point.load()
            for pack in _iter_loaded_pack_definitions(loaded):
                packs_by_key.setdefault(pack.key, pack)
        except Exception:
            continue
    return [packs_by_key[key] for key in sorted(packs_by_key)]


def get_config_pack(key: str) -> ConfigPackDefinition:
    clean_key = (key or "").strip().lower()
    for pack in list_config_packs():
        if pack.key == clean_key:
            return pack
    raise KeyError(
        f"Unknown config pack '{key}'. Install a pack exposing the '{CONFIG_PACK_ENTRY_POINT_GROUP}' entry point group."
    )
