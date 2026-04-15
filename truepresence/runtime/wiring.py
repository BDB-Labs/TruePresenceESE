from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from typing import Any, TypeVar

from truepresence.exceptions import ConfigurationError

T = TypeVar("T")


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _environment_name() -> str:
    return (
        os.environ.get("TRUEPRESENCE_ENV")
        or os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or ""
    ).strip().lower()


def is_test_environment() -> bool:
    return "pytest" in sys.modules or bool(os.environ.get("PYTEST_CURRENT_TEST"))


def is_development_environment() -> bool:
    return _environment_name() in {"dev", "development", "local", "test"}


def allow_lenient_wiring() -> bool:
    return _truthy_env("TRUEPRESENCE_ALLOW_LENIENT_WIRING") or is_test_environment() or is_development_environment()


def load_component(
    *,
    label: str,
    loader: Callable[[], T],
    logger: logging.Logger,
) -> T | None:
    try:
        return loader()
    except Exception as exc:
        if allow_lenient_wiring():
            logger.warning("%s unavailable in lenient wiring mode: %s", label, exc)
            return None
        raise ConfigurationError(
            message=f"{label} wiring failed",
            details={"component": label, "error_type": type(exc).__name__},
        ) from exc


def load_required_runtime(
    *,
    loader: Callable[[], T],
    fallback_factory: Callable[[Exception], T],
    logger: logging.Logger,
) -> T:
    try:
        return loader()
    except Exception as exc:
        if allow_lenient_wiring():
            logger.warning("Shared runtime falling back in lenient wiring mode: %s", exc)
            return fallback_factory(exc)
        raise ConfigurationError(
            message="Shared runtime wiring failed",
            details={"error_type": type(exc).__name__},
        ) from exc
