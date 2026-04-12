import random
from collections import defaultdict
from typing import Dict


class ChallengeBandit:
    def __init__(self) -> None:
        self.success = defaultdict(float)
        self.trials = defaultdict(float)

    def select(self, context: Dict[str, float]) -> str:
        arms = list(self.success.keys()) or [
            "attention_challenge",
            "interruption_challenge",
            "relay_break_challenge",
            "memory_challenge",
        ]
        scores = {}
        for arm in arms:
            success = self.success[arm] + 1.0
            trials = self.trials[arm] + 1.0
            scores[arm] = success / trials + random.random() * 0.1
        return max(scores, key=scores.get)

    def update(self, arm: str, reward: float) -> None:
        self.trials[arm] += 1.0
        self.success[arm] += max(0.0, reward)
