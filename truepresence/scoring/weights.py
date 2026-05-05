from __future__ import annotations

# Per-severity base strengths used as multipliers before confidence/weight
SEVERITY_WEIGHTS: dict[str, float] = {
    "low": 0.25,
    "medium": 0.55,
    "high": 0.85,
}

# Per-category weights: how much each category contributes to the top-level
# probabilistic combination. Must all be in (0, 1]. Sum need not equal 1 —
# the product-of-complements formula handles overlap naturally.
CATEGORY_WEIGHTS: dict[str, float] = {
    "timing_plausibility": 0.70,
    "typing_cadence": 0.65,
    "input_method": 0.60,
    "pointer_behavior": 0.55,
    "session_continuity": 0.50,
    "environment": 0.45,
    "agentic_behavior": 0.80,
    "external_provider": 0.50,
}

# Legacy bases retained for human-support feature scoring (unchanged)
BASE_HUMAN_PRESENCE = 0.58
BASE_AUTOMATION = 0.24
BASE_AGENTIC_CONTROL = 0.18
