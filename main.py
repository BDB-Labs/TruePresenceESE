#!/usr/bin/env python3
"""TruePresence Server - Entry point"""
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from truepresence.api.server import app as rest_app
from truepresence.api import ws_server
from truepresence.adapters import telegram_bot
from truepresence.exceptions import TruePresenceError

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

@app.exception_handler(TruePresenceError)
async def tp_exception_handler(request: Request, exc: TruePresenceError):
    return JSONResponse(
        status_code=500,
        content={"error": exc.__class__.__name__, "message": exc.message, "details": exc.details}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "InternalError", "message": str(exc)}
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )