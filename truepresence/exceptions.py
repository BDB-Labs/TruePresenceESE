"""
TruePresence Exceptions

Custom exceptions for TruePresence system with proper error propagation.
Critical systems should not fail silently.
"""

from typing import Any, Optional, Dict


class TruePresenceError(Exception):
    """Base exception for TruePresence system."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }


class OrchestratorError(TruePresenceError):
    """Orchestrator-level errors."""
    pass


class RoleError(TruePresenceError):
    """Role execution errors."""
    
    def __init__(self, message: str, role_name: str, original_error: Optional[Exception] = None):
        details = {"role": role_name}
        if original_error:
            details["original_error"] = str(original_error)
            details["error_type"] = type(original_error).__name__
        super().__init__(message, details)
        self.role_name = role_name


class EvidenceError(TruePresenceError):
    """Evidence processing errors."""
    pass


class SynthesisError(TruePresenceError):
    """Synthesis/aggregation errors."""
    pass


class ConfigurationError(TruePresenceError):
    """Configuration and setup errors."""
    pass


class SessionError(TruePresenceError):
    """Session management errors."""
    pass


class AdaptiveSystemError(TruePresenceError):
    """Adaptive/learning system errors."""
    pass


def wrap_role_error(role_name: str, operation: str, original_error: Exception) -> RoleError:
    """Helper to wrap errors from role operations."""
    return RoleError(
        message=f"Role '{role_name}' failed during {operation}: {str(original_error)}",
        role_name=role_name,
        original_error=original_error
    )


def propagate_error(error: Exception, context: str) -> None:
    """
    Re-raise errors with context for critical systems.
    
    For critical systems, we should not silently swallow errors.
    This function ensures errors propagate with full context.
    """
    if isinstance(error, TruePresenceError):
        raise error
    
    # Wrap non-TruePresence errors
    raise TruePresenceError(
        message=f"Unexpected error in {context}: {str(error)}",
        details={"context": context, "original_error": str(error)}
    )