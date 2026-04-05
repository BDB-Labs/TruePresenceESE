"""Exporters for the architecture-review starter."""

from __future__ import annotations

import csv
import io

from ese.report_exporters import ReportExporterDefinition


def _render_architecture_risk_csv(report: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["role", "severity", "title", "details"])
    for blocker in report.get("blockers", []):
        writer.writerow(
            [
                blocker.get("role", ""),
                blocker.get("severity", ""),
                blocker.get("title", ""),
                blocker.get("details", ""),
            ]
        )
    return buffer.getvalue()


def load_exporter():
    """Return the architecture risk register CSV exporter."""
    return ReportExporterDefinition(
        key="architecture-risk-csv",
        title="Architecture Risk CSV",
        summary="CSV export of architecture blockers and risks.",
        content_type="text/csv; charset=utf-8",
        default_filename="architecture_risks.csv",
        render=_render_architecture_risk_csv,
    )
