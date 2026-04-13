#!/usr/bin/env python3
"""TruePresence Server - Entry point"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from truepresence.api.server import app as rest_app
from truepresence.api import ws_server
from truepresence.adapters import telegram_bot

app = FastAPI(title="TruePresence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rest_app.router, tags=["rest"])
app.include_router(ws_server.router, tags=["websocket"])
app.include_router(telegram_bot.router, tags=["telegram"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )