"""
Multi-Agent Council for TruePresence

This module replaces simple weighted voting with structured disagreement,
computing variance across opinions as a disagreement signal and deriving
confidence scores inversely proportional to variance.
"""

import numpy as np
from typing import Dict, Any, List


class AgentCouncil:
    """
    Multi-Agent Council that manages structured debate among agents.
    
    This class runs all agents, computes variance across opinions as a disagreement signal,
    and derives confidence scores inversely proportional to that variance.
    """
    
    def __init__(self):
        self.agents = []
        self.agent_names = []
        
    def add_agent(self, agent_name: str, agent):
        """Add an agent to the council."""
        self.agents.append(agent)
        self.agent_names.append(agent_name)
        
    def evaluate(self, evidence: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate evidence using all agents and compute disagreement metrics.
        
        Args:
            evidence: Evidence dictionary for evaluation
            session: Current session dictionary
            
        Returns:
            Dictionary containing agent opinions, disagreement metrics, and confidence scores
        """
        if not self.agents:
            return {
                "agent_opinions": {},
                "disagreement": 0.0,
                "variance": 0.0,
                "confidence": 0.0,
                "consensus": 0.5
            }
        
        # Collect opinions from all agents
        opinions = []
        agent_results = {}
        
        for agent_name, agent in zip(self.agent_names, self.agents):
            try:
                result = agent.evaluate(evidence, session)
                # Extract probability or score from agent result
                probability = result.get('human_probability', 
                                      result.get('probability', 
                                              result.get('score', 0.5)))
                opinions.append(probability)
                agent_results[agent_name] = result
            except Exception as e:
                # If agent fails, use neutral opinion
                opinions.append(0.5)
                agent_results[agent_name] = {"error": str(e), "human_probability": 0.5}
        
        # Calculate statistics
        opinions_array = np.array(opinions)
        mean_opinion = np.mean(opinions_array)
        variance = np.var(opinions_array)
        std_dev = np.std(opinions_array)
        
        # Calculate disagreement (coefficient of variation)
        disagreement = std_dev / mean_opinion if mean_opinion > 0 else 0.0
        
        # Calculate confidence (inverse of disagreement, normalized to [0,1])
        confidence = 1.0 - np.tanh(disagreement * 2.0)  # Using tanh for normalization
        
        return {
            "agent_opinions": agent_results,
            "mean_opinion": float(mean_opinion),
            "disagreement": float(disagreement),
            "variance": float(variance),
            "confidence": float(confidence),
            "consensus": float(mean_opinion),
            "opinion_distribution": [float(op) for op in opinions]
        }