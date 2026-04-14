"""
TruePresence Shared Runtime

Single orchestrator instance shared across all entry points:
  - Telegram webhook (telegram_bot.py)
  - REST API (api/server.py)
  - WebSocket server (api/ws_server.py)

One IdentityGraph, one Redis connection, one set of adaptive weights,
one session memory — regardless of how a user arrives.

With REDIS_URL set, all state survives redeploys and scales horizontally.
"""

import logging
from truepresence.core.orchestrator_v3 import TruePresenceOrchestratorV3

logger = logging.getLogger(__name__)

logger.info("Initializing shared TruePresenceOrchestratorV3 runtime")
orchestrator = TruePresenceOrchestratorV3()
logger.info(f"Shared runtime ready - orchestrator type: {type(orchestrator).__name__}")
logger.info(f"Orchestrator has health_check: {hasattr(orchestrator, 'health_check')}")
