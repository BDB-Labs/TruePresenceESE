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
from truepresence.detectors.telegram_community import (
    conversation_cadence_anomaly,
    coordinated_join_pattern,
    instant_post_after_join,
    join_to_action_plausibility,
    link_drop_after_join,
    message_burst_pattern,
    repeat_group_hopping_pattern,
    run_telegram_community_detectors,
    synchronized_posting_cluster,
)
from truepresence.detectors.typing_cadence import uniform_typing_cadence

__all__ = [
    "DetectorSignal",
    "burst_pause_action_loop",
    "conversation_cadence_anomaly",
    "coordinated_join_pattern",
    "implausible_task_efficiency",
    "implausible_read_response_time",
    "instant_post_after_join",
    "join_to_action_plausibility",
    "large_instant_input_delta",
    "link_drop_after_join",
    "low_exploratory_noise",
    "message_burst_pattern",
    "model_thinking_cadence",
    "paste_or_instant_input",
    "repeat_group_hopping_pattern",
    "run_agentic_control_detectors",
    "run_human_plausibility_detectors",
    "run_telegram_community_detectors",
    "structured_retry_pattern",
    "synchronized_posting_cluster",
    "uniform_typing_cadence",
    "zero_correction_pattern",
]
