#!/usr/bin/env python3
"""TruePresence Server - Entry point"""
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from truepresence.api.ws_server import router as ws_router
from truepresence.api.server import app as rest_app

app = FastAPI(title="TruePresence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST API as sub-application (rest_app is a FastAPI instance, not a router)
app.mount("/api", rest_app)

# WebSocket router mounts directly
app.include_router(ws_router, tags=["websocket"])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
