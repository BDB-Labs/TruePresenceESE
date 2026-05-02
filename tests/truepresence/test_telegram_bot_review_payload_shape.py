import asyncio

from truepresence.adapters.telegram_bot import TelegramProtectionService


def test_manual_review_uses_edited_message_shape() -> None:
    service = TelegramProtectionService(tenant_id="review-test")

    action = {"action": "alert_admin", "confidence": 0.5}
    update = {
        "edited_message": {
            "message_id": 12,
            "text": "edited text",
            "from": {"id": 7, "username": "editor"},
            "chat": {"id": 99, "title": "Room"},
        }
    }
    result = {"final": {"threat_categories": ["x"], "risk_factors": ["y"]}}

    asyncio.run(service._handle_manual_review(action, update, result, tenant_id="review-test"))
    reviews = service.get_pending_reviews("review-test")

    assert len(reviews) == 1
    review = reviews[0]
    assert review["message_text"] == "edited text"
    assert review["user_info"]["id"] == 7
    assert review["chat_info"]["id"] == 99

    asyncio.run(service.close())
