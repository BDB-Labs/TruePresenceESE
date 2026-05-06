# TruePresence Agentic Detection

## Purpose

TruePresence separates generic automation from agentic control.

Generic automation describes scripted or mechanical browser behavior, such as uniform typing cadence, instant input population, or automation environment hints. Agentic control describes interaction patterns that are more consistent with browser agents or AI-assisted task execution, such as plan/act bursts, highly direct task paths, structured retries, and large generated input deltas.

These signals are probabilistic. They do not prove an actor is human, automated, or agentic.

## Privacy Boundaries

Agentic detection uses aggregate behavioral summaries only. It must not collect or transmit:

- raw typed content;
- prompts, messages, comments, answers, or transcripts;
- raw key values;
- raw pointer trails;
- full DOM paths or page text.

The browser SDK computes local summaries such as input length deltas, action burst counts, directness ratios, retry counts, and submit timing. The backend schema allowlist accepts only those derived fields.

## Feature Summary

`AgenticBehaviorFeatures` includes:

- `action_burst_count`;
- `mean_burst_interval_ms`;
- `burst_interval_stddev_ms`;
- `idle_to_action_latency_ms`;
- `exploratory_action_count`;
- `route_directness_score`;
- `large_instant_delta_count`;
- `submit_after_instant_input_ms`;
- `structured_retry_count`;
- `validation_repair_count`.

These fields describe how the interaction unfolded, not what the user or agent typed.

## Detector Families

The first-pass detector families are:

- `model_thinking_cadence`: regular pause intervals between action bursts.
- `burst_pause_action_loop`: repeated compact action bursts separated by pauses.
- `large_instant_input_delta`: large input-length changes in one event, without content capture.
- `low_exploratory_noise`: unusually direct interaction with little pointer or scroll exploration.
- `structured_retry_pattern`: repeated retry or validation-repair aggregates.
- `implausible_task_efficiency`: highly direct route with very low idle-to-action and submit latency.

Each detector emits `DetectorSignal` with `contribution_target = "agentic_control"` and `category = "agentic_behavior"`.

## Scoring Relationship

Agentic-control signals raise `agentic_control_likelihood`. Generic automation signals remain in the automation channel and do not automatically raise agentic-control likelihood.

This keeps a scripted bot distinct from an AI/browser-agent pattern. A session can have high automation likelihood and low agentic-control likelihood when only generic automation evidence is present.

## Limitations

This is deterministic first-pass calibration, not ML. The detector thresholds are intentionally conservative and should be tuned with privacy-safe fixtures and production aggregate telemetry. Agentic patterns can overlap with accessibility tools, power-user workflows, test automation, or unusual but legitimate user behavior, so recommended actions must continue to use confidence gating and avoid certainty claims.
