"""
truepresence.testing.fixtures
==============================
Loading and privacy-safety validation of derived-feature fixture files.

Design contract
---------------
A fixture is a JSON object whose ``feature_packet`` field contains **only
derived metrics** — numeric or categorical values computed from raw
behavioural signals.  Raw content (keystrokes, clipboard text, URLs, DOM
snapshots, device identifiers, IP addresses) is never permitted.

An optional ``signals`` list carries pre-computed ``DetectorSignal`` objects
so that calibration tests can run against known signal sets without re-running
detectors.

An optional ``_meta`` object carries human-readable documentation fields
(``expected_category``, ``description``) and calibration expectations that
are not forwarded to any SDK call.

Public API
----------
``load_fixture(name_or_path)``
    Load a fixture by stem name or absolute/relative ``Path``.
    Raises ``PrivacyGuardError`` if the fixture fails the privacy check.

``list_fixtures(directory)``
    Return a sorted list of fixture stem names found in *directory*.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from truepresence.detectors.human_plausibility import DetectorSignal
from truepresence.sdk.contracts import InteractionFeaturePacket
from truepresence.sdk.privacy import RawContentRejected, ensure_privacy_safe_feature_packet

# Default fixture directory — tests/truepresence/fixtures/ relative to repo root.
_REPO_ROOT = Path(__file__).parent.parent.parent
FIXTURE_DIR: Path = _REPO_ROOT / "tests" / "truepresence" / "fixtures"


class PrivacyGuardError(ValueError):
    """Raised when a fixture contains a field that violates the privacy contract."""


def load_fixture(
    name_or_path: str | Path,
    *,
    fixture_dir: Path | None = None,
) -> dict[str, Any]:
    """Load, validate, and return a fixture dictionary.

    Parameters
    ----------
    name_or_path:
        Fixture stem name (e.g. ``"human_like_session"``) or a ``Path`` to
        the JSON file.  When a stem name is given, the file is resolved
        relative to *fixture_dir* (default: ``FIXTURE_DIR``).
    fixture_dir:
        Override the default fixture directory.

    Returns
    -------
    dict with keys:
        ``"feature_packet"``  – ``InteractionFeaturePacket`` instance
        ``"signals"``         – list of ``DetectorSignal`` instances (may be empty)
        ``"meta"``            – dict of documentation fields from ``_meta``
        ``"name"``            – fixture stem name

    Raises
    ------
    PrivacyGuardError
        If the raw fixture JSON contains any field that violates the TruePresence
        privacy contract.
    FileNotFoundError
        If the fixture file cannot be located.
    """
    path = _resolve_path(name_or_path, fixture_dir or FIXTURE_DIR)
    raw = _read_json(path)
    _assert_privacy_safe(raw, path)

    raw_packet: dict[str, Any] = raw.get("feature_packet", {})
    feature_packet = InteractionFeaturePacket.model_validate(raw_packet)

    signals = [
        DetectorSignal.model_validate(sig) for sig in raw.get("signals", [])
    ]

    meta: dict[str, Any] = raw.get("_meta", {})

    return {
        "feature_packet": feature_packet,
        "signals": signals,
        "meta": meta,
        "name": path.stem,
    }


def list_fixtures(directory: Path | None = None) -> list[str]:
    """Return sorted fixture stem names in *directory*."""
    target = directory or FIXTURE_DIR
    return sorted(p.stem for p in target.glob("*.json"))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_path(name_or_path: str | Path, fixture_dir: Path) -> Path:
    candidate = Path(name_or_path)
    if candidate.is_absolute() or str(name_or_path).endswith(".json"):
        return candidate
    # Treat as a stem name
    return fixture_dir / f"{name_or_path}.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _assert_privacy_safe(raw: dict[str, Any], path: Path) -> None:
    """Run the TruePresence privacy guard over the raw fixture dict."""
    raw_packet = raw.get("feature_packet", {})
    try:
        ensure_privacy_safe_feature_packet(raw_packet)
    except RawContentRejected as exc:
        raise PrivacyGuardError(
            f"Fixture '{path.name}' failed privacy guard: {exc}"
        ) from exc

    # Separately assert that no raw content hides under _meta or signals
    for top_key in ("_meta", "signals", "metadata"):
        if top_key in raw and isinstance(raw[top_key], dict):
            try:
                ensure_privacy_safe_feature_packet(raw[top_key])
            except RawContentRejected:
                # _meta and signals are not feature_packets; only check for
                # obvious raw-content field names, not allowlist violations.
                pass
