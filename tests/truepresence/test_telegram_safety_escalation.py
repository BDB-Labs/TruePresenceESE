import asyncio
import json

import pytest

pytest.importorskip("psycopg2", reason="requires psycopg2-binary from the test/dev install")
pytestmark = [pytest.mark.integration, pytest.mark.db, pytest.mark.telegram]

from truepresence.adapters.telegram import TelegramAdapter  # noqa: E402
from truepresence.adapters.telegram_bot import TelegramProtectionService  # noqa: E402
from truepresence.safety.escalation import (  # noqa: E402
    ProviderRiskSignal,
    build_telegram_safety_evidence_card,
    evaluate_telegram_safety_escalation,
)
from truepresence.safety.policy import (  # noqa: E402
    TelegramSafetyFeatures,
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


def _forwarded_media_update(
    user_id: int,
    chat_id: int,
    date: int,
    *,
    message_id: int,
    file_id: str,
    caption: str = "forwarded sensitive caption must never be retained",
) -> dict:
    update = _media_update(
        user_id=user_id,
        chat_id=chat_id,
        date=date,
        message_id=message_id,
        file_id=file_id,
        caption=caption,
    )
    update["message"]["forward_origin"] = {
        "type": "user",
        "sender_user": {"id": 999_001, "username": "forward-source"},
    }
    update["message"]["forward_date"] = date - 20
    update["message"]["media_url"] = "https://private.example.invalid/media-preview"
    return update


def _safety(event: dict) -> dict:
    return event["context"]["telegram_safety"]


def _assert_no_media_or_raw_content(value: object, *secret_values: str) -> None:
    encoded = json.dumps(value)
    for secret in secret_values:
        assert secret not in encoded
    for forbidden in [
        "caption",
        "file_id",
        "file_unique_id",
        "file_url",
        "media_url",
        "message_text",
        "original_message",
        "photo",
        "raw_content",
        "raw_text",
        "thumbnail",
        "update",
    ]:
        assert forbidden not in encoded


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
    assert "message_text" not in encoded_safety
    assert "photo" not in encoded_payload
    assert "thumbnail" not in encoded_safety
    _assert_no_media_or_raw_content(safety, secret_file_id, secret_caption)


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


def test_safety_confidence_without_provider_uses_detector_signal_confidence() -> None:
    escalation = evaluate_telegram_safety_escalation(
        TelegramSafetyFeatures(
            chat_id=-2101,
            message_id=11,
            sender_id=501,
            event_timestamp=1_700_501_000,
            media_present=True,
            join_to_first_media_ms=1_000,
        )
    )

    assert escalation is not None
    assert escalation.risk_score == pytest.approx(0.86)
    assert escalation.confidence == pytest.approx(0.86)
    assert escalation.risk_label == "critical"


def test_safety_confidence_with_provider_signal_uses_provider_confidence() -> None:
    escalation = evaluate_telegram_safety_escalation(
        TelegramSafetyFeatures(
            chat_id=-2102,
            message_id=12,
            sender_id=502,
            event_timestamp=1_700_502_000,
            media_present=True,
        ),
        provider_signal=ProviderRiskSignal(
            provider_id="lawful-risk-provider",
            provider_reference_id="provider-ref-medium",
            outcome="provider_reference_only",
            risk_score=0.72,
            confidence=0.61,
        ),
    )

    assert escalation is not None
    assert escalation.risk_score == pytest.approx(0.72)
    assert escalation.confidence == pytest.approx(0.61)
    assert escalation.confidence != pytest.approx(escalation.risk_score)


def test_safety_confidence_multiple_signals_gets_bounded_corroboration_bonus() -> None:
    escalation = evaluate_telegram_safety_escalation(
        TelegramSafetyFeatures(
            chat_id=-2103,
            message_id=13,
            sender_id=503,
            event_timestamp=1_700_503_000,
            media_present=True,
            join_to_first_media_ms=1_000,
            media_count_window=4,
            media_burst_count=3,
            account_age_days=3,
        )
    )

    assert escalation is not None
    assert {
        "instant_media_post_after_join",
        "media_burst_pattern",
        "new_account_high_risk_media_behavior",
    }.issubset(set(escalation.reason_codes))
    assert escalation.risk_score == pytest.approx(0.88)
    assert escalation.confidence == pytest.approx(0.96)
    assert escalation.confidence - escalation.risk_score <= 0.12


def test_safety_confidence_high_risk_can_remain_moderate_confidence() -> None:
    escalation = evaluate_telegram_safety_escalation(
        TelegramSafetyFeatures(
            chat_id=-2104,
            message_id=14,
            sender_id=504,
            event_timestamp=1_700_504_000,
            media_present=True,
        ),
        provider_signal=ProviderRiskSignal(
            provider_id="lawful-risk-provider",
            provider_reference_id="provider-ref-high-risk",
            outcome="high_risk_reference",
            risk_score=0.93,
            confidence=0.55,
        ),
    )

    assert escalation is not None
    assert escalation.risk_score == pytest.approx(0.93)
    assert escalation.risk_label == "critical"
    assert escalation.confidence == pytest.approx(0.55)
    assert escalation.recommended_action == "mandatory_safety_escalation"


def test_safety_confidence_provider_high_confidence_can_exceed_risk() -> None:
    escalation = evaluate_telegram_safety_escalation(
        TelegramSafetyFeatures(
            chat_id=-2105,
            message_id=15,
            sender_id=505,
            event_timestamp=1_700_505_000,
            media_present=True,
        ),
        provider_signal=ProviderRiskSignal(
            provider_id="lawful-risk-provider",
            provider_reference_id="provider-ref-high-confidence",
            outcome="high_confidence_reference",
            risk_score=0.7,
            confidence=0.97,
        ),
    )

    assert escalation is not None
    assert escalation.risk_score == pytest.approx(0.7)
    assert escalation.confidence == pytest.approx(0.97)
    assert escalation.confidence != pytest.approx(escalation.risk_score)


def test_safety_confidence_missing_provider_confidence_does_not_mirror_provider_risk() -> None:
    escalation = evaluate_telegram_safety_escalation(
        TelegramSafetyFeatures(
            chat_id=-2106,
            message_id=16,
            sender_id=506,
            event_timestamp=1_700_506_000,
            media_present=True,
        ),
        provider_signal=ProviderRiskSignal(
            provider_id="lawful-risk-provider",
            provider_reference_id="provider-ref-no-confidence",
            outcome="risk_without_confidence",
            risk_score=0.91,
            confidence=None,
        ),
    )

    assert escalation is not None
    assert escalation.risk_score == pytest.approx(0.91)
    assert escalation.confidence == pytest.approx(0.55)
    assert escalation.confidence != pytest.approx(escalation.risk_score)


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
    _assert_no_media_or_raw_content(card)


def test_forwarded_media_metadata_safety_evidence_is_metadata_only() -> None:
    adapter = TelegramAdapter()
    secret_file_id = "FORWARDED_FILE_ID_MUST_NOT_BE_STORED"
    secret_caption = "FORWARDED_CAPTION_MUST_NOT_BE_STORED"

    event = adapter.parse_update(
        _forwarded_media_update(
            user_id=606,
            chat_id=-2606,
            date=1_700_606_000,
            message_id=66,
            file_id=secret_file_id,
            caption=secret_caption,
        )
    )

    safety = _safety(event)
    assert safety["evidence_card"]["media_present"] is True
    assert safety["evidence_card"]["chat_id"] == -2606
    assert safety["evidence_card"]["message_id"] == 66
    _assert_no_media_or_raw_content(safety, secret_file_id, secret_caption)


def test_provider_receives_reference_metadata_without_media_or_caption() -> None:
    captured_metadata = {}

    def provider(metadata: dict) -> dict:
        captured_metadata.update(metadata)
        return {
            "provider_id": "lawful-risk-provider",
            "provider_reference_id": "provider-ref-from-adapter",
            "outcome": "provider_reference_only",
            "risk_score": 0.89,
            "confidence": 0.82,
        }

    adapter = TelegramAdapter({"safety_provider": provider})
    secret_file_id = "PROVIDER_FILE_ID_MUST_NOT_BE_SENT"
    secret_caption = "PROVIDER_CAPTION_MUST_NOT_BE_SENT"

    event = adapter.parse_update(
        _media_update(
            user_id=707,
            chat_id=-2707,
            date=1_700_707_000,
            message_id=77,
            file_id=secret_file_id,
            caption=secret_caption,
        )
    )

    safety = _safety(event)
    assert captured_metadata == {
        "chat_id": -2707,
        "message_id": 77,
        "sender_id": 707,
        "event_timestamp": 1_700_707_000,
        "event_type": "message",
        "media_present": True,
    }
    assert safety["evidence_card"]["provider_reference_id"] == "provider-ref-from-adapter"
    assert safety["evidence_card"]["provider_outcome"] == "provider_reference_only"
    _assert_no_media_or_raw_content(safety, secret_file_id, secret_caption)


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
    assert "media_preview" not in encoded
    _assert_no_media_or_raw_content(review, secret_file_id, secret_caption)
