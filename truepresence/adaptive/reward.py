"""
Reward Engine for TruePresence

This module provides a reward engine that updates weights based on detection feedback,
enabling the system to learn from its performance and improve over time.
"""

from typing import Any, Dict, List

import numpy as np


class RewardEngine:
    """
    Reward Engine that learns from detection outcomes and updates the system.
    
    This class provides methods to compute rewards, update adaptive weights,
    and track performance metrics.
    """
    
    def __init__(self, learning_rate: float = 0.05, discount_factor: float = 0.95):
        """
        Initialize Reward Engine.
        
        Args:
            learning_rate: Learning rate for weight updates
            discount_factor: Discount factor for future rewards
        """
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        
        # Performance tracking
        self.reward_history = []
        self.total_correct = 0
        self.total_incorrect = 0
        self.performance_metrics = {
            "detection_rate": 0.0,
            "false_positive_rate": 0.0,
            "false_negative_rate": 0.0
        }
        
    def compute_reward(self, pre_state: Dict[str, Any], post_state: Dict[str, Any]) -> float:
        """
        Compute reward based on state changes.
        
        Args:
            pre_state: State before evaluation
            post_state: State after evaluation
            
        Returns:
            Reward value (positive for improvement, negative for degradation)
        """
        pre_uncertainty = 1.0 - float(pre_state.get("trust_score", 0.5))
        post_uncertainty = 1.0 - float(post_state.get("trust_score", 0.5))
        reward = pre_uncertainty - post_uncertainty
        return max(0.0, reward)
        
    def compute_detection_reward(
        self,
        predicted_bot: bool,
        actual_bot: bool,
        confidence: float
    ) -> float:
        """
        Compute reward for a detection decision.
        
        Args:
            predicted_bot: Whether the system predicted bot
            actual_bot: Whether it was actually a bot (ground truth)
            confidence: Confidence of the prediction
            
        Returns:
            Reward value
        """
        if predicted_bot and actual_bot:
            # Correct detection - positive reward
            reward = 1.0 * confidence
            self.total_correct += 1
        elif not predicted_bot and not actual_bot:
            # Correct non-detection - small positive reward
            reward = 0.2
            self.total_correct += 1
        elif predicted_bot and not actual_bot:
            # False positive - negative reward
            reward = -0.5 * confidence
            self.total_incorrect += 1
        else:  # not predicted_bot and actual_bot
            # False negative - strong negative reward
            reward = -1.0
            self.total_incorrect += 1
            
        # Update metrics
        self._update_performance_metrics()
        
        return reward
        
    def _update_performance_metrics(self):
        """Update performance tracking metrics."""
        total = self.total_correct + self.total_incorrect
        if total > 0:
            self.performance_metrics["detection_rate"] = self.total_correct / total
            
        # Calculate additional metrics based on recent rewards
        recent_rewards = [r["reward"] for r in self.reward_history[-20:]]
        if recent_rewards:
            avg_positive = np.mean([r for r in recent_rewards if r > 0])
            avg_negative = np.mean([r for r in recent_rewards if r < 0])
            
            self.performance_metrics["avg_positive_reward"] = avg_positive
            self.performance_metrics["avg_negative_reward"] = avg_negative
            
    def update(self, reward: float, metadata: Dict[str, Any] = None):
        """
        Update the reward engine with a new reward value.
        
        Args:
            reward: The reward value from evaluation
            metadata: Optional metadata about the evaluation
        """
        record = {
            "reward": reward,
            "timestamp": __import__("time").time()
        }
        
        if metadata:
            record["metadata"] = metadata
            
        self.reward_history.append(record)
        
        # Keep history manageable
        if len(self.reward_history) > 1000:
            self.reward_history = self.reward_history[-500:]
            
    def get_recent_rewards(self, n: int = 10) -> List[float]:
        """Get the n most recent rewards."""
        return [r["reward"] for r in self.reward_history[-n:]]
        
    def get_cumulative_reward(self) -> float:
        """Get the cumulative sum of all rewards."""
        return sum(r["reward"] for r in self.reward_history)
        
    def get_performance(self) -> Dict[str, float]:
        """Get current performance metrics."""
        return dict(self.performance_metrics)
        
    def reset(self):
        """Reset the reward engine."""
        self.reward_history = []
        self.total_correct = 0
        self.total_incorrect = 0
        self.performance_metrics = {
            "detection_rate": 0.0,
            "false_positive_rate": 0.0,
            "false_negative_rate": 0.0
        }