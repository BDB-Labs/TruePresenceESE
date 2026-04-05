"""Artifact views for the release-governance starter."""

from __future__ import annotations

from ese.artifact_views import ArtifactViewDefinition


def _render_go_live_brief(report: dict) -> str:
    blockers = report.get("blockers", [])
    next_steps = report.get("next_steps", [])
    lines = [
        "# Go-Live Brief",
        "",
        f"- Scope: {report.get('scope') or 'No scope recorded.'}",
        f"- Status: {report.get('status') or 'unknown'}",
        f"- Assurance: {report.get('assurance_level') or 'unknown'}",
        f"- Blockers: {len(blockers)}",
        "",
        "## Required Checks",
        "",
        "- Confirm rollback owner and rollback path.",
        "- Confirm monitoring and alert routing.",
        "- Confirm deploy window, communication, and approval state.",
    ]
    if blockers:
        lines.extend(["", "## Blockers", ""])
        for blocker in blockers[:5]:
            lines.append(f"- {blocker.get('role')}: {blocker.get('title')}")
    if next_steps:
        lines.extend(["", "## Immediate Next Steps", ""])
        for step in next_steps[:5]:
            lines.append(f"- {step.get('role')}: {step.get('text')}")
    return "\n".join(lines) + "\n"


def load_view():
    """Return the starter go-live brief view."""
    return ArtifactViewDefinition(
        key="go-live-brief",
        title="Go-Live Brief",
        summary="Condensed release-governance brief for launch review.",
        format="md",
        render=_render_go_live_brief,
    )
