"""
truepresence.testing.scenarios
================================
Scenario runner: load a fixture, run the full evaluation pipeline, and
compare output against caller-supplied expected ranges.

A *scenario* is a complete, repeatable evaluation run:
  1. Load fixture (includes privacy guard)
  2. Run all detectors against the feature packet
  3. Merge detector output with any pre-computed signals in the fixture
  4. Score via the calibrated probabilistic model
  5. Compare likelihoods and confidence against expected ranges
  6. Return a ``ScenarioResult`` with pass/fail verdict

Expected ranges
---------------
Each range is a ``(min_inclusive, max_inclusive)`` tuple of floats in [0, 1].
Omit a field to skip that assertion.

Example::

    result = run_scenario(
        "scripted_bot_session",
        expected_automation=(0.55, 1.0),
        expected_action={"step_up_auth", "manual_review"},
    )
    assert result.passed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from truepresence.detectors.human_plausibility import (
    DetectorSignal,
    run_human_plausibility_detectors,
)
from truepresence.scoring.model import score_interaction
from truepresence.sdk.contracts import (
    EnforcementMode,
    InteractionFeaturePacket,
    TruePresenceEvaluationResponse,
)

from .fixtures import FIXTURE_DIR, load_fixture

FloatRange = tuple[float, float]  # (min_inclusive, max_inclusive)


@dataclass
class ScenarioResult:
    """Full result from a single scenario run."""

    fixture_name: str
    expected_category: str  # from _meta.expected_category or caller override

    # Raw SDK output
    response: TruePresenceEvaluationResponse

    # Individual assertions — each is True/False/None (None = not checked)
    human_presence_pass: bool | None = None
    automation_pass: bool | None = None
    agentic_control_pass: bool | None = None
    confidence_pass: bool | None = None
    action_pass: bool | None = None

    # All signals produced by detectors + fixture pre-computed signals
    all_signals: list[DetectorSignal] = field(default_factory=list)

    # Human-readable failure reasons
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True iff every checked assertion passed and there are no failures."""
        checks = [
            self.human_presence_pass,
            self.automation_pass,
            self.agentic_control_pass,
            self.confidence_pass,
            self.action_pass,
        ]
        return not self.failures and all(v is not False for v in checks)

    @property
    def likelihoods(self) -> dict[str, float]:
        return {
            "human_presence": self.response.human_presence_likelihood,
            "automation": self.response.automation_likelihood,
            "agentic_control": self.response.agentic_control_likelihood,
        }

    @property
    def confidence(self) -> float:
        return self.response.confidence

    @property
    def recommended_action(self) -> str:
        return self.response.recommended_action


def run_scenario(
    name_or_path: str | Path,
    *,
    fixture_dir: Path | None = None,
    enforcement_mode: EnforcementMode = "observe",
    expected_human_presence: FloatRange | None = None,
    expected_automation: FloatRange | None = None,
    expected_agentic_control: FloatRange | None = None,
    expected_confidence: FloatRange | None = None,
    expected_action: set[str] | None = None,
    expected_category: str | None = None,
) -> ScenarioResult:
    """Run a complete evaluation scenario and return a ``ScenarioResult``.

    Parameters
    ----------
    name_or_path:
        Fixture stem name or path (forwarded to ``load_fixture``).
    fixture_dir:
        Override fixture directory.
    enforcement_mode:
        Passed through to the scoring model.
    expected_human_presence / expected_automation / expected_agentic_control / expected_confidence:
        ``(min, max)`` inclusive range assertions.  ``None`` skips the check.
    expected_action:
        Set of acceptable ``recommended_action`` values.  ``None`` skips.
    expected_category:
        Override the ``_meta.expected_category`` for labelling purposes only.
    """
    fixture = load_fixture(name_or_path, fixture_dir=fixture_dir or FIXTURE_DIR)

    packet: InteractionFeaturePacket = fixture["feature_packet"]
    fixture_signals: list[DetectorSignal] = fixture["signals"]
    meta: dict[str, Any] = fixture["meta"]
    name: str = fixture["name"]

    # Run detectors to produce fresh signals
    detector_signals = run_human_plausibility_detectors(packet)

    # Merge: detector signals first, then fixture pre-computed signals
    # De-duplicate by reason_code so fixtures can override detector output
    seen_codes: set[str] = set()
    merged: list[DetectorSignal] = []
    for sig in detector_signals:
        if sig.reason_code not in seen_codes:
            merged.append(sig)
            seen_codes.add(sig.reason_code)
    for sig in fixture_signals:
        if sig.reason_code not in seen_codes:
            merged.append(sig)
            seen_codes.add(sig.reason_code)

    # Score
    response = score_interaction(
        signals=merged,
        feature_packet=packet,
        enforcement_mode=enforcement_mode,
    )

    effective_category = (
        expected_category
        or meta.get("expected_category", "unknown")
    )

    result = ScenarioResult(
        fixture_name=name,
        expected_category=effective_category,
        response=response,
        all_signals=merged,
    )

    # Evaluate assertions
    result.human_presence_pass = _check_range(
        "human_presence_likelihood",
        response.human_presence_likelihood,
        expected_human_presence,
        result.failures,
    )
    result.automation_pass = _check_range(
        "automation_likelihood",
        response.automation_likelihood,
        expected_automation,
        result.failures,
    )
    result.agentic_control_pass = _check_range(
        "agentic_control_likelihood",
        response.agentic_control_likelihood,
        expected_agentic_control,
        result.failures,
    )
    result.confidence_pass = _check_range(
        "confidence",
        response.confidence,
        expected_confidence,
        result.failures,
    )
    result.action_pass = _check_action(
        response.recommended_action,
        expected_action,
        result.failures,
    )

    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _check_range(
    label: str,
    value: float,
    expected: FloatRange | None,
    failures: list[str],
) -> bool | None:
    if expected is None:
        return None
    lo, hi = expected
    if lo <= value <= hi:
        return True
    failures.append(
        f"{label}={value:.4f} is outside expected range [{lo}, {hi}]"
    )
    return False


def _check_action(
    actual: str,
    expected: set[str] | None,
    failures: list[str],
) -> bool | None:
    if expected is None:
        return None
    if actual in expected:
        return True
    failures.append(
        f"recommended_action='{actual}' not in expected set {sorted(expected)}"
    )
    return False
