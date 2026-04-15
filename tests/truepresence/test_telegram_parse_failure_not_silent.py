import pytest

from truepresence.adapters.telegram import TelegramAdapter
from truepresence.exceptions import EvidenceError


def test_telegram_parse_failure_raises_evidence_error() -> None:
    adapter = TelegramAdapter()

    with pytest.raises(EvidenceError):
        adapter.parse_update({"message": "not-a-dict"})
