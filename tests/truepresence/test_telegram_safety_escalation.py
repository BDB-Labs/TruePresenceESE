import asyncio
import json

from truepresence.adapters.telegram import TelegramAdapter
from truepresence.adapters.telegram_bot import TelegramProtectionService
from truepresence.safety.escalation import (
    ProviderRiskSignal,
    build_telegram_safety_evidence_card,
)


def _join_update(user_id: int, chat_id: int, date: int) -> dict:
    return {
        "chat_member": {
            "date": date,
            "chat": {"id": chat_id, "type": "supergroup", "title": "Safety Room"},
            "user": {"id": user_id, "username": f"user{user_id}", "is_bot": False},
            "old_chat_member": {"status": "left"},
            "new_chat_member": {"status": "member"},
        }
    }


def _media_update(
    user_id: int,
    chat_id: int,
    date: int,
    *,
    message_id: int,
    file_id: str,
    caption: str = "sensitive caption must never be retained",
) -> dict:
    return {
        "message": {
            "message_id": message_id,
            "date": date,
            "caption": caption,
            "from": {"id": user_id, "username": f"user{user_id}", "is_bot": False},
            "chat": {"id": chat_id, "type": "supergroup", "title": "Safety Room"},
            "photo": [{"file_id": file_id, "width": 640, "height": 480}],
            "thumbnail": {"file_id": f"thumb-{file_id}"},
        }
    }


def _safety(event: dict) -> dict:
    return event["context"]["telegram_safety"]


def test_media_update_is_processed_without_storing_or_downloading_media() -> None:
    adapter = TelegramAdapter()
    secret_file_id = "MEDIA_FILE_ID_MUST_NOT_BE_STORED"
    secret_caption = "CAPTION_MUST_NOT_BE_STORED"

    event = adapter.parse_update(
        _media_update(
            user_id=101,
            chat_id=-2001,
            date=1_700_100_000,
            message_id=1,
            file_id=secret_file_id,
            caption=secret_caption,
        )
    )

    safety = _safety(event)
    encoded_safety = json.dumps(safety)
    encoded_payload = json.dumps(event["payload"])
    assert safety["evidence_card"]["media_present"] is True
    assert safety["evidence_card"]["chat_id"] == -2001
    assert safety["evidence_card"]["message_id"] == 1
    assert secret_file_id not in encoded_safety
    assert secret_caption not in encoded_safety
    assert "photo" not in encoded_payload
    assert "thumbnail" not in encoded_safety


def test_high_risk_media_burst_produces_safety_escalation() -> None:
    adapter = TelegramAdapter()
    service = TelegramProtectionService.__new__(TelegramProtectionService)
    user_id = 202
    chat_id = -2002

    adapter.parse_update(_join_update(user_id, chat_id, date=1_700_200_000))
    event = None
    for offset in range(4):
        event = adapter.parse_update(
            _media_update(
                user_id=user_id,
                chat_id=chat_id,
                date=1_700_200_001 + offset,
                message_id=offset + 1,
                file_id=f"burst-file-{offset}",
            )
        )

    safety = _safety(event)
    assert "instant_media_post_after_join" in safety["reason_codes"]
    assert "media_burst_pattern" in safety["reason_codes"]
    assert safety["recommended_action"] == "mandatory_safety_escalation"

    action = service._apply_telegram_safety_escalation({"action": "allow", "confidence": 0.1}, event)
    assert action["action"] == "mandatory_safety_escalation"
    assert action["safety_evidence_card"]["risk_label"] == "critical"


def test_provider_reference_is_stored_without_media_content() -> None:
    provider_signal = ProviderRiskSignal(
        provider_id="lawful-risk-provider",
        provider_reference_id="provider-ref-abc123",
        outcome="known_bad_hash_match",
        risk_score=0.93,
        confidence=0.9,
    )

    card = build_telegram_safety_evidence_card(
        chat_id=-2003,
        message_id=33,
        sender_id=303,
        event_timestamp=1_700_300_000,
        event_type="message",
        media_present=True,
        reason_codes=["new_account_high_risk_media_behavior"],
        risk_score=0.93,
        confidence=0.9,
        recommended_action="mandatory_safety_escalation",
        provider_signal=provider_signal,
    )

    encoded = json.dumps(card)
    assert card["provider_reference_id"] == "provider-ref-abc123"
    assert card["provider_outcome"] == "known_bad_hash_match"
    assert "file_id" not in encoded
    assert "thumbnail" not in encoded
    assert "caption" not in encoded


def test_safety_review_dashboard_payload_contains_no_media_or_content() -> None:
    service = TelegramProtectionService(tenant_id="safety-review")
    secret_file_id = "DASHBOARD_MEDIA_ID_MUST_NOT_APPEAR"
    secret_caption = "DASHBOARD_CAPTION_MUST_NOT_APPEAR"
    evidence_card = build_telegram_safety_evidence_card(
        chat_id=-2004,
        message_id=44,
        sender_id=404,
        event_timestamp=1_700_400_000,
        event_type="message",
        media_present=True,
        reason_codes=["media_burst_pattern"],
        risk_score=0.88,
        confidence=0.84,
        recommended_action="mandatory_safety_escalation",
    )
    action = {
        "action": "mandatory_safety_escalation",
        "confidence": 0.84,
        "safety_evidence_card": evidence_card,
        "evidence_card": evidence_card,
    }
    result = {
        "final": {
            "threat_categories": [],
            "risk_factors": ["media_burst_pattern"],
            "reason_codes": ["media_burst_pattern"],
        }
    }

    try:
        asyncio.run(
            service._handle_manual_review(
                action,
                _media_update(
                    user_id=404,
                    chat_id=-2004,
                    date=1_700_400_000,
                    message_id=44,
                    file_id=secret_file_id,
                    caption=secret_caption,
                ),
                result,
                tenant_id="safety-review",
            )
        )
        review = service.get_pending_reviews("safety-review")[0]
    finally:
        asyncio.run(service.close())

    encoded = json.dumps(review)
    assert review["evidence_card"]["risk_label"] == "critical"
    assert review["evidence_card"]["recommended_action"] == "mandatory_safety_escalation"
    assert review["evidence_card"]["evidence_id"]
    assert "update" not in review
    assert "original_message" not in review
    assert "message_text" not in review
    assert secret_file_id not in encoded
    assert secret_caption not in encoded
    assert "photo" not in encoded
    assert "thumbnail" not in encoded
