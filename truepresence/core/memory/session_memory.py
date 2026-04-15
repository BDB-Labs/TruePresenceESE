"""
Compatibility wrapper for the product-facing SessionTimeline.
"""

from truepresence.memory.session_timeline import SessionTimeline


class SessionMemory(SessionTimeline):
    """Backward-compatible alias for the upgraded temporal timeline."""
