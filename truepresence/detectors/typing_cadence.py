from __future__ import annotations

from truepresence.detectors.human_plausibility import DetectorSignal, _signal
from truepresence.sdk.features import TypingCadenceFeatures


def uniform_typing_cadence(features: TypingCadenceFeatures | None) -> list[DetectorSignal]:
    if features is None or features.inter_key_interval_stddev_ms is None:
        return []

    stddev = features.inter_key_interval_stddev_ms
    cpm = features.characters_per_minute or 0

    if stddev <= 1:
        return [
            _signal(
                "uniform_typing_cadence",
                "high",
                0.9,
                "automation",
                "Inter-key interval variance is effectively zero.",
                category="typing_cadence",
            )
        ]

    if stddev <= 8 and cpm >= 120:
        return [
            _signal(
                "uniform_typing_cadence",
                "medium",
                0.76,
                "automation",
                "Typing cadence is unusually uniform for sustained human input.",
                category="typing_cadence",
            )
        ]

    if stddev <= 15 and cpm >= 260:
        return [
            _signal(
                "uniform_typing_cadence",
                "medium",
                0.66,
                "automation",
                "Fast input with very low cadence variation is automation-consistent.",
                category="typing_cadence",
            )
        ]

    return []
