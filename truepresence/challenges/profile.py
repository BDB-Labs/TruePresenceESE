"""
Challenge Profile Module for TruePresence

This module provides optional challenge memory profiles for gatekeeper deployments.
Questions only trigger when risk is above threshold - never for normal users.
This is NOT an identity system - it's episodic verification reinforcement only.
"""

import yaml
import os
from typing import List, Dict, Any, Optional

from truepresence.challenges.deterministic import stable_challenge_id, stable_index


class ChallengeProfile:
    """
    Challenge Profile for episodic verification.
    
    This class manages challenge questions that are triggered only when
    risk exceeds a threshold. It is NOT an identity system - it only provides
    episodic verification reinforcement.
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize Challenge Profile.
        
        Args:
            config_path: Path to config file (defaults to config.yaml in project root)
        """
        self.enabled = False
        self.risk_threshold = 0.7
        self.questions = []
        self._load_config(config_path)
        
    def _load_config(self, config_path: str = None):
        """Load challenge profile configuration."""
        if config_path is None:
            # Default to project root config
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config.yaml"
            )
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    
                challenge_profile = config.get("challenge_profile", {})
                self.enabled = challenge_profile.get("enabled", False)
                self.risk_threshold = challenge_profile.get("risk_threshold", 0.7)
                self.questions = challenge_profile.get("questions", [])
            except Exception as e:
                print(f"Warning: Could not load challenge profile config: {e}")
        else:
            # Use default questions if no config
            self.questions = [
                "Type the third letter of the word 'hello'",
                "Count backward from 10 to 1",
                "Type your favorite color",
                "Spell the word 'presence' backwards",
                "Type the current day of the week"
            ]
    
    def should_challenge(self, risk_score: float) -> bool:
        """
        Determine if a challenge should be issued.
        
        Args:
            risk_score: Current risk score (0-1)
            
        Returns:
            True if challenge should be issued
        """
        if not self.enabled:
            return False
            
        return risk_score >= self.risk_threshold
    
    def get_challenge(self, session_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get a challenge question.
        
        Args:
            session_id: Optional session ID for deterministic selection
            
        Returns:
            Challenge dictionary with id and prompt, or None if not enabled
        """
        if not self.enabled or not self.questions:
            return None
            
        # Select question based on session_id for consistency
        if session_id:
            index = stable_index(session_id, len(self.questions))
        else:
            import random
            index = random.randint(0, len(self.questions) - 1)
            
        return {
            "id": stable_challenge_id(session_id or "anonymous", index),
            "prompt": self.questions[index],
            "type": "memory_verification"
        }
    
    def verify_response(self, challenge_id: str, response: str, expected: str = None) -> Dict[str, Any]:
        """
        Verify a challenge response.
        
        Args:
            challenge_id: ID of the challenge
            response: User's response
            expected: Expected answer (optional - for open-ended questions)
            
        Returns:
            Verification result
        """
        if not self.enabled:
            return {"verified": False, "reason": "challenge_profile_disabled"}
            
        # Simple verification - could be extended with more sophisticated checks
        response_lower = response.strip().lower()
        
        if expected:
            expected_lower = expected.lower()
            correct = response_lower == expected_lower
            
            return {
                "verified": correct,
                "challenge_id": challenge_id,
                "reason": "correct" if correct else "incorrect"
            }
        else:
            # For open-ended questions, just note the response
            return {
                "verified": True,
                "challenge_id": challenge_id,
                "response_received": True,
                "reason": "response_recorded"
            }
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return {
            "enabled": self.enabled,
            "risk_threshold": self.risk_threshold,
            "question_count": len(self.questions)
        }
    
    def enable(self):
        """Enable challenge profiles."""
        self.enabled = True
        
    def disable(self):
        """Disable challenge profiles."""
        self.enabled = False
    
    def set_threshold(self, threshold: float):
        """Set risk threshold for challenges."""
        self.risk_threshold = max(0.0, min(1.0, threshold))
        
    def add_question(self, question: str):
        """Add a challenge question."""
        if question not in self.questions:
            self.questions.append(question)
            
    def remove_question(self, question: str):
        """Remove a challenge question."""
        if question in self.questions:
            self.questions.remove(question)
            
    def get_questions(self) -> List[str]:
        """Get all challenge questions."""
        return list(self.questions)
