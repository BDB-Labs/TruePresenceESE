from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from truepresence.runtime.wiring import allow_lenient_wiring, load_component

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "https://verify.bageltech.net",
    "https://www.bageltech.net",
    "https://bageltech.net",
    "http://localhost:3000",
]


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
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _initialize_database_if_configured()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="TruePresence", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("truepresence.main:app", host="0.0.0.0", port=port, reload=False)
