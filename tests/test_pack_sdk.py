from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ese.cli import app
from ese.pack_sdk import (
    describe_pack_project,
    load_pack_definition_from_manifest,
    scaffold_pack_project,
    smoke_test_pack_project,
)

runner = CliRunner()
EXAMPLE_PACK_DIR = Path("examples/release_ops_pack")


def test_scaffold_pack_project_creates_valid_manifest_and_loader(tmp_path: Path) -> None:
    project_dir = tmp_path / "release_ops_pack"
    project = scaffold_pack_project(
        project_dir,
        pack_key="release-ops",
        preset="strict",
    )

    manifest_path = project_dir / "src" / "release_ops_pack" / "ese_pack.yaml"
    assert project.manifest_path == manifest_path.resolve()
    assert manifest_path.exists()

    pack = load_pack_definition_from_manifest(manifest_path)
    assert pack.key == "release-ops"
    assert pack.contract_version == 1
    assert len(pack.roles) == 2


def test_smoke_test_pack_project_generates_valid_config(tmp_path: Path) -> None:
    project_dir = tmp_path / "release_ops_pack"
    scaffold_pack_project(
        project_dir,
        pack_key="release-ops",
        preset="strict",
    )

    report = smoke_test_pack_project(project_dir)

    assert report["pack_key"] == "release-ops"
    assert report["provider"] == "openai"
    assert report["config"]["install_profile"]["pack"] == "release-ops"
    assert report["config"]["runtime"]["adapter"] == "dry-run"


def test_example_pack_project_is_valid_and_smoke_testable() -> None:
    report = describe_pack_project(EXAMPLE_PACK_DIR)
    smoke = smoke_test_pack_project(EXAMPLE_PACK_DIR)

    assert report["pack_key"] == "release-ops"
    assert report["role_count"] == 2
    assert smoke["config"]["role_order"] == ["release_planner", "release_reviewer"]


def test_pack_cli_init_validate_and_test_commands(tmp_path: Path) -> None:
    project_dir = tmp_path / "ops_pack"

    init_result = runner.invoke(
        app,
        [
            "pack",
            "init",
            str(project_dir),
            "--key",
            "release-ops",
            "--preset",
            "strict",
        ],
    )
    assert init_result.exit_code == 0
    assert "Scaffolded external pack" in init_result.stdout

    validate_result = runner.invoke(app, ["pack", "validate", str(project_dir), "--json"])
    assert validate_result.exit_code == 0
    validation_payload = json.loads(validate_result.stdout)
    assert validation_payload["pack_key"] == "release-ops"

    test_result = runner.invoke(app, ["pack", "test", str(project_dir), "--json"])
    assert test_result.exit_code == 0
    smoke_payload = json.loads(test_result.stdout)
    assert smoke_payload["pack_key"] == "release-ops"
    assert smoke_payload["config"]["install_profile"]["kind"] == "pack"
