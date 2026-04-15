import logging

import pytest

from truepresence.exceptions import ConfigurationError
from truepresence.runtime import wiring


def test_load_component_raises_in_strict_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wiring, "is_test_environment", lambda: False)
    monkeypatch.delenv("TRUEPRESENCE_ALLOW_LENIENT_WIRING", raising=False)
    monkeypatch.setenv("TRUEPRESENCE_ENV", "production")

    with pytest.raises(ConfigurationError):
        wiring.load_component(
            label="Broken component",
            loader=lambda: (_ for _ in ()).throw(ValueError("boom")),
            logger=logging.getLogger(__name__),
        )


def test_load_component_returns_none_in_lenient_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wiring, "is_test_environment", lambda: False)
    monkeypatch.setenv("TRUEPRESENCE_ENV", "development")

    result = wiring.load_component(
        label="Broken component",
        loader=lambda: (_ for _ in ()).throw(ValueError("boom")),
        logger=logging.getLogger(__name__),
    )

    assert result is None
