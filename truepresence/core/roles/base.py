"""
Unified Role Interface for TruePresence

This module provides a common base class and interface for all roles,
ensuring consistent method signatures and enabling dynamic role loading.

CRITICAL: This system does NOT fail silently. All errors are propagated
with full context for debugging and monitoring.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Role(ABC):
    """
    Abstract base class for all roles in the TruePresence system.
    
    All roles must implement:
    - evaluate(): Process evidence and return analysis result
    - get_confidence(): Return confidence score for the role's output
    
    Interface designed to work with:
    - ESEEnsembleRuntime (analyze method)
    - TruePresenceOrchestrator (evaluate method)
    - AgentCouncil (evaluate method)
    
    CRITICAL: All errors are logged and re-raised - no silent failures.
    """
    
    def __init__(self):
        self._last_confidence = 0.5
        self._last_error = None
    
    @abstractmethod
    def evaluate(self, evidence: Dict[str, Any], session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluate evidence and return analysis result.
        
        Args:
            evidence: Evidence dictionary containing signals and context
            session: Optional session data
            
        Returns:
            Dictionary with role output including at minimum:
            - human_probability: float (0-1)
            - role: str (role name)
            - confidence: float (0-1)
            
        Raises:
            RoleError: If evaluation fails - errors are NOT swallowed
        """
        pass
    
    @abstractmethod
    def analyze(self, evidence: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze evidence (ESE-compatible interface).
        
        This method provides compatibility with the ESEEnsembleRuntime pipeline.
        
        Args:
            evidence: Evidence dictionary
            context: Optional context
            
        Returns:
            Dictionary with analysis results
            
        Raises:
            RoleError: If analysis fails - errors are NOT swallowed
        """
        pass
    
    def get_confidence(self) -> float:
        """Get confidence score for last evaluation."""
        if self._last_error:
            logger.warning(f"Role {self.get_role_name()} has unhandled error: {self._last_error}")
            return 0.0  # Return explicit 0 instead of default - critical system
        return self._last_confidence
    
    def get_role_name(self) -> str:
        """Get the role name from class name."""
        return self.__class__.__name__.replace('Analyst', '').replace('Reviewer', '').replace('Role', '').lower()
    
    def get_last_error(self) -> Optional[str]:
        """Get last error that occurred - critical for debugging."""
        return self._last_error


class LivenessRole(Role):
    """Liveness detection role - verifies real user presence."""
    
    def __init__(self):
        super().__init__()
        self._role_name = "liveness"
    
    def evaluate(self, evidence: Dict[str, Any], session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate liveness signals."""
        try:
            signals = evidence.get("signals", {})
            liveness_score = signals.get("liveness", 0.0)
            
            # Also check temporal consistency
            temporal_drift = evidence.get("temporal_drift", 0.0)
            
            # Low drift + high liveness = high confidence human
            # High drift could indicate anomalous behavior
            confidence = min(1.0, liveness_score + (0.2 if temporal_drift < 0.1 else 0.0))
            
            self._last_confidence = confidence
            self._last_error = None
            
            return {
                "role": self._role_name,
                "human_probability": liveness_score,
                "confidence": confidence,
                "finding": "presence_confirmed" if liveness_score > 0.6 else "presence_uncertain",
                "impact": "positive" if liveness_score > 0.6 else "neutral"
            }
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"LivenessRole.evaluate failed: {e}", exc_info=True)
            raise
    
    def analyze(self, evidence: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ESE-compatible analyze method."""
        try:
            result = self.evaluate(evidence, context)
            return {
                "role": "liveness_analyst",
                "confidence": result["confidence"],
                "finding": result["finding"],
                "impact": result["impact"]
            }
        except Exception as e:
            logger.error(f"LivenessRole.analyze failed: {e}", exc_info=True)
            raise


class AdversarialRole(Role):
    """Adversarial review role - hunts for 'too perfect' signals."""
    
    def __init__(self):
        super().__init__()
        self._role_name = "adversarial"
    
    def evaluate(self, evidence: Dict[str, Any], session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate for adversarial/bot signals."""
        try:
            signals = evidence.get("signals", {})
            findings = []
            
            # Check optimization risk (too perfect timing)
            opt_risk = signals.get("optimization_risk", 0.0)
            if opt_risk > 0.7:
                findings.append("unnaturally_consistent_timing")
            
            # Check contradiction
            liveness = signals.get("liveness", 0.0)
            mediation = signals.get("ai_mediation", 0.0)
            if liveness > 0.8 and mediation > 0.5:
                findings.append("contradictory_presence_signals")
            
            # Check mouse entropy
            mouse_entropy = signals.get("mouse_entropy", 0.0)
            if mouse_entropy < 0.1:
                findings.append("low_interaction_entropy")
            
            # Calculate bot probability based on risks
            severity = min(1.0, len(findings) * 0.3) if findings else 0.0
            bot_probability = severity
            human_probability = 1.0 - bot_probability
            
            # Confidence increases with more findings
            confidence = min(1.0, 0.5 + severity)
            
            self._last_confidence = confidence
            self._last_error = None
            
            return {
                "role": self._role_name,
                "human_probability": human_probability,
                "bot_probability": bot_probability,
                "confidence": confidence,
                "findings": findings,
                "severity": severity,
                "impact": "negative" if findings else "neutral"
            }
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"AdversarialRole.evaluate failed: {e}", exc_info=True)
            raise
    
    def analyze(self, evidence: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ESE-compatible analyze method."""
        try:
            result = self.evaluate(evidence, context)
            return {
                "role": "adversarial_reviewer",
                "findings": result.get("findings", []),
                "severity": result.get("severity", 0.0),
                "impact": result["impact"]
            }
        except Exception as e:
            logger.error(f"AdversarialRole.analyze failed: {e}", exc_info=True)
            raise


class MediationRole(Role):
    """Mediation/AI detection role - detects AI-assisted users."""
    
    def __init__(self):
        super().__init__()
        self._role_name = "mediation"
    
    def evaluate(self, evidence: Dict[str, Any], session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate for AI mediation signals."""
        try:
            signals = evidence.get("signals", {})
            ai_mediation = signals.get("ai_mediation", 0.0)
            
            # High paste ratio indicates AI assistance
            human_probability = 1.0 - ai_mediation
            confidence = min(1.0, 0.5 + (ai_mediation * 0.5))
            
            self._last_confidence = confidence
            self._last_error = None
            
            return {
                "role": self._role_name,
                "human_probability": human_probability,
                "ai_mediation_score": ai_mediation,
                "confidence": confidence,
                "finding": "ai_assisted" if ai_mediation > 0.5 else "human_origin",
                "impact": "negative" if ai_mediation > 0.5 else "neutral"
            }
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"MediationRole.evaluate failed: {e}", exc_info=True)
            raise
    
    def analyze(self, evidence: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ESE-compatible analyze method."""
        try:
            result = self.evaluate(evidence, context)
            return {
                "role": "mediation_analyst",
                "confidence": result["confidence"],
                "finding": result["finding"],
                "impact": result["impact"]
            }
        except Exception as e:
            logger.error(f"MediationRole.analyze failed: {e}", exc_info=True)
            raise


class RelayRole(Role):
    """Relay/automation detection role - detects automated tools."""
    
    def __init__(self):
        super().__init__()
        self._role_name = "relay"
    
    def evaluate(self, evidence: Dict[str, Any], session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate for relay/automation signals."""
        try:
            signals = evidence.get("signals", {})
            relay_risk = signals.get("relay_risk", 0.0)
            
            # High relay risk indicates automation
            human_probability = 1.0 - relay_risk
            confidence = min(1.0, 0.5 + (relay_risk * 0.5))
            
            self._last_confidence = confidence
            self._last_error = None
            
            return {
                "role": self._role_name,
                "human_probability": human_probability,
                "relay_risk": relay_risk,
                "confidence": confidence,
                "finding": "automated_tool" if relay_risk > 0.6 else "direct_interaction",
                "impact": "negative" if relay_risk > 0.6 else "neutral"
            }
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"RelayRole.evaluate failed: {e}", exc_info=True)
            raise
    
    def analyze(self, evidence: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ESE-compatible analyze method."""
        try:
            result = self.evaluate(evidence, context)
            return {
                "role": "relay_analyst",
                "confidence": result["confidence"],
                "finding": result["finding"],
                "impact": result["impact"]
            }
        except Exception as e:
            logger.error(f"RelayRole.analyze failed: {e}", exc_info=True)
            raise


class SynthesizerRole(Role):
    """Synthesis role - combines all role outputs into final decision."""
    
    def __init__(self):
        super().__init__()
        self._role_name = "synthesizer"
    
    def evaluate(self, evidence: Dict[str, Any], session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Synthesize final decision from role outputs."""
        try:
            # Get role outputs from evidence if available
            role_outputs = evidence.get("role_outputs", {})
            
            if not role_outputs:
                # Fallback to signal-based synthesis
                signals = evidence.get("signals", {})
                liveness = signals.get("liveness", 0.5)
                ai_mediation = signals.get("ai_mediation", 0.0)
                relay_risk = signals.get("relay_risk", 0.3)
                
                human_probability = (liveness * 0.4) + ((1 - ai_mediation) * 0.3) + ((1 - relay_risk) * 0.3)
            else:
                # Average all role human probabilities
                probs = [v.get("human_probability", 0.5) for v in role_outputs.values()]
                human_probability = sum(probs) / len(probs) if probs else 0.5
            
            confidence = 0.7  # Default confidence for synthesis
            self._last_confidence = confidence
            self._last_error = None
            
            return {
                "role": self._role_name,
                "human_probability": human_probability,
                "confidence": confidence,
                "decision": "allow" if human_probability > 0.65 else ("challenge" if human_probability > 0.35 else "block")
            }
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"SynthesizerRole.evaluate failed: {e}", exc_info=True)
            raise
    
    def analyze(self, evidence: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ESE-compatible analyze method."""
        try:
            result = self.evaluate(evidence, context)
            return {
                "trust_score": result["human_probability"],
                "decision": result["decision"],
                "confidence": result["confidence"]
            }
        except Exception as e:
            logger.error(f"SynthesizerRole.analyze failed: {e}", exc_info=True)
            raise
            
            human_probability = (liveness * 0.4) + ((1 - ai_mediation) * 0.3) + ((1 - relay_risk) * 0.3)
        else:
            # Average all role human probabilities
            probs = [v.get("human_probability", 0.5) for v in role_outputs.values()]
            human_probability = sum(probs) / len(probs) if probs else 0.5
        
        confidence = 0.7  # Default confidence for synthesis
        self._last_confidence = confidence
        
        return {
            "role": "synthesizer",
            "human_probability": human_probability,
            "confidence": confidence,
            "decision": "allow" if human_probability > 0.65 else ("challenge" if human_probability > 0.35 else "block")
        }
    
    def analyze(self, evidence: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ESE-compatible analyze method."""
        result = self.evaluate(evidence, context)
        return {
            "trust_score": result["human_probability"],
            "decision": result["decision"],
            "confidence": result["confidence"]
        }


# Aliases for backward compatibility with existing code
LivenessAnalyst = LivenessRole
AdversarialReviewer = AdversarialRole
MediationAnalyst = MediationRole
RelayAnalyst = RelayRole
TrustSynthesizer = SynthesizerRole