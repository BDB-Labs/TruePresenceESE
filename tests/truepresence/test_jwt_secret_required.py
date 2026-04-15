import importlib
import sys

import pytest


def test_jwt_secret_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUEPRESENCE_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("TRUEPRESENCE_ALLOW_DEV_AUTH", raising=False)
    sys.modules.pop("truepresence.api.auth", None)

    with pytest.raises(RuntimeError):
        importlib.import_module("truepresence.api.auth")
