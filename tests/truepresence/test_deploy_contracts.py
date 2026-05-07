from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("slowapi", reason="requires slowapi from the test/dev install")
pytestmark = [pytest.mark.integration, pytest.mark.rate_limit]

from truepresence.main import app  # noqa: E402


def test_render_github_actions_workflows_are_removed() -> None:
    workflows_dir = Path(".github/workflows")

    assert not (workflows_dir / "render-depoly.yml").exists()
    assert not (workflows_dir / "render-deploy.yml").exists()


def test_railway_deploy_config_uses_readiness_healthcheck() -> None:
    railway_toml = Path("railway.toml").read_text(encoding="utf-8")
    railway_json = Path("deploy/railway.json").read_text(encoding="utf-8")

    assert 'healthcheckPath = "/ready"' in railway_toml
    assert "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}" in railway_toml
    assert "localhost:${PORT:-8000}/ready" in railway_json
    assert "localhost:${PORT:-8000}/health" not in railway_json


def test_deployment_readme_matches_railway_and_vercel_targets() -> None:
    readme = Path("deploy/README.md").read_text(encoding="utf-8")

    assert "Railway hosts the Python backend" in readme
    assert "Health check path: `/ready`" in readme
    assert "Vercel hosts the Next.js dashboard" in readme
    assert "Root directory: `truepresence/ui`" in readme
    assert "TRUEPRESENCE_API_URL" in readme
    assert "## Render" not in readme


def test_vercel_dashboard_config_matches_nextjs_project() -> None:
    vercel_config = Path("truepresence/ui/vercel.json").read_text(encoding="utf-8")

    assert '"framework": "nextjs"' in vercel_config
    assert '"installCommand": "npm install"' in vercel_config
    assert '"buildCommand": "npm run build"' in vercel_config
    assert '"outputDirectory": ".next"' in vercel_config


def test_python_version_pin_matches_backend_runtime() -> None:
    assert Path(".python-version").read_text(encoding="utf-8").strip() == "3.11"


def test_dockerfile_expands_runtime_port_in_start_command() -> None:
    dockerfile = Path("deploy/Dockerfile").read_text(encoding="utf-8")

    assert '"${PORT:-8000}"' not in dockerfile
    assert 'CMD ["sh", "-c"' in dockerfile
    assert "--port ${PORT:-8000}" in dockerfile


def test_deployment_readme_lists_required_production_environment() -> None:
    readme = Path("deploy/README.md").read_text(encoding="utf-8")

    for variable in [
        "JWT_SECRET",
        "DATABASE_URL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET",
        "TRUEPRESENCE_ENCRYPTION_KEY",
    ]:
        assert variable in readme


def test_readiness_endpoint_fails_when_required_dependency_unhealthy(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
