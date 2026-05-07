import pytest

pytest.importorskip("psycopg2", reason="requires psycopg2-binary from the test/dev install")
pytestmark = [pytest.mark.integration, pytest.mark.db, pytest.mark.telegram]

from truepresence.adapters.telegram import TelegramAdapter  # noqa: E402


def test_parse_message_populates_velocity_and_single_history_append() -> None:
    adapter = TelegramAdapter()

    event = adapter.parse_update(
        {
            "message": {
                "message_id": 1,
                "date": 1710000000,
                "text": "hello world",
                "from": {"id": 42, "username": "alice", "is_bot": False},
                "chat": {"id": 1001, "type": "group"},
            }
        }
    )

    assert event is not None
    assert event["features"]["message_velocity"] == 1
    assert event["signals"]["message_velocity"] == 1
    assert len(adapter._user_recent_texts["42"]) == 1
