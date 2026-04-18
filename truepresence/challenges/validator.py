import time
import uuid
from typing import Any, Dict


class ChallengeValidator:
    """
    Implements Phase 2: Closing the Challenge Loop.
    Validates not just the answer, but the 'How' (TTR).
    """
    def __init__(self):
        self.active_challenges = {}

    def issue_challenge(self, session_id: str, prompt: str) -> Dict[str, Any]:
        challenge_id = str(uuid.uuid4())
        challenge = {
            "id": challenge_id,
            "prompt": prompt,
            "created_at": time.time(),
        }
        self.active_challenges[session_id] = challenge
        return challenge

    def validate_response(self, session_id: str, response_text: str) -> Dict[str, Any]:
        challenge = self.active_challenges.get(session_id)
        if not challenge:
            return {"valid": False, "reason": "no_active_challenge"}

        ttr = time.time() - challenge["created_at"] # Time to Respond
        
        # Logic: If response is too fast (< 1s) or too slow (> 30s), it's suspicious
        is_timing_valid = 1.0 < ttr < 30.0
        
        # In a real system, we would check the 'response_text' against the prompt
        # For now, we validate the Presence of a response + Timing
        is_correct = len(response_text.strip()) > 0
        
        del self.active_challenges[session_id]
        
        return {
            "valid": is_correct and is_timing_valid,
            "ttr": ttr,
            "reason": "timing_anomaly" if not is_timing_valid else "correct"
        }
