"""
Adaptive Weights Engine for TruePresence

This module provides dynamic weight adjustment for roles based on performance feedback,
replacing hardcoded weights with learned, adaptive ones.
"""

from typing import Dict, List


class AdaptiveWeights:
    """
    Adaptive Weights Engine that learns optimal role weights based on feedback.
    
    This class maintains weights for different roles (liveness, adversarial, mediation)
    and updates them dynamically based on reward signals using gradient-based learning.
    """
    
    def __init__(self, initial_weights: Dict[str, float] = None, learning_rate: float = 0.05):
        """
        Initialize adaptive weights engine.
        
        Args:
            initial_weights: Dictionary of initial role weights
            learning_rate: Learning rate for weight updates
        """
        self.learning_rate = learning_rate
        
        # Set default initial weights if none provided
        if initial_weights is None:
            self.weights = {
                "liveness": 0.4,
                "adversarial": 0.3, 
                "mediation": 0.3
            }
        else:
            self.weights = initial_weights
            
        # Initialize history for tracking performance
        self.history = []
        
    def update(self, role_scores: Dict[str, float], outcome: float):
        """
        Update weights based on role performance and outcome.
        
        Args:
            role_scores: Dictionary of role scores (outputs) for the current evaluation
            outcome: Reward signal (+1 for correct, -1 for incorrect, 0 for neutral)
        """
        if not role_scores:
            return
            
        # Store current state for history
        self.history.append({
            "weights": dict(self.weights),
            "scores": dict(role_scores),
            "outcome": outcome
        })
        
        # Update each role's weight based on performance
        for role, score in role_scores.items():
            if role in self.weights:
                # Calculate error: how far was the role's score from the desired outcome?
                error = outcome - score
                
                # Update weight using gradient-based learning
                # Roles that perform well (score close to outcome) get increased weight
                self.weights[role] += self.learning_rate * error * score
        
        # Normalize weights to sum to 1.0
        self._normalize()
        
    def _normalize(self):
        """Normalize weights so they sum to 1.0."""
        total = sum(self.weights.values())
        if total > 0:
            for role in self.weights:
                self.weights[role] /= total
                
    def get_weights(self) -> Dict[str, float]:
        """Get current weights."""
        return dict(self.weights)
        
    def set_learning_rate(self, learning_rate: float):
        """Set learning rate."""
        self.learning_rate = learning_rate
        
    def reset(self):
        """Reset weights to initial values."""
        default_weights = {
            "liveness": 0.4,
            "adversarial": 0.3,
            "mediation": 0.3
        }
        self.weights = default_weights
        self.history = []
        
    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get recent weight update history."""
        return self.history[-limit:]