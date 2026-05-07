import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("psycopg2", reason="requires psycopg2-binary from the test/dev install")
pytestmark = [pytest.mark.integration, pytest.mark.db, pytest.mark.telegram]

import truepresence.adapters.telegram_bot as telegram_bot  # noqa: E402


class _FakeService:
    async def process_update(self, update, tenant_id=None):
        return {"action": "allow", "confidence": 0.5, "evaluation": {}}



def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(telegram_bot.router)
    return TestClient(app)


def test_webhook_invalid_secret_returns_401(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    monkeypatch.setattr(telegram_bot, "get_service_for_tenant", lambda tenant_id: _FakeService())

    client = _build_client()
    response = client.post(
        "/telegram/webhook",
        headers={
            "X-Tenant-ID": "default",
            "X-Telegram-Bot-Api-Secret-Token": "wrong-secret",
        },
        json={"update_id": 123},
    )

    assert response.status_code == 401


def test_webhook_requires_secret_in_production(monkeypatch):
    monkeypatch.setenv("TRUEPRESENCE_ENV", "production")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(telegram_bot, "get_service_for_tenant", lambda tenant_id: _FakeService())

    client = _build_client()
    response = client.post(
        "/telegram/webhook",
        headers={"X-Tenant-ID": "default"},
        json={"update_id": 123},
    )

    assert response.status_code == 503
    assert "webhook secret is required" in response.json()["detail"].lower()


def test_observe_mode_suppresses_punitive_action(monkeypatch):
    service = telegram_bot.TelegramProtectionService.__new__(telegram_bot.TelegramProtectionService)
    monkeypatch.delenv("TELEGRAM_ENFORCEMENT_MODE", raising=False)

    action = {"action": "ban", "confidence": 0.95}
    result = service._apply_enforcement_mode(action, "default")

    assert result["action"] == "allow"
    assert result["intended_action"] == "ban"
    assert result["suppressed_action"] == "ban"
    assert result["suppression_reason"] == "telegram_enforcement_mode_observe"
    assert result["enforcement_mode"] == "observe"


def test_challenge_only_mode_downgrades_ban_to_challenge(monkeypatch):
    service = telegram_bot.TelegramProtectionService.__new__(telegram_bot.TelegramProtectionService)
    monkeypatch.setenv("TELEGRAM_ENFORCEMENT_MODE", "challenge_only")

    action = {"action": "ban", "confidence": 0.95}
    result = service._apply_enforcement_mode(action, "default")

    assert result["action"] == "challenge"
    assert result["intended_action"] == "ban"
    assert result["suppressed_action"] == "ban"
    assert result["suppression_reason"] == "telegram_enforcement_mode_challenge_only"


def test_review_required_mode_downgrades_ban_to_admin_review(monkeypatch):
    service = telegram_bot.TelegramProtectionService.__new__(telegram_bot.TelegramProtectionService)
    monkeypatch.setenv("TELEGRAM_ENFORCEMENT_MODE", "review_required")

    action = {"action": "ban", "confidence": 0.95}
    result = service._apply_enforcement_mode(action, "default")

    assert result["action"] == "alert_admin"
    assert result["intended_action"] == "ban"
    assert result["suppressed_action"] == "ban"
    assert result["suppression_reason"] == "telegram_enforcement_mode_review_required"


def test_enforce_mode_preserves_punitive_action(monkeypatch):
    service = telegram_bot.TelegramProtectionService.__new__(telegram_bot.TelegramProtectionService)
    monkeypatch.setenv("TELEGRAM_ENFORCEMENT_MODE", "enforce")

    action = {"action": "ban", "confidence": 0.95}
    result = service._apply_enforcement_mode(action, "default")

    assert result["action"] == "ban"
    assert result["intended_action"] == "ban"
    assert result["enforcement_mode"] == "enforce"


def test_status_requires_admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "admin-secret")

    client = _build_client()
    response = client.get("/telegram/status", headers={"X-Tenant-ID": "default"})

    assert response.status_code == 403


def test_config_options_requires_admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "admin-secret")

    client = _build_client()
    response = client.get("/telegram/config/options", headers={"X-Tenant-ID": "default"})

    assert response.status_code == 403


def test_resolve_review_rejects_invalid_decision(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "admin-secret")

    client = _build_client()
    response = client.post(
        "/telegram/reviews/some-review-id/resolve",
        headers={"X-Tenant-ID": "default", "X-Admin-Token": "admin-secret"},
        json={"decision": "quarantine"},
    )

    assert response.status_code == 400
