# TruePresence SDK Implementation Backlog

## Purpose

This backlog tracks the SDK-first TruePresence workstreams after the SDK, scoring, Telegram, safety, and dashboard evidence-card merges. It distinguishes completed v0 work from remaining hardening and roadmap items.

TruePresence remains an integrated SDK and evidence system for estimating whether an interaction is consistent with human operation, scripted automation, or AI-agentic control.

The core product claim remains probabilistic and auditable:

> TruePresence records how an interaction unfolds, not what a user types.

## Product Boundary

TruePresence is SDK-first and surface-agnostic. Telegram is one adapter. The product center is an interaction-authenticity engine that can be embedded into websites, testing sites, staging environments, and community surfaces.

## Document Map

| Document | Role |
|---|---|
| [README](../README.md) | Product-forward overview and quickstart |
| [Browser SDK](TRUEPRESENCE_BROWSER_SDK.md) | Browser SDK API and integration guide |
| [Privacy contract](TRUEPRESENCE_PRIVACY_PRESERVING_SDK_CONTRACT.md) | Privacy-safe payload and output semantics |
| [Scoring model](TRUEPRESENCE_SCORING_MODEL.md) | Deterministic probabilistic scoring model |
| [Codebase map](TRUEPRESENCE_CODEBASE_MAP.md) | Canonical package paths, modules, and entry points |
| [Dashboard evidence](TRUEPRESENCE_DASHBOARD.md) | Privacy-safe evidence-card display rules |
| [Roadmap](TRUEPRESENCE_ROADMAP.md) | Prioritized workstream status table |

## Completed V0 Work

These items are implemented enough to serve as the current baseline. They may still have hardening items listed in the roadmap.

| Workstream | Status | Evidence | Notes |
|---|---|---|---|
| README product positioning | Implemented v0 | [README](../README.md) | README now positions TruePresence as a privacy-preserving interaction authenticity SDK, not a Telegram-only moderation product. |
| SDK contracts | Implemented v0 | `truepresence/sdk/contracts.py`, `truepresence/sdk/features.py` | Request and response models include likelihoods, confidence, reason codes, evidence packet IDs, recommended action, and enforcement mode. |
| Privacy-preserving feature model v0 | Implemented v0 | `truepresence/sdk/privacy.py`, `truepresence/sdk/privacy.js`, [privacy contract](TRUEPRESENCE_PRIVACY_PRESERVING_SDK_CONTRACT.md) | Closed schemas and allowlists reject raw content fields before scoring. Further allowlist hardening remains. |
| Backend evaluation endpoint | Implemented v0 | `POST /api/v1/truepresence/evaluate-interaction` in `truepresence/api/server.py` | Web/SDK evaluations run without Telegram dependencies and return SDK contract responses. |
| Browser JavaScript SDK | Implemented v0 | `truepresence/sdk/index.js`, `tests/browser-sdk/truepresence-browser-sdk.test.mjs`, [browser SDK doc](TRUEPRESENCE_BROWSER_SDK.md) | Collects derived form, typing, pointer, and challenge summaries without transmitting raw text by default. |
| Human plausibility detectors | Implemented v0 | `truepresence/detectors/human_plausibility.py`, `typing_cadence.py`, `reading_time.py` | Emits weak signal reason codes and confidence/severity contributions. |
| Calibrated scoring model | Implemented v0 | `truepresence/scoring/model.py`, `truepresence/scoring/weights.py`, [scoring doc](TRUEPRESENCE_SCORING_MODEL.md) | Deterministic probabilistic scoring with category-aware aggregation, confidence, and reason codes. |

## Remaining Roadmap Backlog

| Workstream | Current status | Remaining work | Target branch |
|---|---|---|---|
| Privacy allowlist hardening | Implemented v0; needs hardening | Expand negative tests for renamed content fields, nested metadata, URLs, clipboard/path fields, and future SDK sections. Keep rejecting unsafe payloads before scoring. | `feature/privacy-allowlist-hardening` |
| Agentic-control detectors | Implemented v0; needs hardening | Calibrate thresholds with additional Playwright/Selenium and browser-agent traces, reduce false positives for power users and accessibility tooling, and document production tuning limits. | `feature/agentic-control-detectors` |
| Evidence artifact linkage | Implemented v0; needs durable linkage | Replace process-local SDK artifact storage with durable tenant-scoped persistence, link decision artifacts and evidence artifacts consistently, and define retention controls. | `feature/evidence-artifact-linkage` |
| Testing harness | Implemented v0; needs broader coverage | Add scenario coverage for more surfaces, tenant policies, dashboard payloads, regression reporting, and production-like fixtures. | `feature/evaluation-harness` |
| Challenge framework | Implemented v0 modules; API/UI incomplete | Expose challenge start/complete routes, connect challenge outputs to SDK feature packets, and ensure challenge responses remain content-minimized. | `feature/challenge-framework` |
| Risk provider connectors | Planned; not yet implemented as provider connectors | Add third-party provider adapter contracts for bot, fraud, attestation, or lawful media-risk providers. Provider outputs should enter evidence without becoming the final authority. | `feature/risk-provider-connectors` |
| Telegram community signals | Implemented v0; needs production hardening | Calibrate metadata-only thresholds, add tenant policy controls, and continue preventing message text, captions, raw media IDs, and previews from entering evidence cards. | `feature/telegram-community-signals` |
| Telegram safety escalation | Implemented v0; needs operational hardening | Validate lawful-provider workflows, escalation policy configuration, retention, and no-media-preview dashboard behavior under production tenant settings. | `feature/telegram-safety-escalation` |
| Dashboard evidence cards | Implemented v0; needs production data validation | Validate against real tenant data, durable SDK evidence artifacts, and richer empty/error states while preserving the no-content display boundary. | `feature/dashboard-evidence-cards` |

See [TRUEPRESENCE_ROADMAP.md](TRUEPRESENCE_ROADMAP.md) for the priority-ranked roadmap table.

## Status Notes By Workstream

### SDK Contracts

Status: implemented v0.

The public SDK contract layer lives under `truepresence/sdk/` and defines:

- `InteractionFeaturePacket`
- `TypingCadenceFeatures`
- `PointerBehaviorFeatures`
- `ChallengeInteractionFeatures`
- `AgenticBehaviorFeatures`
- `SessionContinuityFeatures`
- `EnvironmentFeatures`
- `ExternalRiskProviderFeatures`
- `TruePresenceEvaluationRequest`
- `TruePresenceEvaluationResponse`

The response remains probabilistic and includes:

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

### Privacy-Preserving Feature Model

Status: implemented v0; needs hardening.

The current model rejects raw typed text, raw key values, arbitrary unknown fields, and renamed raw-content fields. It accepts aggregate timing, cadence, pointer, challenge, environment, session-continuity, agentic, and external-risk-provider summaries.

Remaining work is not a new privacy model. It is allowlist hardening, regression coverage, and review of every new feature section before it can enter SDK payloads.

### Web/SDK Evaluation Endpoint

Status: implemented v0.

The SDK endpoint is:

```http
POST /api/v1/truepresence/evaluate-interaction
```

It accepts privacy-safe feature packets and returns `TruePresenceEvaluationResponse`. It runs independently of Telegram.

### Browser JavaScript SDK

Status: implemented v0.

The browser SDK lives in `truepresence/sdk/*.js` and is documented in [TRUEPRESENCE_BROWSER_SDK.md](TRUEPRESENCE_BROWSER_SDK.md). It collects derived metrics locally and excludes raw text, sensitive fields, file fields, and ignored fields by default.

### Human Plausibility Detectors

Status: implemented v0.

Current detector coverage includes typing cadence, reading-time plausibility, paste/instant input patterns, correction patterns, pointer summaries, and human-consistent evidence. No detector alone should decide a final outcome.

### Agentic-Control Detectors

Status: implemented v0; needs hardening.

Agentic-control detection is intentionally separate from generic automation. The v0 detector family contributes to `agentic_control_likelihood`, but production tuning remains. See [TRUEPRESENCE_AGENTIC_DETECTION.md](TRUEPRESENCE_AGENTIC_DETECTION.md).

### Scoring And Signal Fusion

Status: implemented v0.

The deterministic probabilistic scorer aggregates signals by category, avoids overcounting repeated signals from the same category, applies corroboration and contradiction handling, and emits likelihoods, confidence, reason codes, and recommended action.

### Evidence Artifacts

Status: implemented v0; needs durable linkage.

SDK evidence artifacts are content-minimized and retrievable by `evidence_packet_id`. The first pass uses process-local storage and therefore needs production persistence, tenant scoping, retention controls, and stronger decision-artifact linkage. See [TRUEPRESENCE_EVIDENCE_ARTIFACTS.md](TRUEPRESENCE_EVIDENCE_ARTIFACTS.md).

### Challenge Framework

Status: implemented v0 modules; API/UI incomplete.

Challenge modules exist under `truepresence/challenges/`, but the product still needs SDK-facing challenge start/complete routes and dashboard/admin observability. Challenges must evaluate process, not private knowledge.

### Risk Provider Connectors

Status: planned; not yet implemented as provider connectors.

The SDK has an `ExternalRiskProviderFeatures` data shape and Telegram safety has a media-risk provider protocol, but there is no general `truepresence/risk_providers/` connector package yet.

### Telegram Community Signals

Status: implemented v0; needs production hardening.

Telegram community signals are metadata-only and documented in [TRUEPRESENCE_TELEGRAM_COMMUNITY_SIGNALS.md](TRUEPRESENCE_TELEGRAM_COMMUNITY_SIGNALS.md). Remaining work is calibration, tenant policy controls, and production review behavior.

### Telegram Safety Escalation

Status: implemented v0; needs operational hardening.

Safety escalation records metadata-only risk evidence and avoids media preview or media storage by default. Remaining work is production provider workflow validation, retention, escalation policy configuration, and legal/ops review. See [TRUEPRESENCE_TELEGRAM_SAFETY.md](TRUEPRESENCE_TELEGRAM_SAFETY.md).

### Dashboard Evidence Cards

Status: implemented v0; needs production data validation.

Dashboard evidence cards distinguish Web SDK evaluations, Telegram evaluations, and safety escalations. They render likelihoods, confidence, reason codes, evidence IDs, decision IDs where available, recommended actions, and timestamps without displaying raw content. See [TRUEPRESENCE_DASHBOARD.md](TRUEPRESENCE_DASHBOARD.md).

## Strategic Rule

TruePresence should never need to know what a user typed in order to decide whether the interaction looked human.

The product wins by measuring interaction plausibility, not by collecting private content.
