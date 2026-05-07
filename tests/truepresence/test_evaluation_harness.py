"""
tests/truepresence/test_evaluation_harness.py
=============================================
Verifies the evaluation harness against the contract specified in the
feature/evaluation-harness task.

Covered requirements
--------------------
1. All fixtures load without error.
2. Privacy guard accepts every fixture (no raw content).
3. Known-human fixture does not overfire: automation_likelihood < 0.45.
4. Scripted-bot fixture elevates automation: automation_likelihood >= 0.55.
5. Browser-agent fixture: agentic signals present once detectors are active
   (currently a forward-looking guard — asserts the fixture itself is valid).
6. No fixture contains raw content fields (guard at load time, tested
   explicitly here as a belt-and-suspenders check).
7. ``run_scenario`` returns a populated ``ScenarioResult``.
8. ``build_report`` returns the required contract fields.
9. ``summarise_suite`` aggregates correctly.
"""

from __future__ import annotations

import json

import pytest

from truepresence.testing import (
    PrivacyGuardError,
    ScenarioResult,
    build_report,
    list_fixtures,
    load_fixture,
    run_scenario,
    summarise_suite,
)
from truepresence.testing.fixtures import FIXTURE_DIR

# ---------------------------------------------------------------------------
# All fixture stem names managed by this harness
# ---------------------------------------------------------------------------

ALL_FIXTURE_NAMES = [
    "human_like_session",
    "scripted_bot_session",
    "pasted_response_session",
    "uniform_typing_session",
    "impossible_reading_time_session",
    "playwright_like_session",
    "browser_agent_session",
    "mixed_human_agent_session",
]


# ===========================================================================
# Requirement 1 – fixtures load
# ===========================================================================

@pytest.mark.parametrize("name", ALL_FIXTURE_NAMES)
def test_fixture_loads(name: str) -> None:
    """Every fixture must load without raising any exception."""
    fixture = load_fixture(name)
    assert fixture["feature_packet"] is not None
    assert isinstance(fixture["signals"], list)
    assert isinstance(fixture["meta"], dict)
    assert fixture["name"] == name


def test_list_fixtures_includes_all_harness_fixtures() -> None:
    available = set(list_fixtures(FIXTURE_DIR))
    for name in ALL_FIXTURE_NAMES:
        assert name in available, f"Fixture '{name}' missing from {FIXTURE_DIR}"


# ===========================================================================
# Requirement 2 – privacy guard accepts fixtures
# ===========================================================================

@pytest.mark.parametrize("name", ALL_FIXTURE_NAMES)
def test_privacy_guard_accepts_fixture(name: str) -> None:
    """load_fixture must not raise PrivacyGuardError for any harness fixture."""
    try:
        load_fixture(name)
    except PrivacyGuardError as exc:
        pytest.fail(f"Privacy guard rejected fixture '{name}': {exc}")


# ===========================================================================
# Requirement 3 – known-human fixture does not overfire
# ===========================================================================

def test_human_like_fixture_does_not_overfire() -> None:
    """human_like_session must not produce a high automation_likelihood."""
    result = run_scenario(
        "human_like_session",
        expected_automation=(0.0, 0.44),
        expected_human_presence=(0.50, 1.0),
        expected_action={"allow", "observe"},
    )
    _assert_scenario(result)


# ===========================================================================
# Requirement 4 – scripted-bot fixture elevates automation
# ===========================================================================

def test_scripted_bot_fixture_elevates_automation() -> None:
    """scripted_bot_session must produce automation_likelihood >= 0.55."""
    result = run_scenario(
        "scripted_bot_session",
        expected_automation=(0.55, 1.0),
        expected_action={"step_up_auth", "manual_review"},
    )
    _assert_scenario(result)


def test_pasted_response_fixture_elevates_automation() -> None:
    result = run_scenario(
        "pasted_response_session",
        expected_automation=(0.45, 1.0),
    )
    assert result.response.automation_likelihood >= 0.45, (
        f"Expected automation >= 0.45, got {result.response.automation_likelihood:.4f}"
    )


def test_uniform_typing_fixture_elevates_automation() -> None:
    result = run_scenario(
        "uniform_typing_session",
        expected_automation=(0.45, 1.0),
    )
    assert result.response.automation_likelihood >= 0.45, (
        f"Expected automation >= 0.45, got {result.response.automation_likelihood:.4f}"
    )


def test_impossible_reading_time_fixture_elevates_agentic() -> None:
    """impossible_reading_time_session must fire an agentic signal."""
    result = run_scenario("impossible_reading_time_session")
    agentic_codes = {
        sig.reason_code
        for sig in result.all_signals
        if sig.contribution_target == "agentic_control"
    }
    assert agentic_codes, (
        "Expected at least one agentic_control signal from impossible_reading_time_session"
    )


# ===========================================================================
# Requirement 5 – browser-agent fixture is valid and well-formed
# (agentic detector elevation is a forward contract; asserted structurally)
# ===========================================================================

def test_browser_agent_fixture_is_valid_and_privacy_safe() -> None:
    """browser_agent_session loads cleanly and contains agentic feature fields."""
    fixture = load_fixture("browser_agent_session")
    packet = fixture["feature_packet"]
    assert packet.agentic is not None, "browser_agent_session must have agentic features"
    assert packet.agentic.action_burst_count is not None


def test_browser_agent_fixture_elevates_agentic_risk_once_detectors_are_active() -> None:
    """
    Forward contract: when agentic detectors are active the browser_agent_session
    fixture must produce agentic_control_likelihood > 0.20.

    Currently the agentic detectors DO fire on this fixture (burst_pause_action_loop,
    low_exploratory_noise, large_instant_input_delta, etc.), so we assert the
    condition already holds.  This test will catch any regression that silences
    the detectors.
    """
    result = run_scenario("browser_agent_session")
    assert result.response.agentic_control_likelihood > 0.20, (
        f"Expected agentic_control_likelihood > 0.20 for browser_agent_session, "
        f"got {result.response.agentic_control_likelihood:.4f}.  "
        "Check whether agentic detectors are running."
    )


# ===========================================================================
# Requirement 6 – no fixture contains raw content
# ===========================================================================

@pytest.mark.parametrize("name", ALL_FIXTURE_NAMES)
def test_no_fixture_contains_raw_content(name: str) -> None:
    """
    Belt-and-suspenders: read the raw JSON and assert there are no keys that
    match the global raw-content denylist regardless of nesting.
    """
    from truepresence.sdk.privacy import (
        _is_raw_content_key,  # type: ignore[attr-defined]
    )

    path = FIXTURE_DIR / f"{name}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    violations = _collect_raw_violations(raw, _is_raw_content_key)
    assert not violations, (
        f"Fixture '{name}' contains raw content fields: {violations}"
    )


def _collect_raw_violations(obj: object, checker, path: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child_path = f"{path}.{key}" if path else key
            # Allow _meta keys — they are documentation-only and not SDK fields
            if key == "_meta":
                continue
            if checker(key):
                violations.append(child_path)
            else:
                violations.extend(_collect_raw_violations(value, checker, child_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            violations.extend(_collect_raw_violations(item, checker, f"{path}[{i}]"))
    return violations


# ===========================================================================
# ScenarioResult / build_report / summarise_suite contracts
# ===========================================================================

def test_run_scenario_returns_scenario_result() -> None:
    result = run_scenario("human_like_session")
    assert isinstance(result, ScenarioResult)
    assert result.fixture_name == "human_like_session"
    assert result.response is not None


def test_build_report_has_required_fields() -> None:
    result = run_scenario("scripted_bot_session")
    report = build_report(result)

    required_keys = {
        "fixture_name",
        "expected_category",
        "likelihoods",
        "confidence",
        "recommended_action",
        "passed",
    }
    for key in required_keys:
        assert key in report, f"build_report missing required key: '{key}'"

    assert set(report["likelihoods"]) == {
        "human_presence", "automation", "agentic_control"
    }


def test_summarise_suite_aggregates_correctly() -> None:
    results = [
        run_scenario("human_like_session", expected_automation=(0.0, 0.44)),
        run_scenario("scripted_bot_session", expected_automation=(0.55, 1.0)),
    ]
    summary = summarise_suite(results)

    assert summary["total"] == 2
    assert summary["passed"] + summary["failed"] == summary["total"]
    assert isinstance(summary["summary"], str)
    assert "TruePresence Evaluation Suite" in summary["summary"]
    assert len(summary["fixtures"]) == 2


def test_summarise_suite_counts_failures_correctly() -> None:
    """A deliberately failing scenario must be counted as failed."""
    # Impossible range: automation must be > 1.0
    results = [
        run_scenario("human_like_session", expected_automation=(1.01, 1.0)),
    ]
    summary = summarise_suite(results)
    assert summary["failed"] == 1
    assert summary["passed"] == 0


# ===========================================================================
# Mixed-signal fixture structural check
# ===========================================================================

def test_mixed_human_agent_fixture_has_both_human_and_agentic_features() -> None:
    fixture = load_fixture("mixed_human_agent_session")
    packet = fixture["feature_packet"]
    assert packet.typing is not None, "mixed_human_agent_session must have typing features"
    assert packet.agentic is not None, "mixed_human_agent_session must have agentic features"
    assert (packet.typing.correction_count or 0) > 0, "Expect human-like corrections"
    assert (packet.agentic.action_burst_count or 0) >= 3, "Expect agentic burst pattern"


# ===========================================================================
# Helpers
# ===========================================================================

def _assert_scenario(result: ScenarioResult) -> None:
    """Assert that a scenario passed; print the report on failure."""
    if not result.passed:
        report = build_report(result)
        pytest.fail(
            f"Scenario '{result.fixture_name}' failed:\n"
            + "\n".join(f"  • {f}" for f in result.failures)
            + f"\n  likelihoods={report['likelihoods']}"
            + f"\n  action={report['recommended_action']}"
            + f"\n  confidence={report['confidence']:.4f}"
        )
