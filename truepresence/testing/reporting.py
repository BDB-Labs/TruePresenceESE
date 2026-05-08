"""
truepresence.testing.reporting
================================
Format individual ``ScenarioResult`` objects and summarise suite runs.

``build_report(result)``
    Return a structured dict suitable for logging, assertion messages, or
    serialisation to JSON.

``summarise_suite(results)``
    Return a dict with pass/fail counts, per-fixture verdicts, and a
    plain-text summary string.
"""

from __future__ import annotations

from typing import Any

from .scenarios import ScenarioResult


def build_report(result: ScenarioResult) -> dict[str, Any]:
    """Return a structured evaluation report for a single scenario run.

    The returned dict contains:
    - ``fixture_name``        – stem name of the fixture
    - ``expected_class``      – labelled class from fixture _meta or override
    - ``likelihoods``         – ``{human_presence, automation, agentic_control}``
    - ``confidence``          – model confidence value
    - ``recommended_action``  – SDK recommended action string
    - ``expected``            – expected ranges/actions used for pass/fail
    - ``reason_codes``        – list of reason codes from fired signals
    - ``signal_count``        – total number of signals evaluated
    - ``assertions``          – per-field pass/fail/skipped status
    - ``failures``            – list of human-readable failure descriptions
    - ``passed``              – overall boolean verdict
    """
    assertions: dict[str, str] = {
        "human_presence": _verdict(result.human_presence_pass),
        "automation": _verdict(result.automation_pass),
        "agentic_control": _verdict(result.agentic_control_pass),
        "confidence": _verdict(result.confidence_pass),
        "recommended_action": _verdict(result.action_pass),
    }

    return {
        "fixture_name": result.fixture_name,
        "expected_class": result.expected_category,
        "expected_category": result.expected_category,
        "likelihoods": result.likelihoods,
        "confidence": result.confidence,
        "recommended_action": result.recommended_action,
        "expected": {
            "likelihoods": {
                "human_presence": _range_value(
                    result.expected_ranges.get("human_presence_likelihood")
                ),
                "automation": _range_value(
                    result.expected_ranges.get("automation_likelihood")
                ),
                "agentic_control": _range_value(
                    result.expected_ranges.get("agentic_control_likelihood")
                ),
            },
            "confidence": _range_value(result.expected_ranges.get("confidence")),
            "recommended_action": sorted(result.expected_actions),
        },
        "reason_codes": sorted(
            {sig.reason_code for sig in result.all_signals}
        ),
        "signal_count": len(result.all_signals),
        "assertions": assertions,
        "failures": list(result.failures),
        "passed": result.passed,
    }


def summarise_suite(results: list[ScenarioResult]) -> dict[str, Any]:
    """Summarise a list of scenario results.

    Returns a dict containing:
    - ``total``    – number of scenarios run
    - ``passed``   – count of passing scenarios
    - ``failed``   – count of failing scenarios
    - ``false_positives`` – benign fixtures with escalating actions
    - ``false_negatives`` – risk fixtures with allow/observe actions
    - ``fixtures`` – list of per-fixture ``build_report`` dicts
    - ``summary``  – plain-text summary string
    """
    reports = [build_report(r) for r in results]
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    false_positives = sum(1 for r in results if _is_false_positive(r))
    false_negatives = sum(1 for r in results if _is_false_negative(r))

    lines: list[str] = [
        f"TruePresence Evaluation Suite: {passed}/{len(results)} passed",
        f"False positives: {false_positives} | False negatives: {false_negatives}",
        "",
    ]
    for report in reports:
        verdict = "PASS" if report["passed"] else "FAIL"
        likelihoods = report["likelihoods"]
        lines.append(
            f"  [{verdict}] {report['fixture_name']}"
            f" | expected={report['expected_class']}"
            f" | human={likelihoods['human_presence']:.3f}"
            f" | automation={likelihoods['automation']:.3f}"
            f" | agentic={likelihoods['agentic_control']:.3f}"
            f" | action={report['recommended_action']}"
            f" | confidence={report['confidence']:.3f}"
        )
        for failure in report["failures"]:
            lines.append(f"         ✗ {failure}")

    summary = "\n".join(lines)

    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "fixtures": reports,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _verdict(value: bool | None) -> str:
    if value is None:
        return "skipped"
    return "pass" if value else "fail"


def _range_value(value: tuple[float, float] | None) -> list[float] | None:
    if value is None:
        return None
    lower, upper = value
    return [lower, upper]


def _is_false_positive(result: ScenarioResult) -> bool:
    return (
        result.expected_category in {"human", "low_evidence"}
        and result.recommended_action in {"soft_challenge", "step_up_auth", "manual_review"}
    )


def _is_false_negative(result: ScenarioResult) -> bool:
    return (
        result.expected_category in {"automation", "agentic_control"}
        and result.recommended_action in {"allow", "observe"}
    )
