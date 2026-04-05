"""Registry of supported ESE extension surfaces."""

from __future__ import annotations

from dataclasses import dataclass

from ese.artifact_views import (
    ARTIFACT_VIEW_CONTRACT_VERSION,
    ARTIFACT_VIEW_ENTRY_POINT_GROUP,
)
from ese.config_packs import CONFIG_PACK_CONTRACT_VERSION, CONFIG_PACK_ENTRY_POINT_GROUP
from ese.integrations import INTEGRATION_CONTRACT_VERSION, INTEGRATION_ENTRY_POINT_GROUP
from ese.policy_checks import (
    POLICY_CHECK_CONTRACT_VERSION,
    POLICY_CHECK_ENTRY_POINT_GROUP,
)
from ese.report_exporters import (
    REPORT_EXPORTER_CONTRACT_VERSION,
    REPORT_EXPORTER_ENTRY_POINT_GROUP,
)


@dataclass(frozen=True)
class ExtensionSurfaceDefinition:
    key: str
    title: str
    entry_point_group: str
    contract_version: int


def list_extension_surfaces() -> list[ExtensionSurfaceDefinition]:
    return [
        ExtensionSurfaceDefinition(
            key="config-packs",
            title="Config Packs",
            entry_point_group=CONFIG_PACK_ENTRY_POINT_GROUP,
            contract_version=CONFIG_PACK_CONTRACT_VERSION,
        ),
        ExtensionSurfaceDefinition(
            key="policy-checks",
            title="Policy Checks",
            entry_point_group=POLICY_CHECK_ENTRY_POINT_GROUP,
            contract_version=POLICY_CHECK_CONTRACT_VERSION,
        ),
        ExtensionSurfaceDefinition(
            key="report-exporters",
            title="Report Exporters",
            entry_point_group=REPORT_EXPORTER_ENTRY_POINT_GROUP,
            contract_version=REPORT_EXPORTER_CONTRACT_VERSION,
        ),
        ExtensionSurfaceDefinition(
            key="artifact-views",
            title="Artifact Views",
            entry_point_group=ARTIFACT_VIEW_ENTRY_POINT_GROUP,
            contract_version=ARTIFACT_VIEW_CONTRACT_VERSION,
        ),
        ExtensionSurfaceDefinition(
            key="integrations",
            title="Integrations",
            entry_point_group=INTEGRATION_ENTRY_POINT_GROUP,
            contract_version=INTEGRATION_CONTRACT_VERSION,
        ),
    ]
