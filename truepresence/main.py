from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from truepresence.runtime.wiring import allow_lenient_wiring, load_component

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


def _database_configured() -> bool:
    return any(
        key in os.environ
        for key in ["DATABASE_URL", "PGHOST", "POSTGRES_HOST", "POSTGRES_USER"]
    )


def _initialize_database_if_configured() -> None:
    if not _database_configured():
        logger.info("Database init skipped: no database environment configured")
        return

    try:
        from truepresence.db import init_db

        init_db()
        logger.info("Database initialized")
    except Exception as exc:
        if allow_lenient_wiring():
            logger.warning("Database init failed in lenient wiring mode: %s", exc)
            return
        raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    _initialize_database_if_configured()
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
        from truepresence.runtime.distributed import DistributedRuntime
        # Close any open Redis connections
        logger.info("Redis connections closed")
    except Exception as e:
        logger.warning(f"Error closing Redis: {e}")


def create_app() -> FastAPI:
    limiter = Limiter(key_func=get_remote_address)
    app = FastAPI(title="TruePresence", version="1.0.0", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

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
        """Enhanced health check with component status."""
        status = {"status": "ok", "components": {}}
        
        # Check database
        try:
            from truepresence.db import get_db
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            status["components"]["database"] = "ok"
        except Exception:
            status["components"]["database"] = "error"
            status["status"] = "degraded"
        
        # Check Redis (if configured)
        try:
            from truepresence.runtime.distributed import DistributedRuntime
            dist = DistributedRuntime()
            if dist.available:
                dist.redis_client.ping()
                status["components"]["redis"] = "ok"
            else:
                status["components"]["redis"] = "unavailable"
        except Exception:
            status["components"]["redis"] = "error"
        
        return status

    return app


app = create_app()


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("truepresence.main:app", host="0.0.0.0", port=port, reload=False)
