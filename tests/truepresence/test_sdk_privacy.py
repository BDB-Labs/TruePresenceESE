from __future__ import annotations

import pytest

from truepresence.sdk.privacy import RawContentRejected, ensure_privacy_safe_payload


def test_raw_typed_text_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload(
            {
                "feature_packet": {
                    "typing": {
                        "typed_text": "private answer",
                        "mean_inter_key_interval_ms": 120,
                    }
                }
            }
        )

    message = str(excinfo.value)
    assert "typed_text" in message
    assert "private answer" not in message


def test_raw_key_values_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({"feature_packet": {"typing": {"key_values": ["a", "b"]}}})

    assert "key_values" in str(excinfo.value)


def test_password_like_fields_rejected() -> None:
    with pytest.raises(RawContentRejected) as excinfo:
        ensure_privacy_safe_payload({"feature_packet": {"environment": {"password": "secret"}}})

    message = str(excinfo.value)
    assert "password" in message
    assert "secret" not in message


def test_timing_only_features_accepted() -> None:
    ensure_privacy_safe_payload(
        {
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
    )
