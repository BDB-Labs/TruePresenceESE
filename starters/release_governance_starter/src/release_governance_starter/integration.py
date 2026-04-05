"""Evidence integration for the release-governance starter."""

from __future__ import annotations

import json
from pathlib import Path

from ese.integrations import (
    INTEGRATION_CONTRACT_VERSION,
    PUBLISH_STATUS_DRY_RUN,
    PUBLISH_STATUS_PUBLISHED,
    IntegrationDefinition,
    IntegrationPublishResult,
)


def _resolve_target(artifacts_dir: str, target: str | None) -> Path:
    if target:
        destination = Path(target).expanduser()
        if destination.is_absolute():
            return destination.resolve()
        return (Path(artifacts_dir) / destination).resolve()
    return (Path(artifacts_dir) / "release-governance-evidence").resolve()


def _publish_packet(context, request):
    target_dir = _resolve_target(context.artifacts_dir, request.target)
    packet_path = target_dir / "approval_packet.json"
    summary_path = target_dir / "go_live_summary.md"
    outputs = (str(packet_path), str(summary_path))

    if request.dry_run:
        return IntegrationPublishResult(
            integration_key="release-governance-bundle",
            status=PUBLISH_STATUS_DRY_RUN,
            location=str(target_dir),
            message="Previewed release-governance evidence bundle.",
            outputs=outputs,
        )

    report = dict(context.report)
    target_dir.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(
        json.dumps(
            {
                "run_id": report.get("run_id"),
                "scope": report.get("scope"),
                "status": report.get("status"),
                "assurance_level": report.get("assurance_level"),
                "blockers": report.get("blockers", []),
                "suggested_actions": report.get("suggested_actions", []),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        "\n".join(
            [
                "# Go-Live Summary",
                "",
                f"- Scope: {report.get('scope') or 'No scope recorded.'}",
                f"- Status: {report.get('status') or 'unknown'}",
                f"- Assurance: {report.get('assurance_level') or 'unknown'}",
                f"- Blockers: {len(report.get('blockers', []))}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return IntegrationPublishResult(
        integration_key="release-governance-bundle",
        status=PUBLISH_STATUS_PUBLISHED,
        location=str(target_dir),
        message="Published release-governance evidence bundle.",
        outputs=outputs,
    )


def load_integration():
    """Return the release-governance evidence integration."""
    return IntegrationDefinition(
        key="release-governance-bundle",
        title="Release Governance Bundle",
        summary="Write a portable approval packet and launch summary to disk.",
        publish=_publish_packet,
        contract_version=INTEGRATION_CONTRACT_VERSION,
    )
