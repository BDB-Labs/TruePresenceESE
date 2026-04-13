"""
TruePresence Orchestrator V3 - Enhanced Central Orchestrator

This upgraded orchestrator integrates IdentityGraph, AgentCouncil, and DistributedRuntime
into a unified evaluate method, providing enhanced cross-session detection and
distributed deployment support.
"""

from typing import Dict, Any, Optional
import os
import logging
from truepresence.core.synthesis.synth import EnsembleSynthesis
from truepresence.core.memory.session_memory import SessionMemory
from truepresence.adaptive.weighting import AdaptiveWeights
from truepresence.agents.council import AgentCouncil
from truepresence.memory.identity_graph import IdentityGraph
from truepresence.runtime.distributed import DistributedRuntime
from truepresence.exceptions import OrchestratorError, wrap_role_error

logger = logging.getLogger(__name__)


class TruePresenceOrchestratorV3:
    """
    Enhanced Central Orchestrator (Version 3) for TruePresence.
    
    This version integrates:
    - IdentityGraph for cross-session bot clustering
    - AgentCouncil for structured multi-agent debate
    - DistributedRuntime for horizontal scaling support
    """
    
    def __init__(self, redis_url: str = None):
        """
        Initialize the V3 orchestrator.

        Args:
            redis_url: Optional Redis URL — defaults to REDIS_URL env var
        """
        # Core components
        self.memory = SessionMemory()
        self.adaptive = AdaptiveWeights()
        self.synthesis = EnsembleSynthesis()

        # Enhanced components
        self.council = AgentCouncil()
        self.identity_graph = IdentityGraph(similarity_threshold=0.75)

        # Distributed runtime — wire from env var if not explicitly passed
        redis_url = redis_url or os.environ.get("REDIS_URL")
        self.distributed = None
        if redis_url:
            try:
                self.distributed = DistributedRuntime(redis_url=redis_url)
                logger.info(f"DistributedRuntime connected to Redis")
            except Exception as e:
                logger.warning(f"Could not initialize distributed runtime: {e}")

        # Initialize roles
        self.roles = {}
        self._initialize_roles()
        
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
                
                if role_name != "synthesizer":
                    self.synthesis.add_role(role_name)
                    self.council.add_agent(role_name, self.roles[role_name])
            except Exception as e:
                logger.error(f"FAILED to initialize role {role_name}: {e}", exc_info=True)
                raise OrchestratorError(
                    message=f"Failed to initialize role {role_name}",
                    details={"role": role_name, "error": str(e)}
                )
    
    def build_evidence(self, session: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
        """Build evidence from session and event data."""
        evidence = {
            "session": dict(session),
            "event": dict(event),
            "historical": list(self.memory.window(50))
        }
        
        temporal_drift = self.memory.drift()
        evidence["temporal_drift"] = temporal_drift
        
        # Add cross-session context if available
        session_id = session.get("session_id")
        if session_id:
            # Check identity graph for connected sessions
            connected = self.identity_graph.get_connected_sessions(session_id)
            evidence["cross_session_connections"] = len(connected)
            
            if connected:
                cluster_risk = self.identity_graph.get_session_risk(session_id)
                evidence["cluster_risk"] = cluster_risk
        
        return evidence
    
    def evaluate(
        self,
        session_id: str,
        session: Dict[str, Any],
        event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main evaluation method with full integration.
        
        Args:
            session_id: Unique session identifier
            session: Current session dictionary
            event: Current event dictionary
            
        Returns:
            Complete decision trace with enhanced metrics
        """
        # Store event in memory
        self.memory.add(event)
        
        # Build evidence
        evidence = self.build_evidence(session, event)
        
        # Run all roles
        role_outputs = {}
        for role_name, role in self.roles.items():
            if role_name != "synthesizer":
                try:
                    role_outputs[role_name] = role.evaluate(evidence, session)
                except Exception as e:
                    logger.error(f"Role {role_name} FAILED during evaluate: {e}", exc_info=True)
                    raise wrap_role_error(role_name, "evaluate", e)
        
        # Run agent council for structured debate
        council_result = self.council.evaluate(evidence, session)
        
        # Synthesize results using ensemble
        final_result = self.synthesis.synthesize(role_outputs, evidence)
        
        # Integrate council metrics
        final_result["council_confidence"] = council_result.get("confidence", 0.5)
        final_result["council_disagreement"] = council_result.get("disagreement", 0.0)
        final_result["council_consensus"] = council_result.get("consensus", 0.5)
        
        # Add cross-session risk assessment
        cross_session_risk = 0.0
        if session_id:
            cross_session_risk = self.identity_graph.get_session_risk(session_id)
        final_result["cross_session_risk"] = cross_session_risk
        
        # Calculate final decision
        human_prob = final_result.get("human_probability", 0.5)
        confidence = final_result.get("confidence", 0.5)
        
        # Combine signals for final decision
        combined_score = (
            human_prob * 0.6 +
            council_result.get("consensus", 0.5) * 0.2 +
            (1 - cross_session_risk) * 0.2
        )
        
        if combined_score > 0.75:
            decision = "allow"
        elif combined_score < 0.35:
            decision = "block"
        elif combined_score < 0.5:
            decision = "challenge"
        else:
            decision = "review"
        
        final_result["decision"] = decision
        final_result["combined_score"] = combined_score
        
        # Update distributed runtime if available
        if self.distributed and self.distributed.available:
            self.distributed.append_event(session_id, event)
            self.distributed.update_session_field(session_id, "last_evaluation", final_result)
        
        # Add session to identity graph
        session_data = dict(session)
        session_data["detection"] = {
            "human_probability": human_prob,
            "bot_probability": 1 - human_prob,
            "confidence": confidence,
            "decision": decision
        }
        self.identity_graph.add_session(session_id, session_data)
        
        # Prepare response
        return {
            "session_id": session_id,
            "evidence": evidence,
            "roles": role_outputs,
            "council": council_result,
            "synthesis": final_result,
            "decision": decision,
            "human_probability": human_prob,
            "bot_probability": 1 - human_prob,
            "confidence": confidence,
            "risk_factors": self._extract_risk_factors(final_result, council_result),
            "reasoning_trace": self._build_reasoning_trace(role_outputs, council_result),
            "temporal_signals": {
                "drift": evidence.get("temporal_drift", 0.0),
                "cross_session_risk": cross_session_risk
            }
        }
    
    def _extract_risk_factors(
        self,
        synthesis_result: Dict,
        council_result: Dict
    ) -> list:
        """Extract risk factors from results."""
        risk_factors = []
        
        if synthesis_result.get("variance", 0) > 0.1:
            risk_factors.append("high_role_variance")
            
        if synthesis_result.get("disagreement", 0) > 0.3:
            risk_factors.append("high_agent_disagreement")
            
        if council_result.get("disagreement", 0) > 0.4:
            risk_factors.append("council_disagreement")
            
        if synthesis_result.get("confidence", 1) < 0.5:
            risk_factors.append("low_confidence")
            
        return risk_factors
    
    def _build_reasoning_trace(
        self,
        role_outputs: Dict,
        council_result: Dict
    ) -> Dict[str, str]:
        """Build reasoning trace for each role."""
        trace = {}
        
        for role_name, output in role_outputs.items():
            human_prob = output.get("human_probability", 0.5)
            if human_prob > 0.7:
                trace[role_name] = f"Indicates human (probability: {human_prob:.2f})"
            elif human_prob < 0.3:
                trace[role_name] = f"Indicates bot (probability: {human_prob:.2f})"
            else:
                trace[role_name] = f"Uncertain (probability: {human_prob:.2f})"
        
        # Add council reasoning
        consensus = council_result.get("consensus", 0.5)
        trace["council"] = f"Consensus probability: {consensus:.2f}"
        
        return trace
    
    def get_session_cluster(self, session_id: str) -> set:
        """Get all connected sessions in the identity graph."""
        return self.identity_graph.get_session_cluster(session_id)
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on orchestrator components."""
        health = {
            "memory_events": len(self.memory),
            "adaptive_weights": self.adaptive.get_weights(),
            "identity_graph_sessions": len(self.identity_graph.sessions)
        }
        
        if self.distributed:
            health["distributed"] = self.distributed.health_check()
        
        return health