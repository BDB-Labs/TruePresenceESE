#!/usr/bin/env python3
"""TruePresence Server - Entry point"""
import os
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from truepresence.api.ws_server import router as ws_router
from truepresence.api.server import app as rest_app
from truepresence.api.auth import router as auth_router
from truepresence.adapters.telegram_bot import router as telegram_router
from truepresence.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "https://verify.bageltech.net",
    "https://www.bageltech.net",
    "https://bageltech.net",
    "http://localhost:3000",  # local Next.js dev
]

app = FastAPI(title="TruePresence", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.mount("/api", rest_app)
app.include_router(ws_router, tags=["websocket"])
app.include_router(auth_router)
app.include_router(telegram_router)


@app.on_event("startup")
async def startup():
    """Initialize database schema on startup."""
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database init skipped (DATABASE_URL not set?): {e}")


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
