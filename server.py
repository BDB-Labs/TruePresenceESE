#!/usr/bin/env python3
"""Compatibility entry point for running the canonical TruePresence app."""

import os

import uvicorn

from truepresence.main import app

__all__ = ["app"]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("truepresence.main:app", host="0.0.0.0", port=port, reload=False)
