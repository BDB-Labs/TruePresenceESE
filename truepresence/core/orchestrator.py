"""
TruePresence System Brain - Central Orchestrator

This module provides the central decision authority that sequences:
1. Build evidence
2. Run all roles  
3. Apply adaptive weights
4. Synthesize results
5. Update session
6. Return full decision trace

CRITICAL: This system does NOT fail silently. All errors are propagated
with full context for debugging and monitoring.
"""

from typing import Dict, Any, Optional
import logging
from truepresence.core.synthesis.synth import EnsembleSynthesis
from truepresence.core.memory.session_memory import SessionMemory
from truepresence.adaptive.weighting import AdaptiveWeights
from truepresence.exceptions import OrchestratorError, wrap_role_error

logger = logging.getLogger(__name__)


class TruePresenceOrchestrator:
    """
    Central Orchestrator for TruePresence system.
    
    This class serves as the single decision authority that sequences all operations
    and maintains the system's state and adaptive learning capabilities.
    
    CRITICAL: Errors are NOT swallowed - they are logged and propagated.
    """
    
    def __init__(self):
        """Initialize the orchestrator with memory, adaptive weights, and synthesis engine."""
        logger.info("Initializing TruePresenceOrchestrator")
        
        self.memory = SessionMemory()
        self.adaptive = AdaptiveWeights()
        self.synthesis = EnsembleSynthesis()
        
        # Initialize roles from unified base interface
        self.roles = {}
        self._initialize_roles()
        
        logger.info(f"Orchestrator initialized with roles: {list(self.roles.keys())}")
        
    def _initialize_roles(self):
        """Initialize available roles dynamically using unified Role interface."""
        from truepresence.core.roles.base import (
            LivenessRole, AdversarialRole, MediationRole, RelayRole, SynthesizerRole
        )
        
        role_mapping = {
            "liveness": LivenessRole,
            "adversarial": AdversarialRole,
            "mediation": MediationRole,
            "relay": RelayRole,
            "synthesizer": SynthesizerRole
        }
        
        for role_name, role_class in role_mapping.items():
            try:
                self.roles[role_name] = role_class()
                # Add to synthesis engine (except synthesizer - it's the final step)
                if role_name != "synthesizer":
                    self.synthesis.add_role(role_name)
            except Exception as e:
                logger.error(f"FAILED to initialize role {role_name}: {e}", exc_info=True)
                raise OrchestratorError(
                    message=f"Failed to initialize role {role_name}",
                    details={"role": role_name, "error": str(e)}
                )
    
    def build_evidence(self, session: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build evidence dictionary from session and event data.
        
        Args:
            session: Current session dictionary
            event: Current event dictionary
            
        Returns:
            Evidence dictionary containing all relevant data for evaluation
            
        Raises:
            OrchestratorError: If evidence building fails
        """
        try:
            evidence = {
                "session": dict(session),
                "event": dict(event),
                "historical": list(self.memory.window(session.get("session_id", "default"), 50))
            }
            
            # Add temporal drift information
            temporal_drift = self.memory.drift(session.get("session_id", "default"))
            evidence["temporal_drift"] = temporal_drift
            
            return evidence
        except Exception as e:
            logger.error(f"Evidence building failed: {e}", exc_info=True)
            raise OrchestratorError(
                message=f"Failed to build evidence: {str(e)}",
                details={"session_id": session.get("session_id")}
            )
    
    def evaluate(self, session: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main evaluation method that sequences all operations.
        
        Args:
            session: Current session dictionary
            event: Current event dictionary
            
        Returns:
            Complete decision trace including evidence, role outputs, weights, and final decision
            
        Raises:
            OrchestratorError: If evaluation fails at any step
        """
        # Add event to memory
        self.memory.add(session.get("session_id", "default"), event)
        
        # Build evidence
        evidence = self.build_evidence(session, event)
        
        # Run all roles - CRITICAL: Do NOT catch and swallow errors
        role_outputs = {}
        for role_name, role in self.roles.items():
            try:
                # Use unified evaluate method
                role_outputs[role_name] = role.evaluate(evidence, session)
            except Exception as e:
                logger.error(f"Role {role_name} FAILED during evaluate: {e}", exc_info=True)
                raise wrap_role_error(role_name, "evaluate", e)
        
        # Store role outputs in evidence for synthesizer
        evidence["role_outputs"] = role_outputs
        
        # Synthesize results - do NOT catch errors silently
        try:
            final_result = self.synthesis.synthesize(role_outputs, evidence)
        except Exception as e:
            logger.error(f"Synthesis FAILED: {e}", exc_info=True)
            raise OrchestratorError(
                message=f"Synthesis failed: {str(e)}",
                details={"role_outputs": list(role_outputs.keys())}
            )
        
        # Calculate final decision
        human_prob = final_result.get("human_probability", 0.5)
        confidence = final_result.get("confidence", 0.5)
        
        if human_prob > 0.65:
            decision = "allow"
        elif human_prob > 0.35:
            decision = "challenge"
        else:
            decision = "block"
        
        final_result["decision"] = decision
        
        # Update session with final result
        session.update({
            "last_evaluation": final_result,
            "temporal_drift": evidence.get("temporal_drift", 0.0)
        })
        
        # Return full decision trace
        return {
            "evidence": evidence,
            "roles": role_outputs,
            "weighted_roles": {k: v.get("human_probability", 0.5) * self.adaptive.weights.get(k, 1.0) 
                             for k, v in role_outputs.items()},
            "final": final_result,
            "memory_drift": evidence["temporal_drift"],
            "session_update": session
        }
