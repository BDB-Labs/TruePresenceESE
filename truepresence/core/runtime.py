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

from truepresence.decision.engine import TruePresenceDecisionEngine
from truepresence.ensemble.orchestrator import TruePresenceEnsembleOrchestrator

logger = logging.getLogger(__name__)

logger.info("Initializing shared TruePresence decision runtime")
orchestrator = TruePresenceEnsembleOrchestrator()
decision_engine = TruePresenceDecisionEngine(orchestrator=orchestrator)
logger.info("Shared runtime ready")
