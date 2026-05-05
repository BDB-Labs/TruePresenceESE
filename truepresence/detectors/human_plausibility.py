from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from truepresence.sdk.contracts import InteractionFeaturePacket
from truepresence.sdk.features import TypingCadenceFeatures

Severity = Literal["low", "medium", "high"]
ContributionTarget = Literal["human_presence", "automation", "agentic_control"]
SignalCategory = Literal[
    "timing_plausibility",
    "typing_cadence",
    "input_method",
    "pointer_behavior",
    "session_continuity",
    "environment",
    "agentic_behavior",
    "external_provider",
]


class DetectorSignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason_code: str
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    contribution_target: ContributionTarget
    category: SignalCategory
    explanation: str


def _signal(
    reason_code: str,
    severity: Severity,
    confidence: float,
    contribution_target: ContributionTarget,
    explanation: str,
    category: SignalCategory = "timing_plausibility",
) -> DetectorSignal:
    return DetectorSignal(
        reason_code=reason_code,
        severity=severity,
        confidence=max(0.0, min(1.0, confidence)),
        contribution_target=contribution_target,
        category=category,
        explanation=explanation,
    )


def paste_or_instant_input(features: TypingCadenceFeatures | None) -> list[DetectorSignal]:
    if features is None:
        return []

    triggers = 0
    if (features.paste_count or 0) > 0:
        triggers += 1
    if features.focus_to_first_input_ms is not None and features.focus_to_first_input_ms <= 50:
        triggers += 1
    if (
        features.prompt_render_to_first_input_ms is not None
        and features.prompt_render_to_first_input_ms <= 100
    ):
        triggers += 1
    if features.typing_duration_ms is not None and features.typing_duration_ms <= 100:
        triggers += 1
    if (features.characters_per_minute or 0) >= 700:
        triggers += 1

    if triggers == 0:
        return []

    severity: Severity = "medium"
    confidence = 0.62
    if triggers >= 3:
        severity = "high"
        confidence = 0.82
    elif triggers == 1 and (features.paste_count or 0) == 0:
        severity = "low"
        confidence = 0.45

    return [
        _signal(
            "paste_or_instant_input",
            severity,
            confidence,
            "automation",
            "Input timing suggests pasted, injected, or immediately populated content.",
            category="input_method",
        )
    ]


def zero_correction_pattern(features: TypingCadenceFeatures | None) -> list[DetectorSignal]:
    if features is None:
        return []

    no_corrections = features.correction_count == 0 or features.correction_rate == 0
    if not no_corrections:
        return []

    high_speed = (features.characters_per_minute or 0) >= 320
    low_variance = (
        features.inter_key_interval_stddev_ms is not None
        and features.inter_key_interval_stddev_ms <= 15
    )

    if high_speed and low_variance:
        return [
            _signal(
                "zero_correction_pattern",
                "medium",
                0.68,
                "automation",
                "No corrections combined with fast, low-variance input increases automation consistency.",
                category="typing_cadence",
            )
        ]

    return [
        _signal(
            "zero_correction_pattern",
            "low",
            0.35,
            "automation",
            "No corrections were observed; this is only weak evidence by itself.",
            category="typing_cadence",
        )
    ]


def run_human_plausibility_detectors(packet: InteractionFeaturePacket) -> list[DetectorSignal]:
    from truepresence.detectors.reading_time import implausible_read_response_time
    from truepresence.detectors.typing_cadence import uniform_typing_cadence

    signals: list[DetectorSignal] = []
    signals.extend(implausible_read_response_time(packet.challenge))
    signals.extend(uniform_typing_cadence(packet.typing))
    signals.extend(paste_or_instant_input(packet.typing))
    signals.extend(zero_correction_pattern(packet.typing))
    return signals
