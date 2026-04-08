"""Discovery helpers for installed ESE application bundles."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from ese.extension_contracts import normalize_contract_version, normalize_non_empty
from ese.starter_sdk import (
    STARTER_CONTRACT_VERSION,
    load_starter_project,
)

APPLICATION_BUNDLE_ENTRY_POINT_GROUP = "ese.application_bundles"
APPLICATION_BUNDLE_CONTRACT_VERSION = STARTER_CONTRACT_VERSION


@dataclass(frozen=True)
class ApplicationBundleDefinition:
    key: str
    title: str
    summary: str
    package_name: str
    pack_key: str
    policy_checks: tuple[str, ...] = ()
    report_exporters: tuple[str, ...] = ()
    artifact_views: tuple[str, ...] = ()
    integrations: tuple[str, ...] = ()
    contract_version: int = APPLICATION_BUNDLE_CONTRACT_VERSION


@dataclass(frozen=True)
class ApplicationBundleLoadFailure:
    entry_point: str
    error: str


def _application_bundle_entry_points() -> list[Any]:
    discovered = metadata.entry_points()
    if hasattr(discovered, "select"):
        return list(discovered.select(group=APPLICATION_BUNDLE_ENTRY_POINT_GROUP))
    return list(discovered.get(APPLICATION_BUNDLE_ENTRY_POINT_GROUP, []))


def _normalize_keys(value: Any, *, label: str) -> tuple[str, ...]:
    if value in (None, []):
        return ()
    if isinstance(value, (str, bytes)):
        return (normalize_non_empty(value, label=label),)
    if not isinstance(value, Iterable):
        raise ValueError(f"{label} must be a list of keys")
    keys: list[str] = []
    for item in value:
        keys.append(normalize_non_empty(item, label=label))
    return tuple(keys)


def _normalize_application_bundle_definition(value: Any, *, fallback_key: str) -> ApplicationBundleDefinition:
    if isinstance(value, ApplicationBundleDefinition):
        definition = value
    elif callable(value):
        loaded = value()
        return _normalize_application_bundle_definition(loaded, fallback_key=fallback_key)
    elif isinstance(value, Mapping):
        definition = ApplicationBundleDefinition(
            key=normalize_non_empty(value.get("key") or fallback_key, label="application bundle key"),
            title=normalize_non_empty(value.get("title"), label="application bundle title"),
            summary=normalize_non_empty(value.get("summary"), label="application bundle summary"),
            package_name=normalize_non_empty(value.get("package_name"), label="application bundle package_name"),
            pack_key=normalize_non_empty(value.get("pack_key"), label="application bundle pack_key"),
            policy_checks=_normalize_keys(value.get("policy_checks"), label="application bundle policy check"),
            report_exporters=_normalize_keys(
                value.get("report_exporters"),
                label="application bundle report exporter",
            ),
            artifact_views=_normalize_keys(
                value.get("artifact_views"),
                label="application bundle artifact view",
            ),
            integrations=_normalize_keys(value.get("integrations"), label="application bundle integration"),
            contract_version=normalize_contract_version(
                value.get("contract_version"),
                extension_name="application bundle",
                expected_version=APPLICATION_BUNDLE_CONTRACT_VERSION,
            ),
        )
    else:
        raise TypeError("Application bundles must return ApplicationBundleDefinition or a mapping")

    return ApplicationBundleDefinition(
        key=normalize_non_empty(definition.key, label="application bundle key"),
        title=normalize_non_empty(definition.title, label="application bundle title"),
        summary=normalize_non_empty(definition.summary, label="application bundle summary"),
        package_name=normalize_non_empty(definition.package_name, label="application bundle package_name"),
        pack_key=normalize_non_empty(definition.pack_key, label="application bundle pack_key"),
        policy_checks=_normalize_keys(definition.policy_checks, label="application bundle policy check"),
        report_exporters=_normalize_keys(
            definition.report_exporters,
            label="application bundle report exporter",
        ),
        artifact_views=_normalize_keys(definition.artifact_views, label="application bundle artifact view"),
        integrations=_normalize_keys(definition.integrations, label="application bundle integration"),
        contract_version=normalize_contract_version(
            definition.contract_version,
            extension_name="application bundle",
            expected_version=APPLICATION_BUNDLE_CONTRACT_VERSION,
        ),
    )


def load_application_bundle_from_manifest(path: str | Path) -> ApplicationBundleDefinition:
    project = load_starter_project(path)
    return ApplicationBundleDefinition(
        key=project.key,
        title=project.title,
        summary=project.summary,
        package_name=project.package_name,
        pack_key=project.pack_key,
        policy_checks=tuple(entry.key for entry in project.policy_checks),
        report_exporters=tuple(entry.key for entry in project.report_exporters),
        artifact_views=tuple(entry.key for entry in project.artifact_views),
        integrations=tuple(entry.key for entry in project.integrations),
        contract_version=project.contract_version,
    )


def discover_application_bundles() -> tuple[list[ApplicationBundleDefinition], list[ApplicationBundleLoadFailure]]:
    bundles_by_key: dict[str, ApplicationBundleDefinition] = {}
    failures: list[ApplicationBundleLoadFailure] = []
    for entry_point in _application_bundle_entry_points():
        entry_name = normalize_non_empty(
            getattr(entry_point, "name", "application_bundle"),
            label="entry point name",
        )
        fallback_key = entry_name.replace("_", "-").lower()
        try:
            loaded = entry_point.load()
            definition = _normalize_application_bundle_definition(loaded, fallback_key=fallback_key)
        except Exception as err:  # noqa: BLE001
            failures.append(ApplicationBundleLoadFailure(entry_point=entry_name, error=str(err)))
            continue
        bundles_by_key.setdefault(definition.key, definition)
    return [bundles_by_key[key] for key in sorted(bundles_by_key)], failures


def list_application_bundles() -> list[ApplicationBundleDefinition]:
    bundles, _failures = discover_application_bundles()
    return bundles


def resolve_application_bundle(key: str) -> ApplicationBundleDefinition:
    clean_key = normalize_non_empty(key, label="application bundle key").lower()
    for bundle in list_application_bundles():
        if bundle.key == clean_key:
            return bundle
    supported = ", ".join(bundle.key for bundle in list_application_bundles()) or "none"
    raise KeyError(f"Unknown application bundle '{key}'. Installed bundles: {supported}")
