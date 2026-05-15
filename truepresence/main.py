from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from slowapi.middleware import SlowAPIMiddleware

from truepresence.api.rate_limit import limiter as shared_http_limiter
from truepresence.runtime.health import dependency_components_status
from truepresence.runtime.wiring import load_component

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "https://truepresence.bageltech.net",
    "https://verify.bageltech.net",
    "https://www.bageltech.net",
    "https://bageltech.net",
    "http://localhost:3000",
]


def _get_allowed_origins() -> list[str]:
    """Get allowed CORS origins from environment or use defaults."""
    env_origins = os.environ.get("ALLOWED_ORIGINS", "")
    if env_origins.strip():
        return [origin.strip() for origin in env_origins.split(",") if origin.strip()]
    return ALLOWED_ORIGINS


def _component_status() -> dict[str, Any]:
    status: dict[str, Any] = {"status": "ok", "components": dependency_components_status()}
    for key, value in status["components"].items():
        if key == "redis" and value == "unconfigured":
            continue
        if value not in {"ok", "unconfigured"}:
            status["status"] = "degraded"
    return status



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    yield {"status": "shutdown"}
    # Graceful shutdown: close connection pools
    await _cleanup_connections(app)


async def _cleanup_connections(app: FastAPI) -> None:
    """Close all connection pools on shutdown."""
    logger.info("Shutting down connection pools...")

    # Close DB pool
    try:
        from truepresence.db import _pool
        if _pool is not None:
            _pool.closeall()
            logger.info("Database connection pool closed")
    except Exception as e:
        logger.warning(f"Error closing DB pool: {e}")

    # Close Redis connections
    try:
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            from truepresence.runtime.distributed import DistributedRuntime

            dist = DistributedRuntime(redis_url=redis_url)
            dist.disconnect_pool()
            logger.info("Redis connection pool disconnected")
    except Exception as e:
        logger.warning("Error closing Redis: %s", e)


def create_app() -> FastAPI:
    app = FastAPI(title="TruePresence", version="1.0.0", lifespan=lifespan)
    app.state.limiter = shared_http_limiter
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-TruePresence-Service-Token",
        ],
    )
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please try again later."},
        )
    rest_app = load_component(
        label="REST API",
        loader=lambda: __import__("truepresence.api.server", fromlist=["app"]).app,
        logger=logger,
    )
    if rest_app is not None:
        app.mount("/api", rest_app)

    ws_router = load_component(
        label="WebSocket router",
        loader=lambda: __import__("truepresence.api.ws_server", fromlist=["router"]).router,
        logger=logger,
    )
    if ws_router is not None:
        app.include_router(ws_router, tags=["websocket"])

    telegram_router = load_component(
        label="Telegram router",
        loader=lambda: __import__("truepresence.adapters.telegram_bot", fromlist=["router"]).router,
        logger=logger,
    )
    if telegram_router is not None:
        app.include_router(telegram_router)

    auth_router = load_component(
        label="Auth router",
        loader=lambda: __import__("truepresence.api.auth", fromlist=["router"]).router,
        logger=logger,
    )
    if auth_router is not None:
        app.include_router(auth_router)

    @app.get("/health")
    def health() -> dict[str, Any]:
        """Liveness endpoint with component status."""
        return _component_status()

    @app.get("/ready", response_model=None)
    def ready() -> Any:
        """Readiness endpoint for deployment health checks."""
        status = _component_status()
        if status["status"] != "ok":
            return JSONResponse(status_code=503, content=status)
        return status

    return app


app = create_app()


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("truepresence.main:app", host="0.0.0.0", port=port, reload=False)
