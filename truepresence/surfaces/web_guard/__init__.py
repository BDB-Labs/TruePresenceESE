"""Web Guard surface contracts.

The browser SDK collects telemetry only. The server guard API remains authoritative.
Clients never make the final trust decision.
"""

from .sdk_protocol import WebGuardDecisionEnvelope, WebGuardEvent

__all__ = ["WebGuardDecisionEnvelope", "WebGuardEvent"]
