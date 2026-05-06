from truepresence.detectors.agentic_control import (
    burst_pause_action_loop,
    implausible_task_efficiency,
    large_instant_input_delta,
    low_exploratory_noise,
    model_thinking_cadence,
    run_agentic_control_detectors,
    structured_retry_pattern,
)
from truepresence.detectors.human_plausibility import (
    DetectorSignal,
    paste_or_instant_input,
    run_human_plausibility_detectors,
    zero_correction_pattern,
)
from truepresence.detectors.reading_time import implausible_read_response_time
from truepresence.detectors.typing_cadence import uniform_typing_cadence

__all__ = [
    "DetectorSignal",
    "burst_pause_action_loop",
    "implausible_task_efficiency",
    "implausible_read_response_time",
    "large_instant_input_delta",
    "low_exploratory_noise",
    "model_thinking_cadence",
    "paste_or_instant_input",
    "run_agentic_control_detectors",
    "run_human_plausibility_detectors",
    "structured_retry_pattern",
    "uniform_typing_cadence",
    "zero_correction_pattern",
]
