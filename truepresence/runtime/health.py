"""Shared dependency probes for HTTP health endpoints."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def dependency_components_status() -> dict[str, Any]:
    """Return database and Redis connectivity suitable for health JSON payloads."""
    components: dict[str, str] = {}

    try:
        from truepresence.db import get_db

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        components["database"] = "ok"
    except Exception as exc:
        logger.warning("Health probe: database unavailable: %s", exc)
        components["database"] = "error"

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        components["redis"] = "unconfigured"
        return components

    try:
        from truepresence.runtime.distributed import DistributedRuntime

        dist = DistributedRuntime(redis_url=redis_url)
        if dist.available and dist.redis_client:
            dist.redis_client.ping()
            components["redis"] = "ok"
        else:
            components["redis"] = "unavailable"
    except Exception as exc:
        logger.warning("Health probe: Redis unavailable: %s", exc)
        components["redis"] = "error"

    return components
