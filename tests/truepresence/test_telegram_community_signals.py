import asyncio
import json

from truepresence.adapters.telegram import TelegramAdapter
from truepresence.adapters.telegram_bot import TelegramProtectionService
from truepresence.surfaces.telegram.community import (
    build_telegram_community_evidence_card,
)


def _join_update(user_id: int, chat_id: int, date: int = 1_700_000_000) -> dict:
    return {
        "chat_member": {
            "date": date,
            "chat": {"id": chat_id, "type": "supergroup", "title": "Community"},
            "user": {"id": user_id, "username": f"user{user_id}", "is_bot": False},
            "old_chat_member": {"status": "left"},
            "new_chat_member": {"status": "member"},
        }
    }


def _message_update(
    user_id: int,
    chat_id: int,
    date: int,
    *,
    message_id: int = 1,
    text: str = "metadata-only event",
    entities: list[dict] | None = None,
    photo: list[dict] | None = None,
) -> dict:
    message = {
        "message_id": message_id,
        "date": date,
        "text": text,
        "from": {"id": user_id, "username": f"user{user_id}", "is_bot": False},
        "chat": {"id": chat_id, "type": "supergroup", "title": "Community"},
    }
    if entities is not None:
        message["entities"] = entities
    if photo is not None:
        message["photo"] = photo
    return {"message": message}


def _community(event: dict) -> dict:
    return event["context"]["telegram_community"]


def test_instant_post_after_join_and_link_drop_use_metadata_only() -> None:
    adapter = TelegramAdapter()
    user_id = 77
    chat_id = -1001
    secret_text = "SECRET_INVITE_BODY must not enter community evidence"

    adapter.parse_update(_join_update(user_id, chat_id, date=1_700_000_000))
    event = adapter.parse_update(
        _message_update(
            user_id,
            chat_id,
            1_700_000_001,
            text=secret_text,
            entities=[{"type": "url", "offset": 0, "length": 20}],
        )
    )

    community = _community(event)
    assert community["features"]["join_to_first_message_ms"] == 1000
    assert community["features"]["join_to_first_link_ms"] == 1000
    assert community["features"]["link_present"] is True
    assert "instant_post_after_join" in community["reason_codes"]
    assert "link_drop_after_join" in community["reason_codes"]

    card = build_telegram_community_evidence_card(
        event=event,
        action={"action": "alert_admin", "confidence": 0.73},
        evaluation={"final": {"reason_codes": community["reason_codes"]}},
    )
    encoded = json.dumps(card)
    assert secret_text not in encoded
    assert "message_text" not in card
    assert "content_preview" not in card


def test_message_burst_pattern_is_detected_from_cadence() -> None:
    adapter = TelegramAdapter()
    user_id = 88
    chat_id = -1002
    event = None

    for offset in range(6):
        event = adapter.parse_update(
            _message_update(
                user_id,
                chat_id,
                1_700_010_000 + offset,
                message_id=offset + 1,
            )
        )

    community = _community(event)
    assert community["features"]["message_count_window"] == 6
    assert community["features"]["burst_count"] >= 5
    assert "message_burst_pattern" in community["reason_codes"]
    assert "conversation_cadence_anomaly" in community["reason_codes"]


def test_synchronized_cluster_is_detected_without_message_bodies() -> None:
    adapter = TelegramAdapter()
    chat_id = -1003

    adapter.parse_update(_message_update(101, chat_id, 1_700_020_000, message_id=1, text="alpha"))
    adapter.parse_update(_message_update(102, chat_id, 1_700_020_001, message_id=2, text="bravo"))
    event = adapter.parse_update(_message_update(103, chat_id, 1_700_020_002, message_id=3, text="charlie"))

    community = _community(event)
    assert community["features"]["synchronized_peer_count"] >= 2
    assert "synchronized_posting_cluster" in community["reason_codes"]

    card = build_telegram_community_evidence_card(
        event=event,
        action={"action": "alert_admin", "confidence": 0.68},
        evaluation={"final": {"reason_codes": community["reason_codes"]}},
    )
    encoded = json.dumps(card)
    assert "alpha" not in encoded
    assert "bravo" not in encoded
    assert "charlie" not in encoded


def test_media_evidence_stores_presence_not_media_payload() -> None:
    adapter = TelegramAdapter()
    user_id = 99
    chat_id = -1004
    secret_file_id = "MEDIA_FILE_ID_SHOULD_NOT_BE_STORED"

    adapter.parse_update(_join_update(user_id, chat_id, date=1_700_030_000))
    event = adapter.parse_update(
        _message_update(
            user_id,
            chat_id,
            1_700_030_002,
            text="private caption must not enter evidence card",
            photo=[{"file_id": secret_file_id, "width": 1280, "height": 720}],
        )
    )

    community = _community(event)
    assert community["features"]["media_present"] is True
    assert community["features"]["join_to_first_media_ms"] == 2000

    card = build_telegram_community_evidence_card(
        event=event,
        action={"action": "alert_admin", "confidence": 0.51},
        evaluation={"final": {"reason_codes": community["reason_codes"]}},
    )
    encoded = json.dumps(card)
    assert secret_file_id not in encoded
    assert "private caption" not in encoded
    assert card["feature_summaries"]["media_present"] is True
    assert "media" not in card


def test_manual_review_includes_metadata_only_evidence_card() -> None:
    service = TelegramProtectionService(tenant_id="community-review")
    secret_text = "REVIEW_SECRET_TEXT_SHOULD_NOT_BE_IN_CARD"
    evidence_card = {
        "risk": {"score": 0.82, "level": "high"},
        "confidence": 0.82,
        "reason_codes": ["instant_post_after_join"],
        "timestamps": {"event_timestamp": 1_700_040_000},
        "recommended_action": "alert_admin",
        "feature_summaries": {"join_to_first_message_ms": 900},
        "privacy_boundary": "metadata_only_no_content_preview",
    }
    action = {
        "action": "alert_admin",
        "confidence": 0.82,
        "evidence_card": evidence_card,
    }
    update = {
        "message": {
            "message_id": 10,
            "date": 1_700_040_000,
            "text": secret_text,
            "from": {"id": 1234, "username": "reviewed"},
            "chat": {"id": -1005, "title": "Community"},
        }
    }
    result = {
        "final": {
            "threat_categories": [],
            "risk_factors": ["instant_post_after_join"],
            "reason_codes": ["instant_post_after_join"],
        }
    }

    try:
        asyncio.run(service._handle_manual_review(action, update, result, tenant_id="community-review"))
        review = service.get_pending_reviews("community-review")[0]
    finally:
        asyncio.run(service.close())

    assert review["evidence_card"] == evidence_card
    assert secret_text not in json.dumps(review["evidence_card"])
