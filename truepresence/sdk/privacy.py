"""
TruePresence SDK Privacy Guard
==============================

Enforcement strategy: two complementary layers.

Layer 1 — Section-level allowlist
  For each structured section of a feature_packet (typing, challenge, pointer,
  agentic, environment, session_continuity, external_risk_provider,
  page_context, and metadata), only fields on the explicit allowlist are accepted. Any key not on
  the list is rejected; section schemas are closed by design.

Layer 2 — Global raw-content denylist
  Applied recursively across the whole payload.  Catches renamed raw-content
  fields (answer, response, comment, description, body, message, etc.) that
  could appear at any nesting depth.  This layer fires regardless of whether
  a field appears inside a known section.

The Pydantic models in contracts.py and features.py provide a third line of
defence via extra="forbid", but that runs after this guard.  This guard is
intentionally self-contained so it can protect the raw dict before any model
parsing occurs.

Context metadata sections
  page_context and metadata accept only known aggregate/context keys used by
  the browser SDK. They are intentionally not free-form passthroughs.
"""

from __future__ import annotations

from typing import Any


class RawContentRejected(ValueError):
    """Raised when an SDK payload includes raw user content."""


# ---------------------------------------------------------------------------
# Section-level field allowlists
# Each set defines every key that is permitted within that feature_packet
# section.  Any other key is either rejected outright (if it matches a
# raw-content pattern) or rejected as an unrecognised field.
# ---------------------------------------------------------------------------

_ALLOWED_TYPING_FIELDS: frozenset[str] = frozenset(
    {
        "characters_per_minute",
        "correction_count",
        "correction_rate",
        "focus_to_first_input_ms",
        "inter_key_interval_stddev_ms",
        "last_input_to_submit_ms",
        "mean_inter_key_interval_ms",
        "paste_count",
        "prompt_render_to_first_input_ms",
        "typing_duration_ms",
    }
)

_ALLOWED_CHALLENGE_FIELDS: frozenset[str] = frozenset(
    {
        "challenge_type",
        "correction_count",
        "expected_reading_time_ms",
        "paste_count",
        "prompt_render_to_first_input_ms",
        "response_latency_ms",
        "submitted_exactly",
        "typing_duration_ms",
    }
)

_ALLOWED_POINTER_FIELDS: frozenset[str] = frozenset(
    {
        "click_count",
        "click_hesitation_ms",
        "pointer_entropy",
        "pointer_movement_count",
        "scroll_cadence_score",
    }
)

_ALLOWED_ENVIRONMENT_FIELDS: frozenset[str] = frozenset(
    {
        "automation_framework_hint",
        "headless_browser_hint",
        "reduced_motion_enabled",
        "timezone_offset_minutes",
        "viewport_height",
        "viewport_width",
        "webdriver_detected",
    }
)

_ALLOWED_AGENTIC_FIELDS: frozenset[str] = frozenset(
    {
        "action_burst_count",
        "burst_interval_stddev_ms",
        "exploratory_action_count",
        "idle_to_action_latency_ms",
        "large_instant_delta_count",
        "mean_burst_interval_ms",
        "route_directness_score",
        "structured_retry_count",
        "submit_after_instant_input_ms",
        "validation_repair_count",
    }
)

_ALLOWED_SESSION_CONTINUITY_FIELDS: frozenset[str] = frozenset(
    {
        "focus_blur_count",
        "navigation_count",
        "prior_interaction_count",
        "same_device_session_count",
        "session_age_ms",
    }
)

# page_context is intentionally small: enough to identify surface context
# without URLs, query strings, field values, or arbitrary page content.
_ALLOWED_PAGE_CONTEXT_FIELDS: frozenset[str] = frozenset(
    {
        "hostname",
        "pathname",
        "referrer_present",
        "visibility_state",
    }
)

_ALLOWED_TYPING_SUMMARY_FIELDS: frozenset[str] = frozenset(
    {
        "delete_key_count",
        "input_event_count",
        "last_input_to_submit_ms",
        "max_inter_key_interval_ms",
        "min_inter_key_interval_ms",
        "tracked_field_count",
    }
)

_ALLOWED_METADATA_FIELDS: frozenset[str] = frozenset(
    {
        "mode",
        "sdk_version",
        "tracked_field_count",
        "typing_summary",
    }
)

# external_risk_provider items are structured objects; allowed fields per item:
_ALLOWED_EXTERNAL_RISK_FIELDS: frozenset[str] = frozenset(
    {
        "confidence",
        "provider_id",
        "reason_codes",
        "risk_score",
    }
)

# Top-level feature_packet keys that have their own sub-allowlists:
_SECTION_ALLOWLISTS: dict[str, frozenset[str]] = {
    "agentic": _ALLOWED_AGENTIC_FIELDS,
    "typing": _ALLOWED_TYPING_FIELDS,
    "challenge": _ALLOWED_CHALLENGE_FIELDS,
    "pointer": _ALLOWED_POINTER_FIELDS,
    "environment": _ALLOWED_ENVIRONMENT_FIELDS,
    "page_context": _ALLOWED_PAGE_CONTEXT_FIELDS,
    "session_continuity": _ALLOWED_SESSION_CONTINUITY_FIELDS,
}

# Top-level feature_packet scalar/identity fields — no sub-key enforcement:
_ALLOWED_PACKET_TOP_LEVEL: frozenset[str] = frozenset(
    {
        "agentic",
        "challenge",
        "environment",
        "external_risk_provider",
        "metadata",
        "page_context",
        "pointer",
        "session_continuity",
        "session_id",
        "site_id",
        "surface",
        "tenant_id",
        "typing",
    }
)

# Top-level request keys (wrapping feature_packet):
_ALLOWED_REQUEST_TOP_LEVEL: frozenset[str] = frozenset(
    {
        "enforcement_mode",
        "feature_packet",
        "session_id",
        "tenant_id",
    }
)

# ---------------------------------------------------------------------------
# Global raw-content denylist
# Applied at every level of the payload tree.  These names — and any key
# containing these fragments — are never allowed regardless of nesting depth.
# Covers both the original names and the renamed variants specified in the
# hardening requirements.
# ---------------------------------------------------------------------------

_RAW_CONTENT_EXACT: frozenset[str] = frozenset(
    {
        # Original denylist
        "card_number",
        "cardnumber",
        "freeform_content",
        "freeformcontent",
        "key",
        "key_values",
        "keyvalues",
        "keys",
        "message_body",
        "messagebody",
        "password",
        "raw_text",
        "rawtext",
        "ssn",
        "text",
        "typed_text",
        "typedtext",
        "value",
        # Renamed raw-content fields (hardening additions)
        "answer",
        "body",
        "comment",
        "content",
        "description",
        "field_value",
        "input_value",
        "message",
        "prompt",
        "raw_input",
        "raw_value",
        "response",
        "transcript",
        "user_input",
    }
)

_RAW_CONTENT_FRAGMENTS: frozenset[str] = frozenset(
    {
        "card_number",
        "cardnumber",
        "credit",
        "creditcard",
        "cvc",
        "cvv",
        "freeform",
        "message_body",
        "password",
        "raw_",
        "social_security",
        "ssn",
        "typed_",
    }
)

_SENSITIVE_INPUT_TYPES: frozenset[str] = frozenset(
    {
        "cc-csc",
        "cc-exp",
        "cc-number",
        "credit-card",
        "file",
        "hidden",
        "payment",
        "password",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def _is_raw_content_key(key: Any) -> bool:
    """Return True if the key matches the global raw-content denylist."""
    normalized = _normalize_key(key)
    if normalized in _RAW_CONTENT_EXACT:
        return True
    return any(fragment in normalized for fragment in _RAW_CONTENT_FRAGMENTS)


def _is_sensitive_field_descriptor(key: Any, value: Any) -> bool:
    """Return True for input_type/autocomplete fields that describe sensitive inputs."""
    normalized = _normalize_key(key)
    if normalized not in {"input_type", "field_type", "autocomplete"}:
        return False
    if not isinstance(value, str):
        return False
    return value.strip().lower() in _SENSITIVE_INPUT_TYPES


# ---------------------------------------------------------------------------
# Section-level allowlist scanning
# ---------------------------------------------------------------------------

def _scan_section(
    section_key: str,
    section_value: Any,
    allowlist: frozenset[str],
    path: str,
    violations: list[str],
) -> None:
    """
    Scan a known structured section against its field allowlist.
    Reject any key that is either a raw-content name or simply not permitted.
    """
    if not isinstance(section_value, dict):
        return

    for raw_key, raw_value in section_value.items():
        child_path = f"{path}.{raw_key}"
        normalized = _normalize_key(raw_key)

        # Check raw-content denylist first (gives a more specific error)
        if _is_raw_content_key(raw_key) or _is_sensitive_field_descriptor(raw_key, raw_value):
            violations.append(child_path)
            continue

        # Check section allowlist — reject anything not explicitly permitted
        if normalized not in allowlist:
            violations.append(child_path)
            _global_scan(raw_value, child_path, violations)
            continue

        # Recurse into sub-values to apply global denylist
        _global_scan(raw_value, child_path, violations)


def _scan_external_risk_list(
    items: Any,
    path: str,
    violations: list[str],
) -> None:
    if not isinstance(items, list):
        return
    for i, item in enumerate(items):
        item_path = f"{path}[{i}]"
        if not isinstance(item, dict):
            continue
        for raw_key, raw_value in item.items():
            child_path = f"{item_path}.{raw_key}"
            normalized = _normalize_key(raw_key)
            if _is_raw_content_key(raw_key):
                violations.append(child_path)
                continue
            if normalized not in _ALLOWED_EXTERNAL_RISK_FIELDS:
                violations.append(child_path)
                _global_scan(raw_value, child_path, violations)
                continue
            _global_scan(raw_value, child_path, violations)


def _scan_metadata(metadata: Any, path: str, violations: list[str]) -> None:
    if not isinstance(metadata, dict):
        return

    for raw_key, raw_value in metadata.items():
        child_path = f"{path}.{raw_key}"
        normalized = _normalize_key(raw_key)
        if _is_raw_content_key(raw_key) or _is_sensitive_field_descriptor(raw_key, raw_value):
            violations.append(child_path)
            continue
        if normalized not in _ALLOWED_METADATA_FIELDS:
            violations.append(child_path)
            _global_scan(raw_value, child_path, violations)
            continue
        if normalized == "typing_summary":
            _scan_section(
                normalized,
                raw_value,
                _ALLOWED_TYPING_SUMMARY_FIELDS,
                child_path,
                violations,
            )
        else:
            _global_scan(raw_value, child_path, violations)


# ---------------------------------------------------------------------------
# Global recursive denylist scan
# Used anywhere allowlist scanning delegates to nested values.
# ---------------------------------------------------------------------------

def _global_scan(value: Any, path: str, violations: list[str]) -> None:
    if isinstance(value, dict):
        for raw_key, raw_value in value.items():
            child_path = f"{path}.{raw_key}" if path else str(raw_key)
            if _is_raw_content_key(raw_key) or _is_sensitive_field_descriptor(raw_key, raw_value):
                violations.append(child_path)
                continue
            _global_scan(raw_value, child_path, violations)
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _global_scan(item, f"{path}[{index}]", violations)


# ---------------------------------------------------------------------------
# feature_packet scan: allowlist + global denylist combined
# ---------------------------------------------------------------------------

def _scan_feature_packet(packet: Any, path: str, violations: list[str]) -> None:
    if not isinstance(packet, dict):
        return

    for raw_key, raw_value in packet.items():
        child_path = f"{path}.{raw_key}"
        normalized = _normalize_key(raw_key)

        # Global denylist check first
        if _is_raw_content_key(raw_key):
            violations.append(child_path)
            continue

        # Check against top-level packet allowlist
        if normalized not in _ALLOWED_PACKET_TOP_LEVEL:
            violations.append(child_path)
            _global_scan(raw_value, child_path, violations)
            continue

        # Dispatch to section-specific allowlist scanner
        if normalized in _SECTION_ALLOWLISTS:
            _scan_section(normalized, raw_value, _SECTION_ALLOWLISTS[normalized], child_path, violations)
        elif normalized == "metadata":
            _scan_metadata(raw_value, child_path, violations)
        elif normalized == "external_risk_provider":
            _scan_external_risk_list(raw_value, child_path, violations)
        else:
            # scalar identity fields still get recursive raw-content scans
            _global_scan(raw_value, child_path, violations)


# ---------------------------------------------------------------------------
# Top-level request scan
# ---------------------------------------------------------------------------

def _scan_request(payload: Any, violations: list[str]) -> None:
    if not isinstance(payload, dict):
        _global_scan(payload, "", violations)
        return

    for raw_key, raw_value in payload.items():
        child_path = str(raw_key)
        normalized = _normalize_key(raw_key)

        if _is_raw_content_key(raw_key):
            violations.append(child_path)
            continue

        if normalized not in _ALLOWED_REQUEST_TOP_LEVEL:
            violations.append(child_path)
            _global_scan(raw_value, child_path, violations)
            continue

        if normalized == "feature_packet":
            _scan_feature_packet(raw_value, child_path, violations)
        else:
            _global_scan(raw_value, child_path, violations)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure_privacy_safe_payload(payload: Any) -> None:
    """
    Reject any SDK payload that contains raw user content.

    Raises RawContentRejected without echoing field values.
    Called before Pydantic model parsing so that raw dicts are validated
    before any model constructor runs.
    """
    violations: list[str] = []
    _scan_request(payload, violations)

    _raise_if_violations(violations)


def ensure_privacy_safe_feature_packet(packet: Any) -> None:
    """Reject raw or disallowed fields in a bare feature_packet dict."""
    violations: list[str] = []
    _scan_feature_packet(packet, "feature_packet", violations)
    _raise_if_violations(violations)


def _raise_if_violations(violations: list[str]) -> None:
    if not violations:
        return
    unique = sorted(set(violations))
    raise RawContentRejected(
        "Raw or disallowed fields are not accepted in TruePresence SDK payloads: "
        + ", ".join(unique)
    )


def strip_raw_content(payload: Any) -> Any:
    """
    Return a shallow-cleaned copy with globally disallowed raw-content fields
    removed.  Used by the browser SDK's client-side strip pass; the server
    always calls ensure_privacy_safe_payload and raises rather than silently
    stripping.
    """
    if isinstance(payload, dict):
        stripped: dict[str, Any] = {}
        for key, value in payload.items():
            if _is_raw_content_key(key) or _is_sensitive_field_descriptor(key, value):
                continue
            stripped[str(key)] = strip_raw_content(value)
        return stripped
    if isinstance(payload, list):
        return [strip_raw_content(item) for item in payload]
    return payload


# Preserve original export name for any importers using the old alias
DISALLOWED_RAW_CONTENT_FIELDS = _RAW_CONTENT_EXACT
ALLOWED_AGGREGATE_FIELDS = (
    _ALLOWED_TYPING_FIELDS
    | _ALLOWED_CHALLENGE_FIELDS
    | _ALLOWED_POINTER_FIELDS
    | _ALLOWED_AGENTIC_FIELDS
)
