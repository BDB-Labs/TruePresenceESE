"""
Tests for TruePresence SDK privacy guard.

Covers:
  - Original denylist fields still rejected
  - Renamed raw-content fields rejected (answer, response, comment,
    description, message, content, body, caption, media_url, file_url,
    user_input, input_value, field_value, raw_input, raw_value, prompt,
    transcript)
  - Known aggregate / timing fields still accepted
  - Unknown fields inside known sections are rejected
  - Approved metadata / page_context aggregate keys are accepted
  - Arbitrary metadata fields are rejected by default
  - Deeply nested raw-content fields are caught regardless of depth
"""

from __future__ import annotations

import pytest

from truepresence.sdk.privacy import RawContentRejected, ensure_privacy_safe_payload

pytestmark = pytest.mark.sdk

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_TIMING_PAYLOAD = {
    "feature_packet": {
        "typing": {
            "mean_inter_key_interval_ms": 145,
            "inter_key_interval_stddev_ms": 52,
            "characters_per_minute": 205,
            "correction_count": 2,
            "correction_rate": 0.04,
            "paste_count": 0,
            "focus_to_first_input_ms": 320,
            "prompt_render_to_first_input_ms": 900,
        },
        "challenge": {
            "response_latency_ms": 4200,
            "expected_reading_time_ms": 1800,
        },
        "pointer": {
            "pointer_entropy": 0.71,
            "click_hesitation_ms": 240,
            "scroll_cadence_score": 0.64,
        },
    }
}


def _with_typing_field(key: str, value: object) -> dict:
    import copy
    payload = copy.deepcopy(_VALID_TIMING_PAYLOAD)
    payload["feature_packet"]["typing"][key] = value
    return payload


def _with_top_level_field(key: str, value: object) -> dict:
    return {"feature_packet": {key: value}}


# ---------------------------------------------------------------------------
# 1. Original denylist fields still rejected
# ---------------------------------------------------------------------------

def test_raw_typed_text_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload(_with_typing_field("typed_text", "private answer"))
    msg = str(excinfo.value)
    assert "typed_text" in msg
    assert "private answer" not in msg


def test_raw_key_values_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({"feature_packet": {"typing": {"key_values": ["a", "b"]}}})
    assert "key_values" in str(excinfo.value)


def test_password_field_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({"feature_packet": {"environment": {"password": "secret"}}})
    msg = str(excinfo.value)
    assert "password" in msg
    assert "secret" not in msg


def test_raw_text_field_rejected() -> None:
    with pytest.raises(RawContentRejected):
        ensure_privacy_safe_payload({"feature_packet": {"typing": {"text": "hello"}}})


def test_value_field_rejected() -> None:
    with pytest.raises(RawContentRejected):
        ensure_privacy_safe_payload({"feature_packet": {"typing": {"value": "something"}}})


# ---------------------------------------------------------------------------
# 2. Renamed raw-content fields rejected (hardening requirements)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field_name", [
    "answer",
    "response",
    "comment",
    "description",
    "body",
    "message",
    "content",
    "caption",
    "media_url",
    "file_url",
    "prompt",
    "raw_input",
    "raw_value",
    "transcript",
    "user_input",
    "input_value",
    "field_value",
])
def test_renamed_raw_content_field_rejected(field_name: str) -> None:
    """Any plausibly-raw-content field name must be rejected regardless of section."""
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "typing": {field_name: "some user text"},
            }
        })
    msg = str(excinfo.value)
    assert field_name in msg
    assert "some user text" not in msg


def test_renamed_raw_content_in_challenge_section_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "challenge": {"answer": "the answer"},
            }
        })
    assert "answer" in str(excinfo.value)


def test_renamed_raw_content_in_metadata_rejected() -> None:
    """Metadata is allowlisted and still gets the global raw-content denylist."""
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "metadata": {"message": "hello world"},
            }
        })
    assert "message" in str(excinfo.value)


def test_renamed_raw_content_at_request_level_rejected() -> None:
    """Raw-content names at any depth are caught, including top-level unknown keys."""
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({"response": "raw user answer"})
    assert "response" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 3. Approved aggregate fields still pass
# ---------------------------------------------------------------------------

def test_timing_only_features_accepted() -> None:
    ensure_privacy_safe_payload(_VALID_TIMING_PAYLOAD)


def test_full_valid_request_accepted() -> None:
    ensure_privacy_safe_payload({
        "session_id": "sess_abc",
        "tenant_id": "default",
        "enforcement_mode": "observe",
        "feature_packet": {
            "surface": "web",
            "site_id": "site_001",
            "session_id": "sess_abc",
            "tenant_id": "default",
            "typing": {
                "mean_inter_key_interval_ms": 180,
                "inter_key_interval_stddev_ms": 65,
                "characters_per_minute": 210,
                "correction_count": 2,
                "correction_rate": 0.04,
                "paste_count": 0,
                "focus_to_first_input_ms": 400,
                "prompt_render_to_first_input_ms": 950,
                "typing_duration_ms": 2200,
                "last_input_to_submit_ms": 180,
            },
            "challenge": {
                "response_latency_ms": 3800,
                "expected_reading_time_ms": 1500,
                "challenge_type": "typing_cadence",
                "correction_count": 1,
                "paste_count": 0,
                "typing_duration_ms": 1800,
                "submitted_exactly": True,
            },
            "pointer": {
                "pointer_entropy": 0.72,
                "click_hesitation_ms": 210,
                "scroll_cadence_score": 0.61,
                "pointer_movement_count": 42,
                "click_count": 3,
            },
            "environment": {
                "webdriver_detected": False,
                "headless_browser_hint": False,
                "viewport_width": 1440,
                "viewport_height": 900,
            },
            "session_continuity": {
                "session_age_ms": 12000,
                "focus_blur_count": 2,
            },
            "page_context": {
                "hostname": "example.com",
                "pathname": "/signup",
                "referrer_present": True,
            },
            "metadata": {
                "sdk_version": "0.2.0",
                "mode": "privacy_preserving",
                "tracked_field_count": 2,
                "typing_summary": {
                    "delete_key_count": 1,
                    "input_event_count": 12,
                    "last_input_to_submit_ms": 180,
                    "max_inter_key_interval_ms": 360,
                    "min_inter_key_interval_ms": 80,
                    "tracked_field_count": 2,
                },
            },
            "external_risk_provider": [
                {
                    "provider_id": "risk_provider_test",
                    "risk_score": 0.22,
                    "confidence": 0.74,
                    "reason_codes": ["aggregate_provider_signal"],
                }
            ],
        },
    })


def test_pointer_aggregate_fields_accepted() -> None:
    ensure_privacy_safe_payload({
        "feature_packet": {
            "pointer": {
                "pointer_entropy": 0.68,
                "pointer_movement_count": 35,
                "click_count": 2,
                "click_hesitation_ms": 180,
                "scroll_cadence_score": 0.55,
            }
        }
    })


# ---------------------------------------------------------------------------
# 4. Unknown fields inside known sections rejected (allowlist enforcement)
# ---------------------------------------------------------------------------

def test_unknown_top_level_request_field_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "session_id": "sess_abc",
            "tenant_id": "default",
            "feature_packet": {},
            "client_trace_id": "trace value that must not be echoed",
        })
    msg = str(excinfo.value)
    assert "client_trace_id" in msg
    assert "trace value that must not be echoed" not in msg


def test_legacy_request_id_field_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "session_id": "sess_abc",
            "tenant_id": "default",
            "feature_packet": {},
            "request_id": "request-id-value",
        })
    assert "request_id" in str(excinfo.value)


def test_legacy_flow_id_feature_packet_field_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "flow_id": "signup-flow",
            }
        })
    assert "flow_id" in str(excinfo.value)


def test_legacy_external_risk_section_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "external_risk": [
                    {"provider_id": "legacy", "risk_score": 0.2},
                ],
            }
        })
    assert "external_risk" in str(excinfo.value)


def test_unknown_field_in_typing_section_rejected() -> None:
    """A field not on the typing allowlist must be rejected even if it looks harmless."""
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "typing": {
                    "mean_inter_key_interval_ms": 180,
                    "raw_event_sequence": [1, 2, 3],
                }
            }
        })
    assert "raw_event_sequence" in str(excinfo.value)


def test_unknown_field_in_challenge_section_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "challenge": {
                    "response_latency_ms": 2000,
                    "challenge_html": "<p>type this</p>",
                }
            }
        })
    assert "challenge_html" in str(excinfo.value)


def test_unknown_field_in_pointer_section_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "pointer": {
                    "pointer_entropy": 0.5,
                    "raw_path": [[0, 0], [1, 1]],
                }
            }
        })
    assert "raw_path" in str(excinfo.value)


def test_arbitrary_metadata_field_rejected_by_default() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "metadata": {
                    "arbitrary_note": "do not echo this note",
                }
            }
        })
    msg = str(excinfo.value)
    assert "arbitrary_note" in msg
    assert "do not echo this note" not in msg


# ---------------------------------------------------------------------------
# 5. Approved metadata and page_context fields are accepted
# ---------------------------------------------------------------------------

def test_benign_metadata_passthrough_accepted() -> None:
    """Metadata and page_context accept approved aggregate/context keys."""
    ensure_privacy_safe_payload({
        "feature_packet": {
            "metadata": {
                "sdk_version": "0.2.0",
                "mode": "privacy_preserving",
                "tracked_field_count": 2,
                "typing_summary": {
                    "delete_key_count": 1,
                    "input_event_count": 5,
                    "last_input_to_submit_ms": 120,
                    "max_inter_key_interval_ms": 240,
                    "min_inter_key_interval_ms": 90,
                    "tracked_field_count": 1,
                },
            },
            "page_context": {
                "hostname": "example.test",
                "pathname": "/form",
                "referrer_present": False,
                "visibility_state": "visible",
            },
        }
    })


# ---------------------------------------------------------------------------
# 6. Deeply nested raw-content caught at any depth
# ---------------------------------------------------------------------------

def test_deeply_nested_raw_content_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "metadata": {
                    "debug": {
                        "capture": {
                            "typed_text": "deep secret",
                        }
                    }
                }
            }
        })
    assert "typed_text" in str(excinfo.value)


def test_raw_content_in_list_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {
                "metadata": {
                    "items": [{"typed_text": "secret"}]
                }
            }
        })
    assert "typed_text" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 7. Error messages never echo field values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field_name,field_value", [
    ("typed_text", "private answer text"),
    ("answer", "user submitted answer"),
    ("password", "hunter2"),
    ("message", "hello from user"),
])
def test_error_message_never_echoes_field_value(field_name: str, field_value: str) -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({
            "feature_packet": {"typing": {field_name: field_value}}
        })
    msg = str(excinfo.value)
    assert field_value not in msg
    assert field_name in msg
