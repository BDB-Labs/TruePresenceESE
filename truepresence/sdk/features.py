from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PrivacySafeFeatureModel(BaseModel):
    """Base model for aggregate behavior-derived features only."""

    model_config = ConfigDict(extra="forbid")


class TypingCadenceFeatures(PrivacySafeFeatureModel):
    mean_inter_key_interval_ms: float | None = Field(default=None, ge=0)
    inter_key_interval_stddev_ms: float | None = Field(default=None, ge=0)
    characters_per_minute: float | None = Field(default=None, ge=0)
    correction_count: int | None = Field(default=None, ge=0)
    correction_rate: float | None = Field(default=None, ge=0, le=1)
    paste_count: int | None = Field(default=None, ge=0)
    focus_to_first_input_ms: float | None = Field(default=None, ge=0)
    prompt_render_to_first_input_ms: float | None = Field(default=None, ge=0)
    typing_duration_ms: float | None = Field(default=None, ge=0)
    last_input_to_submit_ms: float | None = Field(default=None, ge=0)


class PointerBehaviorFeatures(PrivacySafeFeatureModel):
    pointer_entropy: float | None = Field(default=None, ge=0)
    click_hesitation_ms: float | None = Field(default=None, ge=0)
    scroll_cadence_score: float | None = Field(default=None, ge=0, le=1)
    pointer_movement_count: int | None = Field(default=None, ge=0)
    click_count: int | None = Field(default=None, ge=0)


class ChallengeInteractionFeatures(PrivacySafeFeatureModel):
    challenge_type: str | None = None
    response_latency_ms: float | None = Field(default=None, ge=0)
    expected_reading_time_ms: float | None = Field(default=None, ge=0)
    prompt_render_to_first_input_ms: float | None = Field(default=None, ge=0)
    correction_count: int | None = Field(default=None, ge=0)
    paste_count: int | None = Field(default=None, ge=0)
    typing_duration_ms: float | None = Field(default=None, ge=0)
    submitted_exactly: bool | None = None


class SessionContinuityFeatures(PrivacySafeFeatureModel):
    session_age_ms: float | None = Field(default=None, ge=0)
    prior_interaction_count: int | None = Field(default=None, ge=0)
    focus_blur_count: int | None = Field(default=None, ge=0)
    navigation_count: int | None = Field(default=None, ge=0)
    same_device_session_count: int | None = Field(default=None, ge=0)


class EnvironmentFeatures(PrivacySafeFeatureModel):
    webdriver_detected: bool | None = None
    automation_framework_hint: bool | None = None
    headless_browser_hint: bool | None = None
    reduced_motion_enabled: bool | None = None
    timezone_offset_minutes: int | None = None
    viewport_width: int | None = Field(default=None, ge=0)
    viewport_height: int | None = Field(default=None, ge=0)


class ExternalRiskProviderFeatures(PrivacySafeFeatureModel):
    provider_id: str
    risk_score: float = Field(ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list)
