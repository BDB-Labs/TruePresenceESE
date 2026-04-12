"""
TruePresence Python SDK

This SDK provides a simple Python client for integrating TruePresence
bot detection into applications.
"""

import requests
from typing import Dict, Any, Optional, List
import uuid


class TruePresenceClient:
    """
    Python client for TruePresence ESE API.
    
    Usage:
        client = TruePresenceClient(api_url="http://localhost:8000")
        session_id = client.create_session()
        
        # Send events for evaluation
        result = client.evaluate(
            session_id=session_id,
            event_type="key_timing",
            timestamp=time.time(),
            payload={"interval_ms": 120}
        )
        
        if result.decision == "block":
            print("Bot detected!")
    """
    
    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        timeout: int = 30,
        mode: str = "sdk"
    ):
        """
        Initialize TruePresence client.
        
        Args:
            api_url: Base URL of the TruePresence API
            timeout: Request timeout in seconds
            mode: Default mode (sdk or gatekeeper)
        """
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.mode = mode
        self.session_id = None
        
    def create_session(self, assurance_level: str = "A1") -> str:
        """
        Create a new session.
        
        Args:
            assurance_level: Assurance level (A1-A4)
            
        Returns:
            Session ID string
        """
        response = requests.post(
            f"{self.api_url}/session/create",
            json={"assurance_level": assurance_level},
            timeout=self.timeout
        )
        response.raise_for_status()
        self.session_id = response.json()["session_id"]
        return self.session_id
        
    def evaluate(
        self,
        session_id: str = None,
        event_type: str = None,
        timestamp: float = None,
        payload: Dict[str, Any] = None,
        features: Dict[str, float] = None,
        context: Dict[str, Any] = None,
        mode: str = None
    ) -> Dict[str, Any]:
        """
        Evaluate an event for bot detection.
        
        Args:
            session_id: Session ID (uses default if not provided)
            event_type: Type of event
            timestamp: Unix timestamp
            payload: Event payload
            features: Behavioral features
            context: Additional context
            mode: Evaluation mode (sdk or gatekeeper)
            
        Returns:
            Evaluation result dictionary
        """
        if session_id is None:
            session_id = self.session_id or self.create_session()
            
        if timestamp is None:
            import time
            timestamp = time.time()
            
        if payload is None:
            payload = {}
            
        event = {
            "event_type": event_type or "unknown",
            "timestamp": timestamp,
            "payload": payload
        }
        
        if features:
            event["features"] = features
            
        request_data = {
            "mode": mode or self.mode,
            "session_id": session_id,
            "event": event
        }
        
        if context:
            request_data["context"] = context
            
        response = requests.post(
            f"{self.api_url}/v1/evaluate",
            json=request_data,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        return response.json()
        
    def evaluate_stream(
        self,
        session_id: str = None,
        events: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluate a stream of events.
        
        Args:
            session_id: Session ID
            events: List of event dictionaries
            
        Returns:
            List of evaluation results
        """
        if session_id is None:
            session_id = self.session_id or self.create_session()
            
        results = []
        for event in (events or []):
            result = self.evaluate(
                session_id=session_id,
                event_type=event.get("event_type"),
                timestamp=event.get("timestamp"),
                payload=event.get("payload", {}),
                features=event.get("features")
            )
            results.append(result)
            
        return results
        
    def check_bot(self, session_id: str = None, threshold: float = 0.5) -> bool:
        """
        Quick check if session is likely a bot.
        
        Args:
            session_id: Session ID
            threshold: Bot probability threshold
            
        Returns:
            True if likely bot, False otherwise
        """
        result = self.evaluate(session_id=session_id)
        return result.get("bot_probability", 0) > threshold
        
    def get_session_cluster(self, session_id: str) -> List[str]:
        """
        Get connected sessions from identity graph.
        
        Args:
            session_id: Session ID to query
            
        Returns:
            List of connected session IDs
        """
        response = requests.get(
            f"{self.api_url}/v1/sessions/{session_id}/cluster",
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json().get("cluster", [])
        
    def reset_session(self, session_id: str) -> bool:
        """
        Reset session memory.
        
        Args:
            session_id: Session ID to reset
            
        Returns:
            True if successful
        """
        response = requests.post(
            f"{self.api_url}/v1/sessions/{session_id}/reset",
            timeout=self.timeout
        )
        return response.status_code == 200
        
    def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        response = requests.get(
            f"{self.api_url}/health",
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()


# Convenience functions for quick integration
def quick_check(event: Dict[str, Any], api_url: str = "http://localhost:8000") -> bool:
    """
    Quick bot check for a single event.
    
    Args:
        event: Event dictionary
        api_url: API URL
        
    Returns:
        True if likely bot
    """
    client = TruePresenceClient(api_url=api_url)
    session_id = client.create_session()
    result = client.evaluate(session_id=session_id, **event)
    return result.get("decision") == "block"


# Export main classes
__all__ = ["TruePresenceClient", "quick_check"]