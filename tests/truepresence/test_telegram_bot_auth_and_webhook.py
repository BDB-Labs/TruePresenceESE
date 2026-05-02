from fastapi import FastAPI
from fastapi.testclient import TestClient

import truepresence.adapters.telegram_bot as telegram_bot


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
