# TruePresence SDK Implementation Backlog

## Purpose

This backlog translates the current TruePresence product direction into concrete programming work.

TruePresence is not a Telegram-only moderation product. It is an integrated SDK and evidence system for determining whether an interaction is consistent with human operation, scripted automation, or AI-agentic control.

The core product claim must remain probabilistic and auditable:

> TruePresence records how an interaction unfolds, not what a user types.

## Product Boundary

TruePresence should be SDK-first and surface-agnostic.

Telegram is one adapter. The product center is an interaction-authenticity engine that can be embedded into websites, testing sites, staging environments, and community surfaces.

## Implementation Workstreams

### 1. SDK Core Contracts

Create a public SDK contract layer.

Proposed files:

- `truepresence/sdk/__init__.py`
- `truepresence/sdk/contracts.py`
- `truepresence/sdk/features.py`
- `truepresence/sdk/evaluation.py`
- `truepresence/sdk/privacy.py`

Required models:

- `InteractionFeaturePacket`
- `TypingCadenceFeatures`
- `PointerBehaviorFeatures`
- `ChallengeInteractionFeatures`
- `SessionContinuityFeatures`
- `EnvironmentFeatures`
- `ExternalRiskProviderFeatures`
- `TruePresenceEvaluationRequest`
- `TruePresenceEvaluationResponse`

Required response fields:

```json
{
  "human_presence_likelihood": 0.74,
  "automation_likelihood": 0.22,
  "agentic_control_likelihood": 0.48,
  "confidence": 0.69,
  "reason_codes": [],
  "evidence_packet_id": "ep_...",
  "recommended_action": "observe",
  "enforcement_mode": "observe"
}
```

Acceptance criteria:

- SDK contracts do not require raw user content.
- Feature models support timing, cadence, rhythm, interaction entropy, and plausibility signals.
- Response models remain probabilistic and avoid certainty claims.

### 2. Privacy-Preserving Feature Model

Implement derived-feature-only processing.

Proposed files:

- `truepresence/sdk/privacy.py`
- `truepresence/sdk/features.py`
- `truepresence/detectors/privacy_guard.py`

Required behavior:

- reject payloads containing raw typed text by default;
- reject raw key values by default;
- ignore password, payment, hidden, file, and explicitly ignored fields;
- allow only aggregate metrics unless an explicit non-default mode is added later;
- enforce `capture_content=false` as the default SDK posture.

Allowed feature examples:

- mean inter-key interval;
- inter-key interval standard deviation;
- characters-per-minute estimate;
- correction count;
- correction rate;
- paste count;
- time from field focus to first input;
- time from prompt render to first input;
- response latency;
- expected reading time;
- pointer entropy;
- click hesitation;
- scroll cadence summary.

Disallowed by default:

- actual typed text;
- raw key values;
- passwords;
- payment data;
- long-term biometric profiles;
- full pointer trails tied to persistent identity.

Acceptance criteria:

- tests prove raw content is rejected or stripped;
- tests prove timing-only payloads are accepted;
- docs state: “collect behavior-derived features, not content.”

### 3. Web Surface Adapter

Add a web/browser surface separate from Telegram.

Proposed files:

- `truepresence/surfaces/web/__init__.py`
- `truepresence/surfaces/web/adapter.py`
- `truepresence/surfaces/web/event_schema.py`
- `truepresence/surfaces/web/feature_normalizer.py`
- `truepresence/surfaces/web/routes.py`

Required endpoint:

```http
POST /api/v1/truepresence/evaluate-interaction
```

Input:

- session id;
- site id / tenant id;
- page context;
- derived behavior features;
- optional challenge metadata;
- optional external provider evidence.

Output:

- human presence likelihood;
- automation likelihood;
- agentic control likelihood;
- confidence;
- reason codes;
- evidence packet id;
- recommended action;
- enforcement mode.

Acceptance criteria:

- web evaluation can run without Telegram dependencies;
- web adapter maps feature packets into the existing evidence packet / argument graph / decision engine pipeline;
- endpoint returns a response compatible with SDK contracts.

### 4. Browser JavaScript SDK

Add a minimal privacy-preserving browser SDK.

Proposed files:

- `sdks/js/src/index.ts`
- `sdks/js/src/collector.ts`
- `sdks/js/src/features/typing.ts`
- `sdks/js/src/features/pointer.ts`
- `sdks/js/src/features/challenge.ts`
- `sdks/js/src/privacy.ts`
- `sdks/js/package.json`
- `sdks/js/README.md`

Public API sketch:

```ts
TruePresence.init({
  siteKey: "tp_site_...",
  endpoint: "https://example.com/api/v1/truepresence/evaluate-interaction",
  captureContent: false,
  mode: "privacy_preserving"
});

TruePresence.protectForm("#signup-form", {
  challenge: "typing_cadence",
  sensitivity: "medium"
});
```

Required behavior:

- collect derived metrics locally;
- never transmit raw text by default;
- ignore sensitive fields;
- support `data-truepresence="challenge"`;
- support `data-truepresence="timing-only"`;
- support `data-truepresence-ignore="true"`;
- send summarized feature packets to the server.

Acceptance criteria:

- unit tests prove no raw keystrokes or field contents are transmitted;
- integration fixture demonstrates protected form evaluation;
- SDK can operate in observe-only mode.

### 5. Human Plausibility Envelope

Implement detectors that evaluate whether interaction timing is plausible for human operation.

Proposed files:

- `truepresence/detectors/human_plausibility.py`
- `truepresence/detectors/typing_cadence.py`
- `truepresence/detectors/reading_time.py`
- `truepresence/detectors/pointer_entropy.py`

Required detectors:

- `implausible_read_response_time`;
- `uniform_typing_cadence`;
- `zero_correction_pattern`;
- `instant_full_input`;
- `paste_or_script_injection_pattern`;
- `no_pointer_interaction`;
- `low_interaction_entropy`;
- `impossible_sequence_timing`.

Reading-time detector:

- estimate minimum plausible reading time from prompt length;
- compare to response latency;
- emit reason code when response occurs faster than plausible human reading and response time.

Typing cadence detector:

- evaluate mean interval, variance, bursting, pauses, corrections, and paste events;
- treat perfectly uniform cadence as suspicious;
- avoid treating a single signal as determinative.

Acceptance criteria:

- detectors return reason codes and severity/confidence contributions;
- no detector directly decides “human” or “bot” alone;
- tests cover human-like, scripted, pasted, and implausibly fast examples.

### 6. Agentic-Control Detectors

Add detectors specifically aimed at AI browser agents, not just classic bots.

Proposed files:

- `truepresence/detectors/agentic_control.py`
- `truepresence/detectors/dom_automation.py`
- `truepresence/detectors/task_flow.py`

Target signals:

- DOM-first interaction patterns;
- low exploratory noise;
- direct navigation to relevant controls;
- unusually efficient task completion;
- model-thinking cadence: bursts of action separated by regular delays;
- structured retries;
- perfect recovery from errors;
- large text appears instantly;
- semantic intent jumps across page elements;
- automation API or webdriver indicators where visible.

Acceptance criteria:

- agentic-control score is separate from generic automation score;
- detectors support weak/medium/strong signal levels;
- tests include Playwright/Selenium-style traces and simulated AI-agent traces.

### 7. Scoring And Signal Fusion

Create a scoring model that combines multiple weak signals into a probabilistic result.

Proposed files:

- `truepresence/scoring/__init__.py`
- `truepresence/scoring/model.py`
- `truepresence/scoring/weights.py`
- `truepresence/scoring/calibration.py`

Required design:

- no single detector should create a final conclusion;
- combine signal severity, confidence, and corroboration;
- separate scores for:
  - `human_presence_likelihood`;
  - `automation_likelihood`;
  - `agentic_control_likelihood`;
- emit confidence separately from likelihood;
- preserve reason codes and evidence references.

Recommended initial approach:

- deterministic weighted signal fusion for v0;
- calibratable weights stored in config;
- later replace or augment with trained calibration after test corpus exists.

Acceptance criteria:

- tests show multiple weak signals can raise risk;
- tests show isolated weak signals do not overfire;
- tests show strong contradictions reduce confidence;
- scoring output includes explanation-ready reason codes.

### 8. Challenge Framework

Build process-based challenges that measure interaction mechanics rather than private knowledge.

Proposed files:

- `truepresence/challenges/__init__.py`
- `truepresence/challenges/base.py`
- `truepresence/challenges/typing_phrase.py`
- `truepresence/challenges/reaction_timing.py`
- `truepresence/challenges/visual_selection.py`

Challenge examples:

- type a displayed phrase;
- wait until visual state changes, then click;
- select an indicated visual element;
- follow a short instruction where timing and process matter.

Important rule:

- challenges should evaluate process, not collect private knowledge.

Acceptance criteria:

- challenge response can be evaluated without storing typed content;
- challenge outputs become derived features;
- challenge failures recommend step-up or review rather than automatic punitive action.

### 9. Enforcement Separation

Separate signal generation from enforcement across all surfaces.

Proposed files:

- `truepresence/policy/actions.py`
- `truepresence/policy/enforcement_mode.py`
- update Telegram adapter to use shared policy enforcement mode.

Required actions:

- `allow`;
- `observe`;
- `soft_challenge`;
- `step_up_auth`;
- `rate_limit`;
- `manual_review`;
- `block`.

Required modes:

- `observe`;
- `challenge_only`;
- `review_required`;
- `enforce`.

Acceptance criteria:

- default mode is observe;
- production enforcement is opt-in;
- Telegram does not remain the only enforcement model;
- SDK consumers receive recommended actions, not automatic punishment by default.

### 10. External Risk Provider Connectors

Allow third-party bot/fraud/attestation providers to contribute evidence without becoming the final authority.

Proposed files:

- `truepresence/risk_providers/__init__.py`
- `truepresence/risk_providers/base.py`
- `truepresence/risk_providers/cloudflare.py`
- `truepresence/risk_providers/fingerprint.py`
- `truepresence/risk_providers/recaptcha.py`
- `truepresence/risk_providers/arkose.py`

Required contract:

```python
class RiskProvider:
    def evaluate(self, request_context, session_context):
        ...
```

Provider results should include:

- provider name;
- provider confidence;
- risk score;
- reason codes;
- raw provider reference id;
- whether score was verified server-side.

Acceptance criteria:

- external scores enter evidence packets as evidence;
- external providers do not bypass TruePresence scoring;
- missing provider data degrades gracefully.

### 11. Testing And Staging Harness

Build a controlled evaluation harness so TruePresence can measure its own accuracy.

Proposed files:

- `truepresence/testing/__init__.py`
- `truepresence/testing/fixtures.py`
- `truepresence/testing/scenarios.py`
- `tests/truepresence/web/`
- `tests/truepresence/detectors/`
- `tests/truepresence/scoring/`
- `tests/truepresence/fixtures/human_like_session.json`
- `tests/truepresence/fixtures/scripted_bot_session.json`
- `tests/truepresence/fixtures/agentic_browser_session.json`

Scenario classes:

- known human-like session;
- pasted response session;
- perfectly uniform typing session;
- impossible reading-time response;
- Playwright/Selenium-like session;
- agentic browser session;
- mixed human-plus-agent session.

Acceptance criteria:

- test harness can report false positive / false negative behavior for fixtures;
- scoring model is validated against known scenarios;
- regression tests prevent privacy contract violations.

### 12. Evidence Packet Extension

Extend existing evidence packet generation to support SDK/web-derived features.

Proposed work:

- update `truepresence/evidence/packet.py`;
- update `truepresence/evidence/packet_builder.py`;
- add feature sections for typing, pointer, challenge, session continuity, environment, external risk, and agentic behavior.

Acceptance criteria:

- evidence packets can explain decisions without raw content;
- evidence packet includes feature summaries and reason codes;
- evidence packet stores enough context for audit/replay.

### 13. API And Dashboard Updates

Expose SDK/web evaluation separately from Telegram.

Proposed work:

- add `/api/v1/truepresence/evaluate-interaction`;
- add `/api/v1/truepresence/challenge/start`;
- add `/api/v1/truepresence/challenge/complete`;
- update dashboard to show SDK/web evaluations;
- distinguish Telegram adapter events from web SDK events.

Acceptance criteria:

- web evaluations visible in dashboard;
- dashboard shows likelihoods, confidence, reason codes, and evidence id;
- no raw typed content shown anywhere.

### 14. Documentation And Product Narrative

Write a product narrative that prevents Telegram from becoming the accidental product center.

Proposed docs:

- `docs/TRUEPRESENCE_PRODUCT_NARRATIVE.md`
- `docs/TRUEPRESENCE_WEB_SDK_CONTRACT.md`
- `docs/TRUEPRESENCE_DETECTION_MODEL.md`
- `docs/TRUEPRESENCE_PRIVACY_MODEL.md`
- update existing issue register to distinguish SDK-core issues from Telegram adapter issues.

Required language:

- “interaction authenticity”;
- “human-presence likelihood”;
- “automation likelihood”;
- “agentic-control likelihood”;
- “privacy-preserving derived features”;
- “signals, not certainty.”

Avoid:

- “proves human”;
- “detects all AI agents”;
- “identifies users by behavior”;
- “records typing.”

### 15. Immediate Fixes Already Identified

Carry forward the earlier Telegram hardening, but treat it as adapter hardening, not core product work.

Needed Telegram fixes:

- require webhook secret in production;
- add enforcement modes;
- default Telegram to observe mode;
- suppress punitive actions unless explicitly enabled;
- include execution outcome in webhook responses/logs;
- safer token decrypt fallback;
- idempotent moderation outbox in a later pass.

Acceptance criteria:

- Telegram adapter follows the same signal-first policy as the web SDK;
- Telegram does not bypass core enforcement mode controls.

## Recommended Build Order

1. SDK contracts and privacy-preserving feature models.
2. Human plausibility detectors: reading time, typing cadence, correction rate, paste/script injection.
3. Scoring and signal fusion.
4. Web surface adapter and `/evaluate-interaction` endpoint.
5. Minimal browser JS SDK.
6. Challenge framework.
7. Testing/staging harness with known scenarios.
8. Agentic-control detectors.
9. External risk provider connectors.
10. Dashboard updates.
11. Telegram adapter hardening using shared policy enforcement modes.

## Strategic Rule

TruePresence should never need to know what a user typed in order to decide whether the interaction looked human.

The product wins by measuring interaction plausibility, not by collecting private content.
