from __future__ import annotations

from typing import Any


class RawContentRejected(ValueError):
    """Raised when an SDK payload includes raw user content."""


DISALLOWED_RAW_CONTENT_FIELDS = {
    "text",
    "raw_text",
    "typed_text",
    "value",
    "keys",
    "key_values",
    "password",
    "card_number",
    "ssn",
    "message_body",
    "freeform_content",
}

ALLOWED_AGGREGATE_FIELDS = {
    "mean_inter_key_interval_ms",
    "inter_key_interval_stddev_ms",
    "characters_per_minute",
    "correction_count",
    "correction_rate",
    "paste_count",
    "focus_to_first_input_ms",
    "prompt_render_to_first_input_ms",
    "response_latency_ms",
    "expected_reading_time_ms",
    "pointer_entropy",
    "click_hesitation_ms",
    "scroll_cadence_score",
}

_SENSITIVE_KEY_FRAGMENTS = {
    "password",
    "card_number",
    "cardnumber",
    "credit_card",
    "creditcard",
    "ssn",
    "social_security",
    "message_body",
    "freeform_content",
}

_SENSITIVE_INPUT_TYPES = {
    "cc-number",
    "cc-csc",
    "cc-exp",
    "credit-card",
    "file",
    "hidden",
    "payment",
    "password",
}


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def _is_disallowed_key(key: Any) -> bool:
    normalized = _normalize_key(key)
    return normalized in DISALLOWED_RAW_CONTENT_FIELDS or any(
        fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS
    )


def _is_sensitive_field_descriptor(key: Any, value: Any) -> bool:
    normalized = _normalize_key(key)
    if normalized not in {"input_type", "field_type", "autocomplete"}:
        return False
    if not isinstance(value, str):
        return False
    return value.strip().lower() in _SENSITIVE_INPUT_TYPES


def _scan_payload(value: Any, path: str, violations: list[str]) -> None:
    if isinstance(value, dict):
        for raw_key, raw_value in value.items():
            child_path = f"{path}.{raw_key}" if path else str(raw_key)
            if _is_disallowed_key(raw_key) or _is_sensitive_field_descriptor(raw_key, raw_value):
                violations.append(child_path)
                continue
            _scan_payload(raw_value, child_path, violations)
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_payload(item, f"{path}[{index}]", violations)


def ensure_privacy_safe_payload(payload: Any) -> None:
    """Reject raw content fields without echoing their values."""

    violations: list[str] = []
    _scan_payload(payload, "", violations)
    if violations:
        unique = sorted(set(violations))
        raise RawContentRejected(
            "Raw content fields are not allowed in TruePresence SDK payloads: "
            + ", ".join(unique)
        )


def strip_raw_content(payload: Any) -> Any:
    """Return a copy with raw-content fields removed."""

    if isinstance(payload, dict):
        stripped: dict[str, Any] = {}
        for key, value in payload.items():
            if _is_disallowed_key(key) or _is_sensitive_field_descriptor(key, value):
                continue
            stripped[str(key)] = strip_raw_content(value)
        return stripped
    if isinstance(payload, list):
        return [strip_raw_content(item) for item in payload]
    return payload
