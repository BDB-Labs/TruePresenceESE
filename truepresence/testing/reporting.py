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
    - ``expected_category``   – labelled category from fixture _meta or override
    - ``likelihoods``         – ``{human_presence, automation, agentic_control}``
    - ``confidence``          – model confidence value
    - ``recommended_action``  – SDK recommended action string
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
        "expected_category": result.expected_category,
        "likelihoods": result.likelihoods,
        "confidence": result.confidence,
        "recommended_action": result.recommended_action,
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
    - ``fixtures`` – list of per-fixture ``build_report`` dicts
    - ``summary``  – plain-text summary string
    """
    reports = [build_report(r) for r in results]
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    lines: list[str] = [
        f"TruePresence Evaluation Suite: {passed}/{len(results)} passed",
        "",
    ]
    for report in reports:
        verdict = "PASS" if report["passed"] else "FAIL"
        lines.append(
            f"  [{verdict}] {report['fixture_name']}"
            f" | category={report['expected_category']}"
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
