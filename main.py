#!/usr/bin/env python3
"""TruePresence Server - Entry point"""
from truepresence.main import app as _app
from truepresence.main import main as run_main

app = _app


if __name__ == "__main__":
    run_main()
