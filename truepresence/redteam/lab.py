"""
Adversarial Lab for TruePresence

This module ties together the TruePresenceOrchestrator, AttackGenerator, and RewardEngine
into a complete testing loop that generates attacks, evaluates detection, and feeds back rewards.
"""

import time
from typing import Dict, Any, List


class AdversarialLab:
    """
    Adversarial Lab for testing and improving TruePresence detection capabilities.
    
    This class provides a complete testing environment that generates adversarial attacks,
    evaluates the system's detection capabilities, and feeds back rewards to improve
    the adaptive learning components.
    """
    
    def __init__(self, orchestrator, attack_generator, reward_engine):
        """
        Initialize Adversarial Lab.
        
        Args:
            orchestrator: TruePresenceOrchestrator instance
            attack_generator: AttackGenerator instance
            reward_engine: RewardEngine instance
        """
        self.orchestrator = orchestrator
        self.attack_generator = attack_generator
        self.reward_engine = reward_engine
        
    def run(self, session: Dict[str, Any], steps: int = 10) -> Dict[str, Any]:
        """
        Run adversarial testing loop.
        
        Args:
            session: Base session to use for testing
            steps: Number of attack/evaluation cycles to run
            
        Returns:
            Dictionary containing test results and metrics
        """
        results = {
            "attacks_generated": 0,
            "detections": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "rewards_given": 0,
            "attack_details": []
        }
        
        for step in range(steps):
            # Generate an attack
            attack_event = self.attack_generator.generate_attack(session)
            results["attacks_generated"] += 1
            
            # Evaluate the attack
            evaluation_result = self.orchestrator.evaluate(session, attack_event)
            
            # Determine if this was a successful detection
            final_result = evaluation_result.get("final", {})
            human_prob = final_result.get("human_probability", 0.5)
            confidence = final_result.get("confidence", 0.5)
            
            # Check if attack was detected (bot probability > 0.7 with reasonable confidence)
            is_detected = human_prob < 0.3 and confidence > 0.6
            
            # Get ground truth from attack (whether it was actually a bot attack)
            attack_type = attack_event.get("attack_type", "unknown")
            is_actual_bot = attack_type != "human_like_human"  # Assuming most attacks are bot-like
            
            # Update detection metrics
            if is_actual_bot and is_detected:
                results["detections"] += 1
                reward = 1.0  # Positive reward for correct detection
            elif not is_actual_bot and is_detected:
                results["false_positives"] += 1
                reward = -0.5  # Negative reward for false positive
            elif is_actual_bot and not is_detected:
                results["false_negatives"] += 1
                reward = -1.0  # Strong negative reward for missed detection
            else:
                reward = 0.2  # Small positive reward for correct non-detection
                
            results["rewards_given"] += reward
            
            # Update reward engine
            self.reward_engine.update(reward)
            
            # Store attack details
            results["attack_details"].append({
                "step": step,
                "attack_type": attack_type,
                "human_probability": human_prob,
                "confidence": confidence,
                "detected": is_detected,
                "reward": reward,
                "timestamp": time.time()
            })
            
            # Small delay between steps to simulate real-time
            time.sleep(0.1)
            
        # Calculate overall metrics
        total_attacks = results["attacks_generated"]
        detection_rate = results["detections"] / total_attacks if total_attacks > 0 else 0.0
        false_positive_rate = results["false_positives"] / total_attacks if total_attacks > 0 else 0.0
        false_negative_rate = results["false_negatives"] / total_attacks if total_attacks > 0 else 0.0
        
        results.update({
            "detection_rate": detection_rate,
            "false_positive_rate": false_positive_rate,
            "false_negative_rate": false_negative_rate,
            "average_reward": results["rewards_given"] / total_attacks if total_attacks > 0 else 0.0
        })
        
        return results
        
    def continuous_testing(self, session: Dict[str, Any], duration_minutes: float = 5.0):
        """
        Run continuous testing for a specified duration.
        
        Args:
            session: Base session to use for testing
            duration_minutes: Duration to run testing in minutes
            
        Returns:
            Dictionary containing test results and metrics
        """
        end_time = time.time() + (duration_minutes * 60)
        step_count = 0
        
        while time.time() < end_time:
            # Run a batch of tests
            batch_results = self.run(session, steps=5)
            step_count += 5
            
            # Print progress
            print(f"Completed {step_count} steps - Detection Rate: {batch_results['detection_rate']:.2f}")
            
            # Small delay between batches
            time.sleep(1)
            
        return batch_results