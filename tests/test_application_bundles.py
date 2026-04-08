from __future__ import annotations

from ese.application_bundles import (
    ApplicationBundleDefinition,
    discover_application_bundles,
    load_application_bundle_from_manifest,
    resolve_application_bundle,
)


class _EntryPoint:
    def __init__(self, name: str, value):
        self.name = name
        self._value = value

    def load(self):
        return self._value


def test_load_application_bundle_from_manifest_maps_bundle_contract() -> None:
    bundle = load_application_bundle_from_manifest(
        "starters/release_governance_starter/src/release_governance_starter/ese_application.yaml"
    )

    assert bundle.key == "release-governance"
    assert bundle.pack_key == "release-governance"
    assert bundle.policy_checks == ("release-governance-safety",)
    assert bundle.integrations == ("release-governance-bundle",)


def test_discover_application_bundles_loads_entry_points(monkeypatch) -> None:
    monkeypatch.setattr(
        "ese.application_bundles._application_bundle_entry_points",
        lambda: [
            _EntryPoint(
                "release_governance_application",
                lambda: {
                    "key": "release-governance",
                    "title": "Release Governance",
                    "summary": "Bundle for release workflows.",
                    "package_name": "release_governance_starter",
                    "pack_key": "release-governance",
                    "policy_checks": ["release-governance-safety"],
                    "report_exporters": ["release-gate-csv"],
                    "artifact_views": ["go-live-brief"],
                    "integrations": ["release-governance-bundle"],
                },
            )
        ],
    )

    bundles, failures = discover_application_bundles()

    assert failures == []
    assert len(bundles) == 1
    assert bundles[0].key == "release-governance"
    assert bundles[0].pack_key == "release-governance"


def test_discover_application_bundles_rejects_unsupported_contract_version(monkeypatch) -> None:
    monkeypatch.setattr(
        "ese.application_bundles._application_bundle_entry_points",
        lambda: [
            _EntryPoint(
                "release_governance_application",
                {
                    "key": "release-governance",
                    "title": "Release Governance",
                    "summary": "Bundle for release workflows.",
                    "package_name": "release_governance_starter",
                    "pack_key": "release-governance",
                    "contract_version": 99,
                },
            )
        ],
    )

    bundles, failures = discover_application_bundles()

    assert bundles == []
    assert len(failures) == 1
    assert "expected 1" in failures[0].error


def test_resolve_application_bundle_returns_known_bundle(monkeypatch) -> None:
    monkeypatch.setattr(
        "ese.application_bundles.list_application_bundles",
        lambda: [
            ApplicationBundleDefinition(
                key="release-governance",
                title="Release Governance",
                summary="Bundle for release workflows.",
                package_name="release_governance_starter",
                pack_key="release-governance",
            )
        ],
    )

    bundle = resolve_application_bundle("release-governance")

    assert bundle.title == "Release Governance"
