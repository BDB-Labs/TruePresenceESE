from fastapi import FastAPI
from fastapi.testclient import TestClient

from truepresence.adapters import telegram_bot


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(telegram_bot.router)
    return TestClient(app)


def test_telegram_admin_routes_require_auth() -> None:
    response = _client().get("/telegram/status")

    assert response.status_code == 401


def test_telegram_webhook_uses_tenant_query(monkeypatch) -> None:
    captured = {}

    async def fake_process_update(update, tenant_id=None):
        captured["update"] = update
        captured["tenant_id"] = tenant_id
        return None

    monkeypatch.setattr(telegram_bot.service, "process_update", fake_process_update)

    response = _client().post("/telegram/webhook?tenant=client1", json={"update_id": 123})

    assert response.status_code == 200
    assert captured["tenant_id"] == "client1"
    assert captured["update"] == {"update_id": 123}


def test_telegram_config_updates_running_service() -> None:
    service = telegram_bot.TelegramProtectionService()

    updated = service.update_tenant_config(
        "client1",
        {
            "detectors": {"copyright_violation": {"enabled": False}},
            "response_thresholds": {"ban": 0.9},
        },
    )

    assert updated["detectors"]["copyright_violation"]["enabled"] is False
    assert updated["response_thresholds"]["ban"] == 0.9
    assert service.tenant_adapters["client1"].active_detectors["copyright_violation"]["enabled"] is False


def test_telegram_review_resolve_uses_router_singleton() -> None:
    app = FastAPI()
    app.dependency_overrides[telegram_bot.require_telegram_admin] = lambda: {"role": "super_admin"}
    app.include_router(telegram_bot.router)
    client = TestClient(app)
    tenant_id = "route-test"
    review_id = telegram_bot.service.add_pending_review(
        {
            "original_message": {},
            "action": {},
            "update": {},
            "evaluation": {"final": {}},
        },
        tenant_id=tenant_id,
    )

    response = client.post(
        f"/telegram/reviews/{review_id}/resolve?tenant={tenant_id}",
        json={"decision": "allow", "notes": "reviewed"},
    )

    assert response.status_code == 200
    assert response.json()["review_id"] == review_id
    assert telegram_bot.service.pending_reviews[tenant_id][review_id]["status"] == "resolved"
