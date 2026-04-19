"""
TruePresence Orchestrator V3 - Enhanced Central Orchestrator

This upgraded orchestrator integrates IdentityGraph, AgentCouncil, and DistributedRuntime
into a unified evaluate method, providing enhanced cross-session detection and
distributed deployment support.
"""

import logging
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from truepresence.adaptive.weighting import AdaptiveWeights
from truepresence.agents.council import AgentCouncil
from truepresence.core.synthesis.synth import EnsembleSynthesis
from truepresence.evidence import (
    ArgumentGraphBuilder,
    EvidencePacket,
    EvidencePacketBuilder,
)
from truepresence.exceptions import (
    ConfigurationError,
    OrchestratorError,
    wrap_role_error,
)
from truepresence.memory.identity_graph import IdentityGraph
from truepresence.memory.session_timeline import SessionTimeline
from truepresence.runtime.distributed import DistributedRuntime
from truepresence.runtime.wiring import allow_lenient_wiring

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
        self.memory = SessionTimeline()
        self.adaptive = AdaptiveWeights()
        self.synthesis = EnsembleSynthesis()
        self.packet_builder = EvidencePacketBuilder()
        self.argument_graph_builder = ArgumentGraphBuilder()

        # Enhanced components
        self.council = AgentCouncil()
        self.identity_graph = IdentityGraph(similarity_threshold=0.75)

        # Distributed runtime — wire from env var if not explicitly passed
        redis_url = redis_url or os.environ.get("REDIS_URL")
        self.distributed = None
        if redis_url:
            try:
                self.distributed = DistributedRuntime(redis_url=redis_url)
                if not self.distributed.available:
                    raise ConfigurationError(
                        message="Distributed runtime is unavailable while REDIS_URL is configured",
                        details={"redis_url_configured": True},
                    )
                logger.info("DistributedRuntime connected to Redis")
            except Exception as e:
                if allow_lenient_wiring():
                    logger.warning(f"Could not initialize distributed runtime in lenient wiring mode: {e}")
                else:
                    raise

        # Initialize roles
        self.roles = {}
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._initialize_roles()
        
    def _initialize_roles(self):
        """Initialize available roles dynamically using unified Role interface."""
        from truepresence.core.roles.base import (
            AdversarialRole,
            LivenessRole,
            MediationRole,
            RelayRole,
            SynthesizerRole,
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
                ) from e
    
    def build_evidence(
        self,
        session: Dict[str, Any],
        event: Dict[str, Any],
        evidence_packet: EvidencePacket | None = None,
        argument_graph=None,
    ) -> tuple[Dict[str, Any], EvidencePacket, Any]:
        """Build role evidence from a product-level evidence packet."""
        session_id = session.get("session_id") or event.get("session_id")
        packet = evidence_packet or self.packet_builder.build(
            session_id=session_id,
            surface=event.get("context", {}).get("platform", "unknown"),
            event=event,
            session=session,
            session_history=list(self.memory.window(session_id, 50)),
            tenant_id=session.get("tenant_id"),
        )

        temporal_drift = self.memory.drift(session_id)
        packet.metadata["temporal_drift"] = temporal_drift

        if session_id:
            connected = self.identity_graph.get_connected_sessions(session_id)
            packet.identity_refs["connected_sessions"] = len(connected)
            if connected:
                packet.identity_refs["cluster_risk"] = self.identity_graph.get_session_risk(session_id)

        graph = argument_graph or self.argument_graph_builder.build(packet)
        evidence = packet.as_role_evidence(graph)
        evidence["historical"] = list(self.memory.window(session_id, 50))
        evidence["temporal_drift"] = temporal_drift
        evidence["cross_session_connections"] = packet.identity_refs.get("connected_sessions", 0)
        evidence["cluster_risk"] = packet.identity_refs.get("cluster_risk", 0.0)
        evidence["argument_graph"] = graph.summary()
        return evidence, packet, graph

    def run(self, evidence_packet: EvidencePacket, argument_graph, session: Dict[str, Any] | None = None) -> Dict[str, Any]:
        session_data = dict(session or evidence_packet.session_context or {})
        session_data.setdefault("session_id", evidence_packet.session_id)
        return self._evaluate_internal(
            session_id=evidence_packet.session_id,
            session=session_data,
            event=evidence_packet.latest_event,
            evidence_packet=evidence_packet,
            argument_graph=argument_graph,
        )
    
    def evaluate(
        self,
        session_id: str | Dict[str, Any] | None = None,
        session: Dict[str, Any] | None = None,
        event: Dict[str, Any] | None = None,
        *,
        evidence_packet: EvidencePacket | None = None,
        argument_graph=None,
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
        if event is None and isinstance(session_id, dict) and isinstance(session, dict):
            session_data = dict(session_id)
            event_data = dict(session)
            resolved_session_id = session_data.get("session_id") or event_data.get("session_id")
            return self._evaluate_internal(
                session_id=resolved_session_id,
                session=session_data,
                event=event_data,
                evidence_packet=evidence_packet,
                argument_graph=argument_graph,
            )

        if evidence_packet is not None:
            session_data = dict(session or evidence_packet.session_context or {})
            session_data.setdefault("session_id", evidence_packet.session_id)
            return self.run(evidence_packet, argument_graph, session=session_data)

        if session_id is None or session is None or event is None:
            raise OrchestratorError(
                message="evaluate requires either (session_id, session, event) or evidence_packet",
                details={"session_id": session_id},
            )

        return self._evaluate_internal(
            session_id=str(session_id),
            session=dict(session),
            event=dict(event),
            evidence_packet=evidence_packet,
            argument_graph=argument_graph,
        )

    def _evaluate_internal(
        self,
        *,
        session_id: str,
        session: Dict[str, Any],
        event: Dict[str, Any],
        evidence_packet: EvidencePacket | None = None,
        argument_graph=None,
    ) -> Dict[str, Any]:
        self.memory.add_event(session_id, event)

        evidence, packet, graph = self.build_evidence(
            session,
            event,
            evidence_packet=evidence_packet,
            argument_graph=argument_graph,
        )
        
        # Run roles in parallel using ThreadPoolExecutor
        role_outputs = {}
        futures = {}
        
        for role_name, role in self.roles.items():
            if role_name != "synthesizer":
                futures[self._executor.submit(role.evaluate, evidence, session)] = role_name

        for future in futures:
            role_name = futures[future]
            try:
                role_outputs[role_name] = future.result()
            except Exception as e:
                logger.error(f"Role {role_name} FAILED during evaluate: {e}", exc_info=True)
                raise wrap_role_error(role_name, "evaluate", e) from e
        
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
            "evidence_packet": packet.model_dump(),
            "argument_graph": graph.model_dump(),
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
