"""
Unified Role Interface for TruePresence

This module provides a common base class and interface for all roles,
ensuring consistent method signatures and enabling dynamic role loading.

CRITICAL: This system does NOT fail silently. All errors are propagated
with full context for debugging and monitoring.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

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
    """
    Adversarial review role - hunts for 'too perfect' signals and specific threats.
    
    Detects:
    - Mirrors/Userbots (spam amplification)
    - Crypto Miners (resource abuse)
    - DMCA Violations (copyright infringement)
    - Torrent Aggregators (pirate content)
    - VNC/Virtual Desktops (remote abuse)
    - Illegal Content (general)
    """
    
    def __init__(self):
        super().__init__()
        self._role_name = "adversarial"
    
    def evaluate(self, evidence: Dict[str, Any], session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate for adversarial/bot signals and specific threat categories."""
        try:
            signals = evidence.get("signals", {})
            findings = []
            threat_categories = []
            
            # ===== STANDARD BOT DETECTION =====
            
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
            
            # ===== SPECIFIC THREAT DETECTION =====
            
            # 1. Mirror/Userbot Detection
            # - High message velocity + identical messages across groups
            # - Same content posted to multiple groups in short time
            message_velocity = signals.get("message_velocity", 0)
            content_similarity = signals.get("content_similarity", 0)
            
            if message_velocity > 50 and content_similarity > 0.9:
                findings.append("mirrored_content_detected")
                threat_categories.append("mirrors_userbots")
            
            # 2. Crypto Miner Detection
            # - High CPU usage patterns, computational resource abuse
            # - Scripts running in background, unusual network activity
            cpu_usage = signals.get("cpu_usage", 0)
            network_entropy = signals.get("network_entropy", 0.5)
            
            if cpu_usage > 80 and network_entropy < 0.3:
                findings.append("high_resource_usage_pattern")
                threat_categories.append("crypto_miners")
            
            # 3. DMCA Protected Content Detection
            # - Sharing known copyrighted content
            # - Links to known piracy sites
            copyright_signals = signals.get("copyright_indicators", [])
            if copyright_signals:
                findings.append("copyright_content_detected")
                threat_categories.append("dmca_violations")
            
            # 4. Torrent Aggregator Detection
            # - Magnet links, torrent file transfers
            # - High bandwidth with specific peer-to-peer patterns
            torrent_indicators = signals.get("torrent_indicators", 0)
            p2p_pattern = signals.get("p2p_pattern", 0)
            
            if torrent_indicators > 0.5 or p2p_pattern > 0.7:
                findings.append("torrent_activity_detected")
                threat_categories.append("torrent_aggregators")
            
            # 5. VNC/Virtual Desktop Detection
            # - Remote desktop activity, VNC ports
            # - Automated screen capture patterns
            vnc_indicators = signals.get("vnc_indicators", 0)
            remote_access_pattern = signals.get("remote_access_pattern", 0)
            
            if vnc_indicators > 0.3 or remote_access_pattern > 0.6:
                findings.append("remote_access_detected")
                threat_categories.append("vnc_virtual_desktops")
            
            # 6. Illegal Content Detection
            # - Match against known illegal content patterns
            # - Drugs, weapons, fraud indicators
            illegal_indicators = signals.get("illegal_indicators", [])
            fraud_pattern = signals.get("fraud_pattern", 0)
            
            if illegal_indicators or fraud_pattern > 0.8:
                findings.append("illegal_content_detected")
                threat_categories.append("illegal_content")
            
            # ===== SEVERITY CALCULATION =====
            
            # Base severity from findings
            base_severity = len(findings) * 0.15
            
            # Boost for confirmed threat categories
            threat_boost = len(threat_categories) * 0.2
            
            # Combine (cap at 1.0)
            severity = min(1.0, base_severity + threat_boost)
            
            # For confirmed illegal categories, max severity
            if "illegal_content" in threat_categories:
                severity = 1.0
            
            bot_probability = severity
            human_probability = 1.0 - bot_probability
            
            # Confidence increases with more findings and confirmed threats
            confidence = min(1.0, 0.5 + (severity * 0.5))
            
            self._last_confidence = confidence
            self._last_error = None
            
            return {
                "role": self._role_name,
                "human_probability": human_probability,
                "bot_probability": bot_probability,
                "confidence": confidence,
                "findings": findings,
                "threat_categories": threat_categories,
                "severity": severity,
                "block_reason": self._get_block_reason(threat_categories, findings),
                "impact": "negative" if findings else "neutral"
            }
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"AdversarialRole.evaluate failed: {e}", exc_info=True)
            raise
    
    def _get_block_reason(self, threat_categories: list, findings: list) -> str:
        """Get human-readable block reason for logging/display."""
        if "illegal_content" in threat_categories:
            return "Illegal content detected - permanent ban"
        elif "crypto_miners" in threat_categories:
            return "Crypto mining detected - resource abuse"
        elif "dmca_violations" in threat_categories:
            return "Copyright violation detected - DMCA"
        elif "torrent_aggregators" in threat_categories:
            return "Torrent activity detected - piracy"
        elif "vnc_virtual_desktops" in threat_categories:
            return "Unauthorized remote access detected"
        elif "mirrors_userbots" in threat_categories:
            return "Spam mirror/userbot detected"
        elif findings:
            return "Bot-like behavior detected"
        else:
            return "Unknown threat"
    
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


# Aliases for backward compatibility with existing code
LivenessAnalyst = LivenessRole
AdversarialReviewer = AdversarialRole
MediationAnalyst = MediationRole
RelayAnalyst = RelayRole
TrustSynthesizer = SynthesizerRole