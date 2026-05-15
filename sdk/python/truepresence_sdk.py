"""
TruePresence Python SDK

This SDK provides a Python client for integrating TruePresence bot detection into applications.

REST endpoints are mounted at `/api` on the TruePresence server. Pass `api_url` as the server
origin (e.g. http://localhost:8000) or include the `/api` suffix; both normalize correctly.
When `TRUEPRESENCE_LEGACY_REST_TOKEN` is enabled on the server, pass the same value as
`service_token` for legacy REST calls (session/create, v1/evaluate, cluster, reset).
"""

from __future__ import annotations

from typing import Any, Dict, List

import requests


def _resolve_api_urls(api_url: str) -> tuple[str, str]:
    raw = api_url.rstrip("/")
    if raw.endswith("/api"):
        rest_base = raw
        api_origin = raw[:-4] if len(raw) > 4 else raw
    else:
        api_origin = raw
        rest_base = f"{raw}/api"
    return api_origin, rest_base


class TruePresenceClient:
    """
    Python client for TruePresence ESE API.

    Usage:
        client = TruePresenceClient(api_url="http://localhost:8000")
        session_id = client.create_session()

        result = client.evaluate(
            session_id=session_id,
            event_type="key_timing",
            timestamp=time.time(),
            payload={"interval_ms": 120},
        )

        if result["decision"] == "block":
            print("Bot detected!")
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        timeout: int = 30,
        mode: str = "sdk",
        service_token: str | None = None,
    ) -> None:
        """
        Args:
            api_url: Server origin or URL ending in `/api`.
            timeout: Request timeout in seconds.
            mode: Default evaluation mode (sdk or gatekeeper).
            service_token: Optional token matching server TRUEPRESENCE_LEGACY_REST_TOKEN.
        """
        self.api_origin, self.rest_base = _resolve_api_urls(api_url)
        self.timeout = timeout
        self.mode = mode
        self.session_id = None
        self.service_token = service_token

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.service_token:
            headers["X-TruePresence-Service-Token"] = self.service_token
        return headers

    def create_session(self, assurance_level: str = "A1") -> str:
        """Create a new session."""
        response = requests.post(
            f"{self.rest_base}/session/create",
            json={"assurance_level": assurance_level},
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        self.session_id = response.json()["session_id"]
        return self.session_id

    def evaluate(
        self,
        session_id: str | None = None,
        event_type: str | None = None,
        timestamp: float | None = None,
        payload: Dict[str, Any] | None = None,
        features: Dict[str, float] | None = None,
        context: Dict[str, Any] | None = None,
        mode: str | None = None,
    ) -> Dict[str, Any]:
        """Evaluate an event for bot detection."""
        if session_id is None:
            session_id = self.session_id or self.create_session()

        if timestamp is None:
            import time

            timestamp = time.time()

        if payload is None:
            payload = {}

        event: Dict[str, Any] = {
            "event_type": event_type or "unknown",
            "timestamp": timestamp,
            "payload": payload,
        }

        if features:
            event["features"] = features

        request_data: Dict[str, Any] = {
            "mode": mode or self.mode,
            "session_id": session_id,
            "event": event,
        }

        if context:
            request_data["context"] = context

        response = requests.post(
            f"{self.rest_base}/v1/evaluate",
            json=request_data,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()

        return response.json()

    def evaluate_stream(
        self,
        session_id: str | None = None,
        events: List[Dict[str, Any]] | None = None,
    ) -> List[Dict[str, Any]]:
        """Evaluate a stream of events."""
        if session_id is None:
            session_id = self.session_id or self.create_session()

        results: List[Dict[str, Any]] = []
        for event in events or []:
            result = self.evaluate(
                session_id=session_id,
                event_type=event.get("event_type"),
                timestamp=event.get("timestamp"),
                payload=event.get("payload", {}),
                features=event.get("features"),
            )
            results.append(result)

        return results

    def check_bot(self, session_id: str | None = None, threshold: float = 0.5) -> bool:
        """Quick check if session is likely a bot."""
        result = self.evaluate(session_id=session_id)
        return result.get("bot_probability", 0) > threshold

    def get_session_cluster(self, session_id: str) -> List[str]:
        """Get connected sessions from identity graph."""
        response = requests.get(
            f"{self.rest_base}/v1/sessions/{session_id}/cluster",
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("cluster", [])

    def reset_session(self, session_id: str) -> bool:
        """Reset session memory."""
        response = requests.post(
            f"{self.rest_base}/v1/sessions/{session_id}/reset",
            headers=self._headers(),
            timeout=self.timeout,
        )
        return response.status_code == 200

    def health_check(self) -> Dict[str, Any]:
        """Check API health (root /health on TruePresence server)."""
        response = requests.get(
            f"{self.api_origin}/health",
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


def quick_check(event: Dict[str, Any], api_url: str = "http://localhost:8000") -> bool:
    """Quick bot check for a single event."""
    client = TruePresenceClient(api_url=api_url)
    session_id = client.create_session()
    result = client.evaluate(
        session_id=session_id,
        event_type=event.get("event_type"),
        timestamp=event.get("timestamp"),
        payload=event.get("payload", {}),
        features=event.get("features"),
    )
    return result.get("decision") == "block"


__all__ = ["TruePresenceClient", "quick_check"]
