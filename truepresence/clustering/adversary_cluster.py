def classify_adversary(features: dict) -> str:
    if features["paste_ratio"] > 0.6:
        return "llm_mediated"
    if features["avg_key_interval"] < 100 and features["latency_variance"] < 0.05:
        return "automation_bot"
    if features["response_latency_mean"] > 3 and features["latency_variance"] > 2:
        return "relay_attacker"
    if features["cursor_entropy"] > 0.7:
        return "human_high_entropy"
    return "unknown_hybrid"
