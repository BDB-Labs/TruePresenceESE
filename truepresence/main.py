from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


def create_app() -> FastAPI:
    app = FastAPI(title="TruePresence", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    try:
        from truepresence.api.server import app as rest_app
    except Exception as exc:
        logger.warning("REST API unavailable during app bootstrap: %s", exc)
    else:
        app.mount("/api", rest_app)

    try:
        from truepresence.api.ws_server import router as ws_router
    except Exception as exc:
        logger.warning("WebSocket router unavailable during app bootstrap: %s", exc)
    else:
        app.include_router(ws_router, tags=["websocket"])

    try:
        from truepresence.adapters.telegram_bot import router as telegram_router
    except Exception as exc:
        logger.warning("Telegram router unavailable during app bootstrap: %s", exc)
    else:
        app.include_router(telegram_router)

    try:
        from truepresence.api.auth import router as auth_router
    except Exception as exc:
        logger.warning("Auth router unavailable during app bootstrap: %s", exc)
    else:
        app.include_router(auth_router)

    @app.on_event("startup")
    async def startup() -> None:
        try:
            from truepresence.db import init_db

            init_db()
            logger.info("Database initialized")
        except Exception as exc:
            logger.warning("Database init skipped (DATABASE_URL not set?): %s", exc)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("truepresence.main:app", host="0.0.0.0", port=port, reload=False)
