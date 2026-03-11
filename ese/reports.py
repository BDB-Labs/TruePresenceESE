"""Helpers for loading and summarizing ESE run artifacts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

SEVERITY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
DEFAULT_HISTORY_LIMIT = 8
MAX_ARTIFACT_VIEW_CHARS = 200_000


class RunReportError(ValueError):
    """Raised when a run report cannot be loaded from artifacts."""


def _state_path(artifacts_dir: str | Path) -> Path:
    return Path(artifacts_dir) / "pipeline_state.json"


def _is_run_dir(path: Path) -> bool:
    return _state_path(path).is_file()


def _history_root(path: Path) -> Path:
    return path.parent if _is_run_dir(path) else path


def _timestamp_for(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as err:
        raise RunReportError(f"Required run artifact not found: {path}") from err
    except json.JSONDecodeError as err:
        raise RunReportError(f"Run artifact is not valid JSON: {path}") from err

    if not isinstance(parsed, dict):
        raise RunReportError(f"Run artifact must be a JSON object: {path}")
    return parsed


def load_pipeline_state(artifacts_dir: str) -> dict[str, Any]:
    path = _state_path(artifacts_dir)
    return _read_json(path)


def load_role_report(artifact_path: str) -> dict[str, Any] | None:
    path = Path(artifact_path)
    if path.suffix.lower() != ".json":
        return None
    return _read_json(path)


def _document_entries(root: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    config_snapshot = str(state.get("config_snapshot") or "").strip()

    candidates = [
        ("summary", "Summary", root / "ese_summary.md"),
        ("pr_review", "PR Review", root / "pr_review.md"),
    ]
    if config_snapshot:
        candidates.insert(1, ("config_snapshot", "Config Snapshot", Path(config_snapshot)))
    seen: set[str] = set()
    for key, title, path in candidates:
        if not str(path):
            continue
        resolved = path if path.is_absolute() else root / path
        if not resolved.exists():
            continue
        normalized = str(resolved)
        if normalized in seen:
            continue
        seen.add(normalized)
        documents.append(
            {
                "key": key,
                "title": title,
                "path": normalized,
                "format": resolved.suffix.lower().lstrip(".") or "txt",
            },
        )
    return documents


def collect_run_report(artifacts_dir: str) -> dict[str, Any]:
    root = Path(artifacts_dir)
    state = load_pipeline_state(str(root))
    roles: list[dict[str, Any]] = []
    severity_counts = {severity: 0 for severity in SEVERITY_ORDER}
    blockers: list[dict[str, Any]] = []
    next_steps: list[dict[str, str]] = []

    for item in state.get("execution", []):
        if not isinstance(item, dict):
            continue

        role = str(item.get("role") or "").strip()
        artifact = str(item.get("artifact") or "").strip()
        if not role or not artifact:
            continue

        artifact_path = Path(artifact)
        if not artifact_path.is_absolute():
            artifact_path = root / artifact_path

        entry: dict[str, Any] = {
            "role": role,
            "model": str(item.get("model") or ""),
            "artifact": str(artifact_path),
            "summary": "",
            "findings": [],
            "next_steps": [],
            "artifacts": [],
            "report_format": artifact_path.suffix.lower().lstrip("."),
        }

        report = load_role_report(str(artifact_path))
        if report is None:
            entry["summary"] = artifact_path.read_text(encoding="utf-8")[:500].strip()
            roles.append(entry)
            continue

        entry["summary"] = str(report.get("summary") or "").strip()
        entry["findings"] = report.get("findings") if isinstance(report.get("findings"), list) else []
        entry["next_steps"] = [step for step in report.get("next_steps", []) if isinstance(step, str) and step.strip()]
        entry["artifacts"] = [step for step in report.get("artifacts", []) if isinstance(step, str) and step.strip()]

        for finding in entry["findings"]:
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("severity") or "").upper()
            if severity in severity_counts:
                severity_counts[severity] += 1
            if severity in {"HIGH", "CRITICAL"}:
                blockers.append(
                    {
                        "role": role,
                        "severity": severity,
                        "title": str(finding.get("title") or "").strip(),
                        "details": str(finding.get("details") or "").strip(),
                    },
                )

        for step in entry["next_steps"]:
            next_steps.append({"role": role, "text": step})

        roles.append(entry)

    finding_count = sum(severity_counts.values())
    documents = _document_entries(root, state)
    state_path = _state_path(root)
    return {
        "artifacts_dir": str(root),
        "state": state,
        "status": state.get("status", "unknown"),
        "scope": state.get("scope", ""),
        "provider": state.get("provider", ""),
        "adapter": state.get("adapter", ""),
        "config_snapshot": state.get("config_snapshot"),
        "updated_at": _timestamp_for(state_path),
        "summary_path": str(root / "ese_summary.md"),
        "documents": documents,
        "failure": state.get("failure"),
        "roles": roles,
        "severity_counts": severity_counts,
        "finding_count": finding_count,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "next_steps": next_steps,
    }


def list_recent_runs(artifacts_dir: str, limit: int = DEFAULT_HISTORY_LIMIT) -> list[dict[str, Any]]:
    requested = Path(artifacts_dir)
    root = _history_root(requested)
    candidates: set[Path] = set()

    if _is_run_dir(requested):
        candidates.add(requested)
    if _is_run_dir(root):
        candidates.add(root)
    if root.exists():
        for child in root.iterdir():
            if child.is_dir() and _is_run_dir(child):
                candidates.add(child)

    runs: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            report = collect_run_report(str(candidate))
        except RunReportError:
            continue
        runs.append(
            {
                "artifacts_dir": str(candidate),
                "status": report.get("status", "unknown"),
                "scope": report.get("scope", ""),
                "provider": report.get("provider", ""),
                "adapter": report.get("adapter", ""),
                "updated_at": report.get("updated_at"),
                "finding_count": report.get("finding_count", 0),
                "blocker_count": report.get("blocker_count", 0),
                "role_count": len(report.get("roles", [])),
                "documents": report.get("documents", []),
                "failure": report.get("failure"),
            },
        )

    runs.sort(
        key=lambda item: _state_path(item["artifacts_dir"]).stat().st_mtime,
        reverse=True,
    )
    return runs[:limit]


def load_artifact_view(
    artifacts_dir: str,
    *,
    role: str | None = None,
    document: str | None = None,
    max_chars: int = MAX_ARTIFACT_VIEW_CHARS,
) -> dict[str, Any]:
    if bool(role) == bool(document):
        raise RunReportError("Select exactly one artifact target: role or document.")

    report = collect_run_report(artifacts_dir)
    if role:
        match = next((item for item in report.get("roles", []) if item.get("role") == role), None)
        if match is None:
            raise RunReportError(f"No artifact found for role '{role}'.")
        path = Path(str(match["artifact"]))
        content = path.read_text(encoding="utf-8")
        truncated = len(content) > max_chars
        return {
            "kind": "role",
            "key": role,
            "title": f"{role} Artifact",
            "path": str(path),
            "format": match.get("report_format", path.suffix.lower().lstrip(".")),
            "content": content[:max_chars],
            "truncated": truncated,
            "summary": match.get("summary", ""),
            "findings": match.get("findings", []),
            "next_steps": match.get("next_steps", []),
        }

    doc = next((item for item in report.get("documents", []) if item.get("key") == document), None)
    if doc is None:
        raise RunReportError(f"No document found for key '{document}'.")
    path = Path(str(doc["path"]))
    content = path.read_text(encoding="utf-8")
    truncated = len(content) > max_chars
    return {
        "kind": "document",
        "key": document,
        "title": doc.get("title", document or "Artifact"),
        "path": str(path),
        "format": doc.get("format", path.suffix.lower().lstrip(".")),
        "content": content[:max_chars],
        "truncated": truncated,
    }


def render_status_text(report: dict[str, Any]) -> str:
    executed = len(report.get("roles", []))
    counts = report.get("severity_counts", {})
    severity_line = ", ".join(
        f"{severity.lower()}={counts.get(severity, 0)}"
        for severity in SEVERITY_ORDER
    )
    lines = [
        f"Status: {report.get('status', 'unknown')}",
        f"Provider: {report.get('provider', 'unknown')} ({report.get('adapter', 'unknown')})",
        f"Executed roles: {executed}",
        f"Findings: {report.get('finding_count', 0)} ({severity_line})",
        f"Blockers: {report.get('blocker_count', 0)}",
    ]
    scope = str(report.get("scope") or "").strip()
    if scope:
        lines.insert(1, f"Scope: {scope}")
    return "\n".join(lines)


def render_report_text(report: dict[str, Any]) -> str:
    lines = [
        render_status_text(report),
        "",
        "Roles:",
    ]
    for role in report.get("roles", []):
        lines.append(
            f"- {role['role']} ({role['model']}): {role['summary'] or 'No summary provided.'}",
        )
        for finding in role.get("findings", []):
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("severity") or "").upper() or "UNKNOWN"
            title = str(finding.get("title") or "").strip() or "Untitled finding"
            lines.append(f"  {severity}: {title}")

    blockers = report.get("blockers", [])
    if blockers:
        lines.extend(["", "Blockers:"])
        for blocker in blockers:
            lines.append(
                f"- {blocker['role']} [{blocker['severity']}]: {blocker['title']}",
            )

    next_steps = report.get("next_steps", [])
    if next_steps:
        lines.extend(["", "Next steps:"])
        for item in next_steps:
            lines.append(f"- {item['role']}: {item['text']}")

    return "\n".join(lines)
