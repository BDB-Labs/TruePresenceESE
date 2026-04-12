from typing import Dict, Any
from challenges.engine import create_challenge, Challenge


def simple_attention_challenge() -> Challenge:
    return create_challenge(
        "attention",
        {
            "prompt": "What color is the square on your screen right now?",
            "type": "visual_binding",
        },
        ttl=8.0,
    )


def cognitive_interruption_challenge() -> Challenge:
    return create_challenge(
        "interruption",
        {
            "task": "Count backwards from 57 by 3s and then describe what you see.",
            "type": "dual_task",
        },
        ttl=12.0,
    )


def relay_breaking_challenge() -> Challenge:
    return create_challenge(
        "relay_break",
        {
            "step1": "Say the word 'orange' out loud.",
            "step2": "Immediately type the third letter of what you just said.",
            "step3": "Now describe your physical environment in one sentence.",
        },
        ttl=10.0,
    )


def generate_challenge(session_state: Dict[str, Any]) -> Challenge:
    risk_hint = float(session_state.get("risk_hint", 0.5))
    if risk_hint < 0.4:
        return simple_attention_challenge()
    if risk_hint < 0.7:
        return cognitive_interruption_challenge()
    return relay_breaking_challenge()
