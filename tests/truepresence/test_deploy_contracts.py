from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from truepresence.main import app


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
