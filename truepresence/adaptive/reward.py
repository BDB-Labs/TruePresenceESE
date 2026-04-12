def compute_reward(pre_state: dict, post_state: dict) -> float:
    pre_uncertainty = 1.0 - float(pre_state.get("trust_score", 0.5))
    post_uncertainty = 1.0 - float(post_state.get("trust_score", 0.5))
    reward = pre_uncertainty - post_uncertainty
    return max(0.0, reward)
