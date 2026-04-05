"""Artifact views for the architecture-review starter."""

from __future__ import annotations

from ese.artifact_views import ArtifactViewDefinition


def _render_decision_brief(report: dict) -> str:
    lines = [
        "# Architecture Decision Brief",
        "",
        f"- Scope: {report.get('scope') or 'No scope recorded.'}",
        f"- Status: {report.get('status') or 'unknown'}",
        f"- Assurance: {report.get('assurance_level') or 'unknown'}",
    ]
    blockers = report.get("blockers", [])
    if blockers:
        lines.extend(["", "## Risks", ""])
        for blocker in blockers[:5]:
            lines.append(f"- {blocker.get('severity')}: {blocker.get('title')}")
    recurring_unknowns = report.get("recurring_unknowns", [])
    if recurring_unknowns:
        lines.extend(["", "## Recurring Unknowns", ""])
        for unknown in recurring_unknowns[:5]:
            lines.append(f"- {unknown.get('text')}")
    return "\n".join(lines) + "\n"


def load_view():
    """Return the architecture decision brief view."""
    return ArtifactViewDefinition(
        key="decision-brief",
        title="Decision Brief",
        summary="Condensed architecture decision brief for migration and interface reviews.",
        format="md",
        render=_render_decision_brief,
    )
