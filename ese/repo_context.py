"""Repository-grounded context helpers for task-first ESE runs."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ese.diff_context import build_file_aware_diff_excerpt

MAX_UNTRACKED_PREVIEW_CHARS = 1200


class RepoContextError(ValueError):
    """Raised when repository context cannot be assembled."""


def _run_command(args: list[str], *, cwd: str) -> str:
    try:
        completed = subprocess.run(  # noqa: S603
            args,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as err:
        raise RepoContextError(f"Required command not found: {args[0]}") from err
    except subprocess.CalledProcessError as err:
        stderr = (err.stderr or "").strip()
        stdout = (err.stdout or "").strip()
        detail = stderr or stdout or f"{args[0]} exited with status {err.returncode}"
        raise RepoContextError(detail) from err
    return completed.stdout.strip()


def _git(repo_path: str, *args: str) -> str:
    return _run_command(["git", *args], cwd=repo_path)


def _truncate(text: str, limit: int) -> tuple[str, bool, int, int]:
    if limit <= 0:
        raise RepoContextError("max_diff_chars must be > 0")
    excerpt = build_file_aware_diff_excerpt(
        text,
        limit=limit,
        truncated_label="repository diff truncated by ESE",
    )
    return (
        excerpt.text,
        excerpt.truncated,
        excerpt.included_file_patches,
        excerpt.total_file_patches,
    )


def build_repo_context(
    *,
    repo_path: str = ".",
    include_status: bool = True,
    include_diff: bool = True,
    max_diff_chars: int = 8000,
) -> dict[str, Any]:
    """Collect lightweight repo context for a task-oriented run."""
    repo_root_path = Path(_git(repo_path, "rev-parse", "--show-toplevel"))
    repo_root = str(repo_root_path)
    branch = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    status = _git(repo_root, "status", "--short") if include_status else ""
    diffstat = _git(repo_root, "diff", "--stat", "--find-renames", "HEAD") if include_diff else ""
    changed_files = _git(repo_root, "diff", "--name-status", "--find-renames", "HEAD") if include_diff else ""
    patch_raw = _git(repo_root, "diff", "--no-color", "--find-renames", "HEAD") if include_diff else ""
    untracked_files = (
        [line for line in _git(repo_root, "ls-files", "--others", "--exclude-standard").splitlines() if line.strip()]
        if include_diff
        else []
    )
    if include_diff and patch_raw:
        patch, patch_truncated, included_patch_files, total_patch_files = _truncate(
            patch_raw,
            max_diff_chars,
        )
    else:
        patch, patch_truncated, included_patch_files, total_patch_files = "", False, 0, 0

    untracked_previews: dict[str, str] = {}
    remaining_chars = max(0, max_diff_chars - len(patch))
    if include_diff and untracked_files and remaining_chars > 0:
        for relative_path in untracked_files:
            if remaining_chars <= 0:
                break
            file_path = repo_root_path / relative_path
            if not file_path.is_file():
                continue
            try:
                preview = file_path.read_text(encoding="utf-8", errors="ignore").strip()
            except OSError:
                continue
            if not preview:
                continue
            preview = preview[: min(remaining_chars, MAX_UNTRACKED_PREVIEW_CHARS)]
            untracked_previews[relative_path] = preview
            remaining_chars -= len(preview)

    return {
        "repo_path": repo_root,
        "branch": branch,
        "status": status,
        "diffstat": diffstat,
        "changed_files": changed_files,
        "patch": patch,
        "patch_truncated": patch_truncated,
        "included_patch_files": included_patch_files,
        "total_patch_files": total_patch_files,
        "max_diff_chars": max_diff_chars,
        "untracked_files": untracked_files,
        "untracked_previews": untracked_previews,
    }


def render_repo_context(context: dict[str, Any]) -> str:
    """Render repo context into additional prompt text."""
    lines = [
        "Repository context for this task run:",
        f"Repository: {context.get('repo_path', '.')}",
        f"Branch: {context.get('branch', 'unknown')}",
    ]
    status = str(context.get("status") or "").strip()
    changed_files = str(context.get("changed_files") or "").strip()
    diffstat = str(context.get("diffstat") or "").strip()
    patch = str(context.get("patch") or "").strip()
    untracked_files = [item for item in context.get("untracked_files", []) if isinstance(item, str) and item.strip()]
    raw_previews = context.get("untracked_previews")
    untracked_previews = raw_previews if isinstance(raw_previews, dict) else {}
    if status:
        lines.extend(["", "Git status:", status])
    if diffstat:
        lines.extend(["", "Diffstat:", diffstat])
    if changed_files:
        lines.extend(["", "Changed files:", changed_files])
    if untracked_files:
        lines.extend(["", "Untracked files:"])
        lines.extend(f"- {path}" for path in untracked_files)
    if patch:
        header = "Unified diff:"
        if bool(context.get("patch_truncated")):
            included = int(context.get("included_patch_files") or 0)
            total = int(context.get("total_patch_files") or 0)
            header = (
                f"Unified diff (truncated to {context.get('max_diff_chars')} chars; "
                f"included {included} of {total} file patches):"
            )
        lines.extend(["", header, patch])
    for path in untracked_files:
        preview = str(untracked_previews.get(path) or "").strip()
        if preview:
            lines.extend(["", f"Untracked file preview: {path}", preview])
    return "\n".join(lines).strip()
