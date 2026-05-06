# TruePresence Testing Harness

> **Branch:** `feature/evaluation-harness`  
> **Status:** Active  

The TruePresence evaluation harness provides a repeatable, privacy-safe way to measure SDK behaviour against a curated set of known-category sessions.

---

## Table of contents

1. [Purpose](#purpose)  
2. [Directory layout](#directory-layout)  
3. [Fixtures](#fixtures)  
   - [Format](#fixture-format)  
   - [Privacy contract](#privacy-contract)  
   - [Built-in fixtures](#built-in-fixtures)  
   - [Adding a new fixture](#adding-a-new-fixture)  
4. [Harness modules](#harness-modules)  
   - [fixtures.py](#fixturespy)  
   - [scenarios.py](#scenariospy)  
   - [reporting.py](#reportingpy)  
5. [Running the harness](#running-the-harness)  
6. [Interpreting results](#interpreting-results)  
   - [False positives](#false-positives)  
   - [False negatives](#false-negatives)  
7. [CI integration](#ci-integration)  

---

## Purpose

Detectors and the probabilistic scoring model must be validated against controlled inputs before any production deployment.  Ad-hoc unit tests that construct feature packets inline are fragile and difficult to audit.  The harness solves three problems:

- **Repeatability** — fixtures are versioned JSON files that produce the same output every run.
- **Auditability** — each fixture documents its intended category and the behaviours it exercises.
- **Privacy safety** — the privacy guard runs on every fixture load; a fixture that leaks raw content is rejected before any code runs.

---

## Directory layout

```
truepresence/
  testing/
    __init__.py          Public API re-exports
    fixtures.py          Fixture loader + privacy guard wrapper
    scenarios.py         Scenario runner (detectors → scoring → assertions)
    reporting.py         Structured report and suite summary formatters

tests/truepresence/
  fixtures/              JSON fixture files (derived metrics only)
  test_evaluation_harness.py   Pytest suite for the harness
```

---

## Fixtures

### Fixture format

```json
{
  "feature_packet": { ... },   // InteractionFeaturePacket fields (derived metrics only)
  "signals": [ ... ],          // optional pre-computed DetectorSignal objects
  "_meta": {
    "expected_category": "automation",
    "description": "Human-readable description of what this fixture models."
  }
}
```

- **`feature_packet`** must contain only fields permitted by `InteractionFeaturePacket` and the section allowlists in `truepresence.sdk.privacy`.  Any raw field (keystrokes, clipboard text, URLs) causes the fixture to fail the privacy guard.
- **`signals`** are merged with detector output at run time.  A fixture signal de-duplicates against a detector signal with the same `reason_code`; the fixture signal wins.  Use this to inject a signal that the current detector set cannot produce yet (e.g. a future `external_provider_flag`).
- **`_meta`** is documentation only.  It is never forwarded to the SDK.

### Privacy contract

Every field in a fixture — including inside `_meta` — is checked against the global raw-content denylist in `truepresence.sdk.privacy`.  The denylist covers exact names (`text`, `password`, `answer`, `response`, `body`, …) and fragment matches (`raw_`, `typed_`, `freeform`, …).

A fixture that violates this contract raises `truepresence.testing.PrivacyGuardError` and cannot be loaded.  This is intentional: a fixture that would be rejected by the SDK in production must also be rejected in tests.

### Built-in fixtures

| Fixture | Expected category | Key signals exercised |
|---|---|---|
| `human_like_session` | `human` | Natural typing cadence, corrections, high pointer entropy, real reading latency |
| `scripted_bot_session` | `automation` | Near-zero IKI stddev, instant paste, webdriver hints, zero corrections |
| `pasted_response_session` | `automation` | Single paste, sub-50 ms focus-to-input, no keystrokes |
| `uniform_typing_session` | `automation` | Zero IKI stddev, fast CPM, no corrections |
| `impossible_reading_time_session` | `agentic_control` | Response latency 90 ms vs 4 800 ms expected reading time |
| `playwright_like_session` | `agentic_control` | Burst/pause loop, high route directness, automation framework hint, near-zero IKI variance |
| `browser_agent_session` | `agentic_control` | Webdriver + headless + all agentic fields active, impossible reading time |
| `mixed_human_agent_session` | `mixed` | Human-plausible typing + agentic burst/pause loops; produces contradictory signals |

### Adding a new fixture

1. **Choose a stem name** that describes the scenario (snake_case, no spaces).
2. **Create `tests/truepresence/fixtures/<name>.json`** using the format above.
3. **Populate `feature_packet`** with derived metrics only.  Do not include raw content of any kind.  Refer to `truepresence/sdk/features.py` for the full list of allowed field names.
4. **Set `_meta.expected_category`** to one of: `human`, `automation`, `agentic_control`, `mixed`, `unknown`.
5. **Verify the privacy guard accepts it:**
   ```bash
   PYTHONPATH=. python -c "
   from truepresence.testing import load_fixture
   load_fixture('your_fixture_name')
   print('OK')
   "
   ```
6. **Add a test** in `tests/truepresence/test_evaluation_harness.py` (or a new file) that calls `run_scenario` with an appropriate expected range.
7. **Add the stem name** to `ALL_FIXTURE_NAMES` in `test_evaluation_harness.py` so it is picked up by the parametrised fixture-load and privacy-guard tests.

---

## Harness modules

### fixtures.py

```python
from truepresence.testing import load_fixture, list_fixtures, PrivacyGuardError

# Load by stem name
fixture = load_fixture("human_like_session")
packet  = fixture["feature_packet"]   # InteractionFeaturePacket
signals = fixture["signals"]          # list[DetectorSignal]
meta    = fixture["meta"]             # dict (expected_category, description)
name    = fixture["name"]             # "human_like_session"

# List available fixtures
names = list_fixtures()               # sorted list of stem names
```

### scenarios.py

```python
from truepresence.testing import run_scenario, ScenarioResult

result: ScenarioResult = run_scenario(
    "scripted_bot_session",
    expected_automation=(0.55, 1.0),           # (min, max) inclusive
    expected_action={"step_up_auth", "manual_review"},
)

result.passed            # True / False
result.likelihoods       # {"human_presence": …, "automation": …, "agentic_control": …}
result.confidence        # float
result.recommended_action
result.all_signals       # merged list of DetectorSignal
result.failures          # list of human-readable failure strings
```

All `expected_*` parameters are optional.  Omit any to skip that assertion.

### reporting.py

```python
from truepresence.testing import build_report, summarise_suite

# Single report
report = build_report(result)
# Keys: fixture_name, expected_category, likelihoods, confidence,
#       recommended_action, reason_codes, signal_count,
#       assertions, failures, passed

# Suite summary
results = [run_scenario(n) for n in ["human_like_session", "scripted_bot_session"]]
suite   = summarise_suite(results)
print(suite["summary"])
# Keys: total, passed, failed, fixtures, summary
```

---

## Running the harness

```bash
# From the repo root
PYTHONPATH=. pytest tests/truepresence/test_evaluation_harness.py tests/truepresence/test_sdk_scoring.py -q
```

Expected output (baseline):
```
59 passed in 0.18s
```

To run only the harness:
```bash
PYTHONPATH=. pytest tests/truepresence/test_evaluation_harness.py -v
```

---

## Interpreting results

### False positives

A false positive occurs when a fixture representing a known-human session triggers a high automation or agentic likelihood.

**Diagnostic steps:**
1. Check `result.all_signals` — identify which `reason_code` fired.
2. Review the detector that produced the signal.  Is the fixture feature value actually within the detector's threshold window?
3. If the fixture is genuinely human-like but the detector fires, consider tightening the detector threshold or adding a human-feature support factor.
4. If the fixture has ambiguous values, update `_meta.description` and adjust the `expected_*` range to reflect the true ambiguity.

**Do not** simply widen expected ranges to make a test pass.  The threshold should be justified by the detector logic.

### False negatives

A false negative occurs when a fixture representing automation or agentic control does not produce a sufficiently elevated likelihood.

**Diagnostic steps:**
1. Check `result.all_signals` — confirm expected signals are present.
2. If no signal fired, verify that the fixture feature values actually satisfy the detector's trigger conditions (e.g. `inter_key_interval_stddev_ms <= 1` for `uniform_typing_cadence` at high severity).
3. If signals are present but the score is low, check the human-feature support path: strong pointer entropy or correction counts reduce the adjusted risk.  A fixture with strong human-support values alongside automation signals will produce a contradictory/mixed result — which may be correct.
4. For agentic detectors, verify the `agentic` feature block is populated.  An absent `agentic` sub-object produces zero agentic signals.

---

## CI integration

The harness is included in the standard pytest run.  The GitHub Actions workflow at `.github/workflows/` runs:

```bash
PYTHONPATH=. pytest tests/ -q
```

All harness tests run automatically on every pull request to `main`.  The harness tests must pass before merge.
