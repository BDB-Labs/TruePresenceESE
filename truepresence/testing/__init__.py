"""
truepresence.testing
====================
Controlled evaluation harness for TruePresence SDK.

Provides:
  - fixtures   : load and validate derived-feature fixture files
  - scenarios  : run the full evaluation pipeline against a fixture
  - reporting  : format and summarise evaluation results

Privacy contract
----------------
No raw behavioural content (keystrokes, clipboard text, URLs, DOM snapshots,
device identifiers, IP addresses) may appear inside any fixture or in any
object produced by this package.  The privacy guard in
``truepresence.sdk.privacy`` is called on every fixture before evaluation.
"""

from .fixtures import PrivacyGuardError, list_fixtures, load_fixture
from .reporting import build_report, summarise_suite
from .scenarios import ScenarioResult, run_scenario

__all__ = [
    "load_fixture",
    "list_fixtures",
    "PrivacyGuardError",
    "run_scenario",
    "ScenarioResult",
    "build_report",
    "summarise_suite",
]
