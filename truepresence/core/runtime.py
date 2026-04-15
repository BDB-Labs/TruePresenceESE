"""
TruePresence Shared Runtime

Single orchestrator instance shared across all entry points:
  - Telegram webhook (telegram_bot.py)
  - REST API (api/server.py)
  - WebSocket server (api/ws_server.py)

The runtime prefers the production V3 orchestrator. When optional heavy
dependencies are unavailable in a local or test environment, it falls back to a
lightweight in-process runtime that preserves the product contracts.
"""

from __future__ import annotations

import logging

from truepresence.decision.engine import TruePresenceDecisionEngine
from truepresence.memory.session_timeline import SessionTimeline

logger = logging.getLogger(__name__)


class _FallbackIdentityGraph:
    def get_connected_sessions(self, session_id: str):
        return set()

    def get_session_risk(self, session_id: str) -> float:
        return 0.0

    def get_session_cluster(self, session_id: str):
        return set()


class _FallbackOrchestrator:
    def __init__(self, error: Exception | None = None):
        self.memory = SessionTimeline()
        self.identity_graph = _FallbackIdentityGraph()
        self._error = error

    def run(self, **kwargs):
        return []

    def get_session_cluster(self, session_id: str):
        return set()

    def health_check(self):
        return {
            "mode": "fallback",
            "error": type(self._error).__name__ if self._error else None,
        }


logger.info("Initializing shared TruePresence decision runtime")
try:
    from truepresence.core.orchestrator_v3 import TruePresenceOrchestratorV3
    from truepresence.ensemble.orchestrator import TruePresenceEnsembleRuntime

    orchestrator = TruePresenceEnsembleRuntime(TruePresenceOrchestratorV3())
except Exception as exc:
    logger.warning("Falling back to lightweight TruePresence runtime: %s", exc)
    orchestrator = _FallbackOrchestrator(exc)

decision_engine = TruePresenceDecisionEngine(ensemble_runtime=orchestrator)
logger.info("Shared runtime ready")
