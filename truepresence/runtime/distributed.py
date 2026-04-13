"""
Distributed Runtime for TruePresence

This module provides Redis-backed session storage to enable horizontal scaling
and multi-node session sharing across distributed deployments.
"""

import json
import time
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class DistributedRuntime:
    """
    Distributed Runtime using Redis for session management.
    
    This class provides distributed session storage and event management
    to enable horizontal scaling and multi-node session sharing.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", ttl_seconds: int = 3600):
        """
        Initialize Distributed Runtime.
        
        Args:
            redis_url: Redis connection URL
            ttl_seconds: Time-to-live for session data in seconds (default: 1 hour)
        """
        self.ttl_seconds = ttl_seconds
        
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                # Test connection
                self.redis_client.ping()
                self.available = True
                logger.info("DistributedRuntime connected to Redis")
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}")
                self.redis_client = None
                self.available = False
        else:
            logger.warning("Redis package not available. Using in-memory fallback.")
            self.redis_client = None
            self.available = False
            self._memory_store = {}
    
    def _get_session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"truepresence:session:{session_id}"
    
    def _get_events_key(self, session_id: str) -> str:
        """Generate Redis key for session events."""
        return f"truepresence:events:{session_id}"
    
    def store_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Store session data in Redis.
        
        Args:
            session_id: Unique session identifier
            session_data: Session data to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._get_session_key(session_id)
            session_data["updated_at"] = time.time()
            
            if self.available and self.redis_client:
                # Store as JSON with TTL
                self.redis_client.setex(
                    key,
                    self.ttl_seconds,
                    json.dumps(session_data)
                )
            else:
                # Fallback to in-memory
                self._memory_store[key] = session_data
                
            return True
        except Exception as e:
            logger.error(f"Error storing session: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load session data from Redis.
        
        Args:
            session_id: Session identifier to load
            
        Returns:
            Session data dictionary or None if not found
        """
        try:
            key = self._get_session_key(session_id)
            
            if self.available and self.redis_client:
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            else:
                # Fallback to in-memory
                session_data = self._memory_store.get(key)
                if session_data:
                    return session_data
                    
            return None
        except Exception as e:
            logger.error(f"Error loading session: {e}")
            return None
    
    def append_event(self, session_id: str, event: Dict[str, Any]) -> bool:
        """
        Append an event to the session's event history.
        
        Args:
            session_id: Session identifier
            event: Event data to append
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._get_events_key(session_id)
            event["timestamp"] = time.time()
            
            if self.available and self.redis_client:
                # Use Redis list for events
                self.redis_client.rpush(key, json.dumps(event))
                # Set expiry on the list
                self.redis_client.expire(key, self.ttl_seconds)
            else:
                # Fallback to in-memory
                if key not in self._memory_store:
                    self._memory_store[key] = []
                self._memory_store[key].append(event)
                
            return True
        except Exception as e:
            logger.error(f"Error appending event: {e}")
            return False
    
    def get_events(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get session events.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of events to retrieve
            
        Returns:
            List of events
        """
        try:
            key = self._get_events_key(session_id)
            
            if self.available and self.redis_client:
                # Get last 'limit' events from the list
                events_data = self.redis_client.lrange(key, -limit, -1)
                return [json.loads(e) for e in events_data]
            else:
                # Fallback to in-memory
                events = self._memory_store.get(key, [])
                return events[-limit:]
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its events.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_key = self._get_session_key(session_id)
            events_key = self._get_events_key(session_id)
            
            if self.available and self.redis_client:
                self.redis_client.delete(session_key, events_key)
            else:
                self._memory_store.pop(session_key, None)
                self._memory_store.pop(events_key, None)
                
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    def update_session_field(self, session_id: str, field: str, value: Any) -> bool:
        """
        Update a specific field in the session.
        
        Args:
            session_id: Session identifier
            field: Field name to update
            value: New value for the field
            
        Returns:
            True if successful, False otherwise
        """
        session = self.load_session(session_id)
        if session is None:
            session = {}
            
        session[field] = value
        return self.store_session(session_id, session)
    
    def get_session_count(self) -> int:
        """
        Get the number of active sessions.
        
        Returns:
            Number of active sessions
        """
        if self.available and self.redis_client:
            keys = self.redis_client.keys("truepresence:session:*")
            return len(keys)
        else:
            return len([k for k in self._memory_store.keys() if "session:" in k])
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the distributed runtime.
        
        Returns:
            Health status dictionary
        """
        if self.available and self.redis_client:
            try:
                info = self.redis_client.info()
                return {
                    "status": "healthy",
                    "redis_connected": True,
                    "redis_version": info.get("redis_version", "unknown"),
                    "active_sessions": self.get_session_count()
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "redis_connected": False,
                    "error": str(e)
                }
        else:
            return {
                "status": "using_fallback",
                "redis_connected": False,
                "active_sessions": self.get_session_count()
            }