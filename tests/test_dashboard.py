from __future__ import annotations

from pathlib import Path

from ese.dashboard import _allocate_run_artifacts_dir


def test_allocate_run_artifacts_dir_uses_requested_root(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"

    allocated = _allocate_run_artifacts_dir(str(root), kind="task-run")

    assert Path(allocated).parent == root
    assert Path(allocated).name.endswith("task-run")


def test_allocate_run_artifacts_dir_uses_parent_for_existing_run_dir(tmp_path: Path) -> None:
    existing_run = tmp_path / "artifacts" / "20260308-task-run"
    existing_run.mkdir(parents=True)
    (existing_run / "pipeline_state.json").write_text("{}", encoding="utf-8")

    allocated = _allocate_run_artifacts_dir(str(existing_run), kind="task-run")

    assert Path(allocated).parent == existing_run.parent
    assert Path(allocated) != existing_run
