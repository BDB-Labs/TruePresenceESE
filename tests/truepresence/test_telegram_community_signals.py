from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("psycopg2", reason="requires psycopg2-binary from the test/dev install")
pytestmark = [pytest.mark.integration, pytest.mark.db, pytest.mark.telegram]

from truepresence.adapters.telegram import TelegramAdapter  # noqa: E402
from truepresence.adapters.telegram_bot import TelegramProtectionService  # noqa: E402
from truepresence.surfaces.telegram.community import (  # noqa: E402
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
    assert "message_text" not in review
    assert "original_message" not in review
    assert "update" not in review


def test_evidence_card_has_required_fields() -> None:
    card = build_telegram_community_evidence_card(
        event={
            "event_type": "message",
            "timestamp": 1_700_050_000,
            "context": {
                "platform": "telegram",
                "user_id": 1001,
                "group_id": -2001,
                "telegram_community": {
                    "features": {"join_to_first_message_ms": 500, "link_present": True},
                    "reason_codes": ["instant_post_after_join"],
                    "detector_signals": [
                        {
                            "reason_code": "instant_post_after_join",
                            "severity": "high",
                            "confidence": 0.78,
                            "contribution_target": "automation",
                            "category": "session_continuity",
                            "explanation": "A message was posted almost immediately after joining.",
                        }
                    ],
                },
            },
        },
        action={"action": "alert_admin", "confidence": 0.73},
        evaluation={"final": {"reason_codes": ["instant_post_after_join"]}},
    )

    assert "risk" in card
    assert "score" in card["risk"]
    assert "level" in card["risk"]
    assert "confidence" in card
    assert "reason_codes" in card
    assert "timestamps" in card
    assert "event_timestamp" in card["timestamps"]
    assert "created_at" in card["timestamps"]
    assert "recommended_action" in card
    assert card["recommended_action"] == "alert_admin"
    assert card["privacy_boundary"] == "metadata_only_no_content_preview"
    assert "feature_summaries" in card
    assert "detector_signals" in card
    assert "actor_refs" in card
    assert "surface" in card
    assert card["surface"] == "telegram"
    encoded = json.dumps(card)
    assert "content_preview" not in card
    assert "message_text" not in encoded


def test_coordinated_join_pattern_is_detected() -> None:
    adapter = TelegramAdapter()
    chat_id = -2002
    join_time = 1_700_060_000
    event = None

    for user_num in range(12):
        adapter.parse_update(_join_update(2000 + user_num, chat_id, date=join_time))
        event = adapter.parse_update(
            _message_update(2000 + user_num, chat_id, join_time + 1, message_id=user_num + 1)
        )

    community = _community(event)
    assert community["features"]["joined_within_cluster_count"] >= 10
    assert "coordinated_join_pattern" in community["reason_codes"]


def test_repeat_group_hopping_pattern_is_detected() -> None:
    adapter = TelegramAdapter()
    user_id = 3001

    for chat_num in range(6):
        adapter.parse_update(_join_update(user_id, -3000 - chat_num, date=1_700_070_000 + chat_num))
        event = adapter.parse_update(
            _message_update(
                user_id,
                -3000 - chat_num,
                1_700_070_000 + chat_num + 1,
                message_id=chat_num + 1,
            )
        )

    community = _community(event)
    assert community["features"]["group_hop_count"] >= 5
    assert "repeat_group_hopping_pattern" in community["reason_codes"]


def test_no_message_content_in_review_data() -> None:
    service = TelegramProtectionService(tenant_id="privacy-review")
    secret_body = "PRIVACY_SECRET_BODY_MUST_NOT_BE_STORED"
    evidence_card = {
        "risk": {"score": 0.65, "level": "medium"},
        "confidence": 0.65,
        "reason_codes": ["message_burst_pattern"],
        "timestamps": {"event_timestamp": 1_700_080_000},
        "recommended_action": "alert_admin",
        "feature_summaries": {"message_count_window": 5, "burst_count": 4},
        "privacy_boundary": "metadata_only_no_content_preview",
    }
    action = {
        "action": "alert_admin",
        "confidence": 0.65,
        "evidence_card": evidence_card,
    }
    update = {
        "message": {
            "message_id": 20,
            "date": 1_700_080_000,
            "text": secret_body,
            "caption": "private caption must not be stored",
            "photo": [{"file_id": "FILE_ID_SHOULD_NOT_BE_STORED"}],
            "from": {"id": 5678, "username": "privacy_test"},
            "chat": {"id": -4001, "title": "Privacy Test"},
        }
    }
    result = {
        "final": {
            "threat_categories": [],
            "risk_factors": ["message_burst_pattern"],
            "reason_codes": ["message_burst_pattern"],
        }
    }

    try:
        asyncio.run(service._handle_manual_review(action, update, result, tenant_id="privacy-review"))
        review = service.get_pending_reviews("privacy-review")[0]
    finally:
        asyncio.run(service.close())

    encoded = json.dumps(review)
    assert secret_body not in encoded
    assert "private caption must not be stored" not in encoded
    assert "FILE_ID_SHOULD_NOT_BE_STORED" not in encoded
    assert "message_text" not in review
    assert "original_message" not in review
    assert "update" not in review
    assert review["evidence_card"]["privacy_boundary"] == "metadata_only_no_content_preview"
