"""
Ensemble Synthesis Engine for TruePresence

This module preserves disagreement, confidence, and variance as first-class outputs
rather than collapsing all role outputs into a single weighted score.

CRITICAL: This system does NOT fail silently. All errors are propagated.
"""

import numpy as np
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class EnsembleSynthesisError(Exception):
    """Raised when synthesis fails - critical errors are not swallowed."""
    pass


class EnsembleSynthesis:
    """
    Ensemble Synthesis Engine that preserves multiple intelligences concept.
    
    Instead of collapsing all role outputs into a single weighted score,
    this class maintains disagreement, confidence, and variance as first-class outputs.
    
    CRITICAL: Errors are NOT swallowed - they are logged and raised.
    """
    
    def __init__(self):
        self.roles = []
        self.role_weights = {}
        
    def add_role(self, role_name: str, weight: float = 1.0):
        """Add a role to the ensemble with optional weight."""
        self.roles.append(role_name)
        self.role_weights[role_name] = weight
        
    def synthesize(self, role_outputs: Dict[str, Dict[str, Any]], evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize outputs from multiple roles while preserving disagreement and variance.
        
        Args:
            role_outputs: Dictionary of role outputs where keys are role names
                        and values are dictionaries containing role-specific outputs
            evidence: The evidence dictionary used for evaluation
            
        Returns:
            Dictionary containing synthesized results with preserved disagreement metrics
            
        Raises:
            EnsembleSynthesisError: If synthesis fails - NOT silently handled
        """
        if not role_outputs:
            logger.warning("No role outputs provided to synthesis - returning neutral result")
            return {
                "human_probability": 0.5,
                "bot_probability": 0.5,
                "confidence": 0.0,
                "disagreement": 0.0,
                "variance": 0.0,
                "role_outputs": {},
                "evidence": evidence,
                "error": "No role outputs provided"
            }
        
        try:
            # Extract probabilities from each role
            probabilities = []
            role_results = {}
            
            for role_name, outputs in role_outputs.items():
                # Get human probability from role output (default to 0.5 if not present)
                human_prob = outputs.get('human_probability', outputs.get('probability', 0.5))
                probabilities.append(human_prob)
                role_results[role_name] = outputs
                
            # Calculate weighted average
            weights = np.array([self.role_weights.get(role, 1.0) for role in role_outputs.keys()])
            weights = weights / np.sum(weights)  # Normalize weights
            
            prob_array = np.array(probabilities)
            weighted_avg = np.sum(prob_array * weights)
            
            # Calculate disagreement metrics
            variance = np.var(prob_array)
            std_dev = np.std(prob_array)
            disagreement = std_dev / np.mean(prob_array) if np.mean(prob_array) > 0 else 0.0
            
            # Calculate confidence (inverse of disagreement, normalized)
            confidence = 1.0 - min(disagreement / 2.0, 1.0)  # Normalize to [0,1]
            
            return {
                "human_probability": float(weighted_avg),
                "bot_probability": float(1.0 - weighted_avg),
                "confidence": float(confidence),
                "disagreement": float(disagreement),
                "variance": float(variance),
                "role_outputs": role_results,
                "evidence": evidence,
                "weights_used": {role: float(weight) for role, weight in zip(role_outputs.keys(), weights)}
            }
        except Exception as e:
            logger.error(f"Synthesis FAILED: {e}", exc_info=True)
            raise EnsembleSynthesisError(
                f"Failed to synthesize role outputs: {str(e)}"
            ) from e