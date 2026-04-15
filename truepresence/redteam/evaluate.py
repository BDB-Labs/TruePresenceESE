from typing import Any, Dict, List

from truepresence.adaptive.reward import RewardEngine
from truepresence.ese_stream import evaluate_incremental


class RedTeamEvaluator:
    """
    Red Team Evaluator that integrates RewardEngine for self-evaluation.
    
    This class evaluates attacks and feeds reward signals back to the
    adaptive weighting system for continuous improvement.
    """
    
    def __init__(self):
        """Initialize Red Team Evaluator with reward engine."""
        self.reward_engine = RewardEngine()
        self.evaluation_history = []
        
    def run_attack(self, test_name: str, events: List[Dict], ground_truth: bool = None) -> Dict:
        """
        Run an attack evaluation and compute reward.
        
        Args:
            test_name: Name of the test/attack
            events: List of events to evaluate
            ground_truth: Whether this was actually a bot attack (if known)
            
        Returns:
            Dictionary containing evaluation results and reward
        """
        if not events:
            return {"test": test_name, "final_score": None, "decision": None, "trace": [], "reward": 0.0}
            
        session_id = events[0]["session_id"]
        results = []
        
        for e in events:
            res = evaluate_incremental(session_id, e)
            results.append(res)
            
        final = results[-1] if results else None
        
        # Extract evaluation results
        human_prob = final.get("human_probability", 0.5) if final else 0.5
        decision = final.get("decision", "unknown") if final else "unknown"
        
        # Compute reward if ground truth is available
        reward = 0.0
        if ground_truth is not None:
            predicted_bot = decision in ["block", "challenge"]
            
            # Compute reward using reward engine
            reward = self.reward_engine.compute_detection_reward(
                predicted_bot=predicted_bot,
                actual_bot=ground_truth,
                confidence=final.get("confidence", 0.5) if final else 0.5
            )
            
            # Update reward engine
            self.reward_engine.update(reward, {
                "test_name": test_name,
                "decision": decision,
                "human_probability": human_prob
            })
            
        # Store evaluation
        self.evaluation_history.append({
            "test_name": test_name,
            "human_probability": human_prob,
            "decision": decision,
            "reward": reward,
            "ground_truth": ground_truth
        })
        
        return {
            "test": test_name,
            "final_score": final.get("live_score") if final else None,
            "decision": decision,
            "human_probability": human_prob,
            "trace": results,
            "reward": reward,
            "ground_truth": ground_truth
        }
        
    def run_batch(self, tests: List[Dict[str, Any]]) -> Dict:
        """
        Run multiple attack evaluations.
        
        Args:
            tests: List of test dictionaries with 'name', 'events', and optional 'ground_truth'
            
        Returns:
            Aggregated results across all tests
        """
        results = []
        
        for test in tests:
            result = self.run_attack(
                test_name=test.get("name", "unnamed"),
                events=test.get("events", []),
                ground_truth=test.get("ground_truth")
            )
            results.append(result)
            
        # Calculate aggregated metrics
        total_tests = len(results)
        detected = sum(1 for r in results if r.get("decision") in ["block", "challenge"])
        avg_reward = sum(r.get("reward", 0) for r in results) / total_tests if total_tests > 0 else 0.0
        
        return {
            "total_tests": total_tests,
            "detected": detected,
            "detection_rate": detected / total_tests if total_tests > 0 else 0.0,
            "average_reward": avg_reward,
            "results": results,
            "performance": self.reward_engine.get_performance()
        }
        
    def get_performance(self) -> Dict:
        """Get current performance metrics."""
        return self.reward_engine.get_performance()


# Legacy function for backward compatibility
def run_attack(test_name: str, events: List[Dict]) -> Dict:
    """Legacy function for running attacks."""
    if not events:
        return {"test": test_name, "final_score": None, "decision": None, "trace": []}
    session_id = events[0]["session_id"]
    results = []
    for e in events:
        res = evaluate_incremental(session_id, e)
        results.append(res)
    final = results[-1] if results else None
    return {
        "test": test_name,
        "final_score": final.get("live_score") if final else None,
        "decision": final.get("decision") if final else None,
        "trace": results,
    }
