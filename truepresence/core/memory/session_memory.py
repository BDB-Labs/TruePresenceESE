"""
Temporal Memory Layer for TruePresence

This module provides session memory with rolling-window history and drift detection
to prevent bots from resetting behavior on each event.
"""

import time
from collections import deque
from typing import Dict, Any, List


class SessionMemory:
    """
    Session Memory with rolling-window history and behavioral drift detection.
    
    This class maintains a history of events and provides methods to detect
    temporal behavioral instability that might indicate bot activity.
    """
    
    def __init__(self, maxlen: int = 1000):
        """
        Initialize session memory.
        
        Args:
            maxlen: Maximum number of events to store in memory
        """
        self.events = deque(maxlen=maxlen)
        
    def add(self, event: Dict[str, Any]):
        """
        Add an event to memory with timestamp.
        
        Args:
            event: Event dictionary to add to memory
        """
        event = dict(event)  # Create a copy to avoid modifying original
        event["ts"] = time.time()
        self.events.append(event)
        
    def window(self, n: int = 50) -> List[Dict[str, Any]]:
        """
        Get a rolling window of recent events.
        
        Args:
            n: Number of recent events to return
            
        Returns:
            List of most recent n events
        """
        return list(self.events)[-n:]
        
    def drift(self) -> float:
        """
        Calculate temporal drift - a measure of behavioral instability.
        
        This method calculates the variance in time intervals between events
        as a measure of how consistent/stable the behavior is over time.
        
        Returns:
            Float representing temporal drift (variance of intervals)
        """
        if len(self.events) < 2:
            return 0.0
            
        # Calculate time intervals between consecutive events
        intervals = []
        for i in range(1, len(self.events)):
            interval = self.events[i]["ts"] - self.events[i-1]["ts"]
            intervals.append(interval)
            
        if len(intervals) < 2:
            return 0.0
            
        # Calculate mean and variance
        mean_interval = sum(intervals) / len(intervals)
        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        
        return float(variance)
        
    def clear(self):
        """Clear all events from memory."""
        self.events.clear()
        
    def __len__(self) -> int:
        """Return number of events in memory."""
        return len(self.events)