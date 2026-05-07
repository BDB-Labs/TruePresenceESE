import pytest

pytest.importorskip("psycopg2", reason="requires psycopg2-binary from the test/dev install")
pytestmark = [pytest.mark.integration, pytest.mark.db, pytest.mark.telegram]

from truepresence.adapters.telegram import TelegramAdapter  # noqa: E402
from truepresence.exceptions import EvidenceError  # noqa: E402


def test_telegram_parse_failure_raises_evidence_error() -> None:
    adapter = TelegramAdapter()

    with pytest.raises(EvidenceError):
        adapter.parse_update({"message": "not-a-dict"})


def test_telegram_message_parse_includes_velocity_signal() -> None:
    adapter = TelegramAdapter()

    event = adapter.parse_update(
        {
            "message": {
                "message_id": 1,
                "date": 1_700_000_000,
                "from": {"id": 123, "username": "person"},
                "chat": {"id": -100, "type": "group"},
                "text": "hello team",
            }
        }
    )

    assert event is not None
    assert event["features"]["message_velocity"] == 1
    assert event["signals"]["message_velocity"] == 1
