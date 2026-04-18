"""
Adversarial Test Harness for TruePresence

This test harness instantiates RuntimeEngine and runs BotSimulator through it,
providing measurable answers to "does TruePresence actually detect bots?"
"""

import random
import time
from typing import Any, Dict, List


class BotSimulator:
    """
    Bot Simulator that generates various types of bot-like behavior.
    
    This class simulates different bot patterns including:
    - Pure bot behavior
    - LLM-generated content patterns
    - Replayed human sessions
    """
    
    def __init__(self):
        self.session_id = f"bot_session_{int(time.time())}"
        
    def generate_bot_events(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate pure bot events."""
        events = []
        for _i in range(count):
            events.append({
                "session_id": self.session_id,
                "event_type": "key_timing",
                "timestamp": time.time(),
                "payload": {
                    "interval_ms": 80 + random.random() * 20  # Very consistent
                },
                "features": {
                    "mouse_variance": 0.3,
                    "typing_speed": 2.0,
                    "timing_consistency": 0.98,
                    "entropy": 1.5
                }
            })
        return events
    
    def generate_llm_events(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate LLM-like user events."""
        events = []
        for i in range(count):
            # LLM users often paste content and have specific timing patterns
            if i % 3 == 0:
                events.append({
                    "session_id": self.session_id,
                    "event_type": "clipboard",
                    "timestamp": time.time(),
                    "payload": {"pasted": True},
                    "features": {
                        "mouse_variance": 0.8,
                        "typing_speed": 0.3,
                        "timing_consistency": 0.6,
                        "entropy": 2.5
                    }
                })
            events.append({
                "session_id": self.session_id,
                "event_type": "key_timing",
                "timestamp": time.time(),
                "payload": {"interval_ms": random.choice([80, 85, 90])},  # Repetitive
                "features": {
                    "mouse_variance": 0.4,
                    "typing_speed": 1.8,
                    "timing_consistency": 0.95,
                    "entropy": 2.0
                }
            })
        return events
    
    def generate_replay_events(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate replayed human session events."""
        events = []
        # Simulate a replayed human pattern
        for _i in range(count):
            events.append({
                "session_id": self.session_id,
                "event_type": "key_timing",
                "timestamp": time.time(),
                "payload": {
                    "interval_ms": 120 + random.random() * 80  # Human-like variance
                },
                "features": {
                    "mouse_variance": 1.0,
                    "typing_speed": 1.0,
                    "timing_consistency": 0.85,
                    "entropy": 3.9
                }
            })
        return events
    
    def stream(self, count: int = 100, bot_type: str = "bot") -> List[Dict[str, Any]]:
        """
        Stream bot events.
        
        Args:
            count: Number of events to generate
            bot_type: Type of bot ('bot', 'llm', 'replay')
            
        Returns:
            List of generated events
        """
        if bot_type == "llm":
            return self.generate_llm_events(count)
        elif bot_type == "replay":
            return self.generate_replay_events(count)
        else:
            return self.generate_bot_events(count)


class RuntimeEngine:
    """
    Runtime Engine for evaluating bot detection.
    
    This class wraps the TruePresence detection system and provides
    a simple interface for testing.
    """
    
    def __init__(self):
        try:
            from truepresence.core.orchestrator_v3 import TruePresenceOrchestratorV3
            self.orchestrator = TruePresenceOrchestratorV3()
        except ImportError:
            print("Warning: Could not import V3 orchestrator, using mock")
            self.orchestrator = None
            
        self.events = []
        
    def evaluate(self, session_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a single event."""
        if self.orchestrator:
            result = self.orchestrator.evaluate(
                session_id=session_id,
                session={"session_id": session_id},
                event=event
            )
            return result
        else:
            # Mock evaluation for testing
            features = event.get("features", {})
            entropy = features.get("entropy", 2.5)
            timing = features.get("timing_consistency", 0.9)
            
            # Simple heuristic
            bot_score = 0.5
            if entropy < 2.0:
                bot_score += 0.3
            if timing > 0.95:
                bot_score += 0.2
                
            return {
                "human_probability": 1.0 - bot_score,
                "bot_probability": bot_score,
                "confidence": 0.7,
                "decision": "block" if bot_score > 0.6 else "allow"
            }
    
    def add_event(self, event: Dict[str, Any]):
        """Add an event to the session."""
        self.events.append(event)


def run_adversarial_test(steps: int = 100, bot_type: str = "bot"):
    """
    Run adversarial test against TruePresence.
    
    Args:
        steps: Number of events to evaluate
        bot_type: Type of bot to test ('bot', 'llm', 'replay')
        
    Returns:
        Test results dictionary
    """
    print(f"Running adversarial test: {steps} events, type: {bot_type}")
    print("=" * 60)
    
    # Initialize engine and simulator
    engine = RuntimeEngine()
    simulator = BotSimulator()
    
    # Generate events
    events = simulator.stream(steps, bot_type)
    
    # Track results
    results = {
        "total_events": 0,
        "bot_detected": 0,
        "human_detected": 0,
        "uncertain": 0,
        "human_probabilities": []
    }
    
    # Evaluate each event
    for event in events:
        result = engine.evaluate(simulator.session_id, event)
        
        results["total_events"] += 1
        results["human_probabilities"].append(result.get("human_probability", 0.5))
        
        if result.get("decision") == "block":
            results["bot_detected"] += 1
        elif result.get("decision") == "allow":
            results["human_detected"] += 1
        else:
            results["uncertain"] += 1
    
    # Calculate statistics
    avg_human_prob = sum(results["human_probabilities"]) / len(results["human_probabilities"])
    detection_rate = results["bot_detected"] / results["total_events"] if results["total_events"] > 0 else 0
    
    print("Results:")
    print(f"  Total Events: {results['total_events']}")
    print(f"  Bot Detected: {results['bot_detected']}")
    print(f"  Human Detected: {results['human_detected']}")
    print(f"  Uncertain: {results['uncertain']}")
    print(f"  Average Human Probability: {avg_human_prob:.3f}")
    print(f"  Detection Rate: {detection_rate:.2%}")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    print("TruePresence Adversarial Test")
    print("=" * 60)
    
    # Test different bot types
    print("\nTest 1: Pure Bot Detection")
    run_adversarial_test(100, "bot")
    
    print("\nTest 2: LLM User Detection")
    run_adversarial_test(100, "llm")
    
    print("\nTest 3: Replay Attack Detection")
    run_adversarial_test(100, "replay")
