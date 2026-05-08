# TruePresence Privacy-Preserving SDK Contract

## Purpose

TruePresence must evaluate interaction authenticity without collecting actual user content.

The product goal is not to record what a person types, reads, or submits. The product goal is to measure whether an interaction unfolds in a way that is consistent with human operation, scripted automation, or agentic AI control.

## Core Principle

> Collect behavior-derived features, not content.

TruePresence should never need raw field values, raw keystrokes, passwords, message text, payment data, medical text, or free-form user content to produce its core human-presence and automation-risk signals.

## What The SDK May Collect

The SDK may collect derived timing, rhythm, and interaction metrics such as:

- typing duration for a protected challenge or field;
- mean inter-key interval;
- inter-key interval variance / standard deviation;
- characters-per-minute estimate;
- correction count and correction rate;
- paste event count;
- time from field focus to first input;
- time from prompt render to first interaction;
- time from final interaction to submit;
- pointer movement entropy;
- click hesitation timing;
- scroll cadence summaries;
- focus / blur sequence metadata;
- challenge response latency;
- whether response timing was physically plausible for a human to read and respond.

These features should be computed locally where practical and transmitted as aggregate metrics.

## Schema Allowlist Enforcement

SDK evaluation payloads are closed-schema by default. The backend accepts only approved request fields and aggregate feature sections, then applies section-level allowlists before scoring.

Allowed top-level request fields:

- `session_id`;
- `tenant_id`;
- `enforcement_mode`;
- `feature_packet`.

Allowed `feature_packet` sections:

- `surface`;
- `site_id`;
- `session_id`;
- `tenant_id`;
- `page_context`;
- `metadata`;
- `typing`;
- `challenge`;
- `agentic`;
- `pointer`;
- `environment`;
- `session_continuity`;
- `external_risk_provider`.

Allowed behavioral feature fields are aggregate-only. Examples include `mean_inter_key_interval_ms`, `inter_key_interval_stddev_ms`, `characters_per_minute`, `correction_count`, `correction_rate`, `paste_count`, `focus_to_first_input_ms`, `prompt_render_to_first_input_ms`, `typing_duration_ms`, `last_input_to_submit_ms`, `response_latency_ms`, `expected_reading_time_ms`, `pointer_entropy`, `pointer_movement_count`, `click_count`, `click_hesitation_ms`, `scroll_cadence_score`, `action_burst_count`, `route_directness_score`, `large_instant_delta_count`, and `structured_retry_count`.

The backend rejects disallowed fields before scoring and before evidence artifacts are built. Browser SDK stripping is only a defensive client-side measure; direct API calls to `/api/v1/truepresence/evaluate-interaction` are subject to the same privacy rules as browser SDK submissions.

Arbitrary free-form fields are rejected by default, including renamed raw-content fields such as `answer`, `response`, `comment`, `description`, `body`, `message`, `prompt`, `transcript`, `content`, `caption`, `media_url`, `file_url`, `user_input`, `input_value`, `field_value`, `raw_value`, and `raw_input`.

## What The SDK Must Not Collect By Default

The SDK must not collect by default:

- actual typed text;
- raw key values;
- passwords;
- payment card data;
- Social Security numbers or government IDs;
- private messages;
- medical, legal, or other sensitive free-text content;
- complete pointer trails tied to a persistent identity;
- long-term biometric profiles unless explicitly enabled by the integrating site with appropriate disclosure and consent.

## Field-Level Controls

Integrating sites must be able to opt fields in or out explicitly.

Recommended HTML controls:

```html
<input data-truepresence="challenge" />
<input data-truepresence="timing-only" />
<textarea data-truepresence-ignore="true"></textarea>
```

Default behavior should ignore sensitive input types, including:

- password;
- payment;
- hidden;
- file;
- fields marked autocomplete for sensitive values where detectable;
- any element marked `data-truepresence-ignore="true"`.

## Challenge Design

TruePresence challenges should measure interaction process rather than private knowledge.

Examples:

- type a displayed phrase;
- click after a visual state change;
- select an indicated visual element;
- complete a short instruction where response time and input rhythm matter.

The system may evaluate whether:

- an answer appeared faster than a human could plausibly read the prompt;
- typing cadence was unnaturally uniform;
- there was no variation, hesitation, or correction where human variation is expected;
- text appeared through paste or script injection rather than typed input;
- interaction sequence resembles DOM automation rather than visual/manual use.

## Output Semantics

TruePresence outputs must be probabilistic and evidence-based.

Recommended signal fields:

```json
{
  "human_presence_likelihood": 0.74,
  "automation_likelihood": 0.22,
  "agentic_control_likelihood": 0.48,
  "confidence": 0.69,
  "reason_codes": [
    "uniform_typing_cadence",
    "implausible_read_response_time"
  ],
  "evidence_packet_id": "ep_...",
  "recommended_action": "step_up_challenge"
}
```

TruePresence must not claim certainty that an actor is human or non-human. It should state that observed interaction features are more or less consistent with human operation, automation, or agentic control.

## Privacy And Retention Defaults

Recommended defaults:

- raw browser events: in-memory only;
- derived feature windows: short-lived;
- evidence packet: retained according to site policy;
- no raw content retention;
- no persistent behavioral identity profile by default.

## Implementation Requirement

Any web SDK, testing SDK, Telegram adapter, or future surface adapter should map its telemetry into this privacy-preserving feature model before evidence packets are built.

TruePresence should be able to explain a decision without exposing what the user typed.

## Product Language

Preferred wording:

> TruePresence records how an interaction unfolds, not what a user types.

Avoid wording such as:

- "proves the user is human";
- "identifies bots with certainty";
- "records user typing";
- "behavioral biometric identity" unless a separate explicit feature is designed, disclosed, consented to, and governed.
