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
from truepresence.runtime.wiring import load_required_runtime

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
        self.mode = "fallback"
        self.degraded_reason = type(error).__name__ if error else None

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
orchestrator = load_required_runtime(
    loader=lambda: __import__("truepresence.ensemble.orchestrator", fromlist=["TruePresenceEnsembleRuntime"]).TruePresenceEnsembleRuntime(
        __import__("truepresence.core.orchestrator_v3", fromlist=["TruePresenceOrchestratorV3"]).TruePresenceOrchestratorV3()
    ),
    fallback_factory=lambda exc: _FallbackOrchestrator(exc),
    logger=logger,
)

decision_engine = TruePresenceDecisionEngine(ensemble_runtime=orchestrator)
logger.info("Shared runtime ready")
