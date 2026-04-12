import random
import time
import uuid
import numpy as np
from typing import Dict, Any, List


class AttackGenerator:
    """
    Attack Generator that creates various types of adversarial attacks.
    
    This class generates different attack patterns to test the system's
    ability to detect sophisticated bot behaviors.
    """
    
    def __init__(self):
        """Initialize Attack Generator."""
        self.attack_types = [
            "bot_like_human",
            "human_like_bot", 
            "replay",
            "noise_injection",
            "timing_attack",
            "behavioral_cloning"
        ]
        
        # Store some human-like patterns for replay attacks
        self.human_patterns = self._generate_human_patterns()
        
    def _generate_human_patterns(self) -> List[Dict]:
        """Generate realistic human behavior patterns for replay attacks."""
        patterns = []
        
        # Generate 5 different human-like patterns
        for i in range(5):
            pattern = {
                "mouse_variance": random.uniform(0.7, 1.2),
                "typing_speed": random.uniform(0.8, 1.5),
                "timing_consistency": random.uniform(0.85, 1.0),
                "event_interval": random.uniform(0.5, 2.0),
                "entropy": random.uniform(3.5, 4.2)
            }
            patterns.append(pattern)
            
        return patterns
        
    def _generate_bot_like_human_attack(self, base_session: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an attack where a bot tries to mimic human behavior."""
        # Start with a copy of the base session
        attack_event = dict(base_session.get("last_event", {}))
        
        # Modify to look bot-like but with some human characteristics
        attack_event["attack_type"] = "bot_like_human"
        attack_event["timestamp"] = time.time()
        
        # Generate bot-like but slightly randomized features
        attack_event["features"] = {
            "mouse_variance": random.uniform(0.2, 0.5),  # Low variance = bot-like
            "typing_speed": random.uniform(1.8, 2.5),     # Too fast = bot-like
            "timing_consistency": random.uniform(0.95, 1.0),  # Too consistent = bot-like
            "event_interval": random.uniform(0.1, 0.3),  # Too regular = bot-like
            "entropy": random.uniform(1.0, 2.5)          # Low entropy = bot-like
        }
        
        # Add some human-like noise to make it subtle
        if random.random() > 0.7:
            attack_event["features"]["mouse_variance"] += random.uniform(0.1, 0.3)
            attack_event["features"]["timing_consistency"] -= random.uniform(0.05, 0.15)
            
        return attack_event
        
    def _generate_human_like_bot_attack(self, base_session: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an attack where a human behaves unusually (false positive test)."""
        attack_event = dict(base_session.get("last_event", {}))
        
        attack_event["attack_type"] = "human_like_bot"
        attack_event["timestamp"] = time.time()
        
        # Generate human-like features with some unusual patterns
        attack_event["features"] = {
            "mouse_variance": random.uniform(0.8, 1.3),  # Human-like variance
            "typing_speed": random.uniform(0.7, 1.2),     # Human-like speed
            "timing_consistency": random.uniform(0.7, 0.9),  # Slightly inconsistent
            "event_interval": random.uniform(0.8, 3.0),  # Variable intervals
            "entropy": random.uniform(3.8, 4.5)          # High entropy
        }
        
        # Add some unusual but still human-like behavior
        if random.random() > 0.6:
            # Maybe the human is tired or distracted
            attack_event["features"]["typing_speed"] *= random.uniform(0.5, 0.8)
            attack_event["features"]["event_interval"] *= random.uniform(1.5, 2.5)
            
        return attack_event
        
    def _generate_replay_attack(self, base_session: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a replay attack using recorded human patterns."""
        attack_event = dict(base_session.get("last_event", {}))
        
        attack_event["attack_type"] = "replay"
        attack_event["timestamp"] = time.time()
        
        # Select a human pattern to replay
        human_pattern = random.choice(self.human_patterns)
        
        # Replay the pattern with slight modifications
        attack_event["features"] = {
            "mouse_variance": human_pattern["mouse_variance"] * random.uniform(0.9, 1.1),
            "typing_speed": human_pattern["typing_speed"] * random.uniform(0.95, 1.05),
            "timing_consistency": human_pattern["timing_consistency"] * random.uniform(0.98, 1.0),
            "event_interval": human_pattern["event_interval"] * random.uniform(0.9, 1.1),
            "entropy": human_pattern["entropy"] * random.uniform(0.95, 1.0)
        }
        
        return attack_event
        
    def _generate_noise_injection_attack(self, base_session: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an attack with injected noise to confuse detection."""
        attack_event = dict(base_session.get("last_event", {}))
        
        attack_event["attack_type"] = "noise_injection"
        attack_event["timestamp"] = time.time()
        
        # Generate features with injected noise
        base_features = base_session.get("typical_features", {
            "mouse_variance": 1.0,
            "typing_speed": 1.0,
            "timing_consistency": 0.9,
            "event_interval": 1.0,
            "entropy": 4.0
        })
        
        attack_event["features"] = {}
        for feature, base_value in base_features.items():
            # Add significant noise
            noise = random.gauss(0, base_value * 0.5)
            noisy_value = max(0.1, base_value + noise)  # Ensure positive values
            attack_event["features"][feature] = noisy_value
            
        return attack_event
        
    def _generate_timing_attack(self, base_session: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an attack that manipulates timing patterns."""
        attack_event = dict(base_session.get("last_event", {}))
        
        attack_event["attack_type"] = "timing_attack"
        attack_event["timestamp"] = time.time()
        
        # Generate timing-based attack features
        attack_event["features"] = {
            "mouse_variance": random.uniform(0.3, 0.6),
            "typing_speed": random.uniform(0.1, 0.5),  # Extremely slow
            "timing_consistency": random.uniform(0.98, 1.0),  # Perfect consistency
            "event_interval": random.uniform(0.05, 0.1),  # Machine-like precision
            "entropy": random.uniform(0.5, 1.5)  # Very low entropy
        }
        
        return attack_event
        
    def _generate_behavioral_cloning_attack(self, base_session: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an attack that clones legitimate user behavior."""
        attack_event = dict(base_session.get("last_event", {}))
        
        attack_event["attack_type"] = "behavioral_cloning"
        attack_event["timestamp"] = time.time()
        
        # Clone the typical user behavior with subtle differences
        typical_features = base_session.get("typical_features", {
            "mouse_variance": 1.1,
            "typing_speed": 0.9,
            "timing_consistency": 0.88,
            "event_interval": 1.2,
            "entropy": 3.9
        })
        
        attack_event["features"] = {}
        for feature, typical_value in typical_features.items():
            # Clone with very small variations
            variation = random.uniform(0.98, 1.02)
            cloned_value = typical_value * variation
            attack_event["features"][feature] = cloned_value
            
        # Add one subtle bot-like characteristic
        bot_feature = random.choice(["mouse_variance", "typing_speed", "timing_consistency"])
        if bot_feature == "mouse_variance":
            attack_event["features"][bot_feature] *= random.uniform(0.4, 0.6)
        elif bot_feature == "typing_speed":
            attack_event["features"][bot_feature] *= random.uniform(1.5, 2.0)
        else:
            attack_event["features"][bot_feature] = min(0.99, attack_event["features"][bot_feature] * random.uniform(1.1, 1.3))
            
        return attack_event
        
    def generate_attack(self, base_session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a random adversarial attack.
        
        Args:
            base_session: Base session to use as reference for attack generation
            
        Returns:
            Dictionary containing the generated attack event
        """
        # Select attack type (weighted towards more sophisticated attacks)
        attack_type = random.choices(
            self.attack_types,
            weights=[0.3, 0.2, 0.2, 0.1, 0.1, 0.1],
            k=1
        )[0]
        
        # Generate the specific attack
        if attack_type == "bot_like_human":
            return self._generate_bot_like_human_attack(base_session)
        elif attack_type == "human_like_bot":
            return self._generate_human_like_bot_attack(base_session)
        elif attack_type == "replay":
            return self._generate_replay_attack(base_session)
        elif attack_type == "noise_injection":
            return self._generate_noise_injection_attack(base_session)
        elif attack_type == "timing_attack":
            return self._generate_timing_attack(base_session)
        else:  # behavioral_cloning
            return self._generate_behavioral_cloning_attack(base_session)


# Legacy functions for backward compatibility
def generate_bot_session(session_id: str):
    """Legacy function for generating bot sessions."""
    events = []
    for _ in range(30):
        events.append({
            "session_id": session_id,
            "event_type": "key_timing",
            "timestamp": time.time(),
            "payload": {"interval_ms": 120},
        })
    return events


def generate_llm_user(session_id: str):
    """Legacy function for generating LLM user sessions."""
    events = []
    for _ in range(20):
        events.append({
            "session_id": session_id,
            "event_type": "clipboard",
            "timestamp": time.time(),
            "payload": {"pasted": True},
        })
        events.append({
            "session_id": session_id,
            "event_type": "key_timing",
            "timestamp": time.time(),
            "payload": {"interval_ms": random.choice([80, 85, 90])},
        })
    return events


def generate_relay(session_id: str):
    """Legacy function for generating relay sessions."""
    events = []
    for _ in range(10):
        events.append({
            "session_id": session_id,
            "event_type": "challenge_response",
            "timestamp": time.time(),
            "payload": {"response_time": random.uniform(2.5, 6.0)},
        })
    return events
