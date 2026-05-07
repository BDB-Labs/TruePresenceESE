# TruePresence Roadmap

## Purpose

This roadmap is the status table for current TruePresence SDK, scoring, evidence, Telegram, safety, and dashboard workstreams. It is intentionally conservative: items are marked as implemented v0, needs hardening, planned, or not yet implemented.

## Link Map

| Document | Role |
|---|---|
| [README](../README.md) | Product overview and quickstart |
| [Browser SDK](TRUEPRESENCE_BROWSER_SDK.md) | Browser SDK integration guide |
| [Privacy contract](TRUEPRESENCE_PRIVACY_PRESERVING_SDK_CONTRACT.md) | Privacy-safe feature and API contract |
| [Codebase map](TRUEPRESENCE_CODEBASE_MAP.md) | Canonical paths and active modules |
| [Scoring model](TRUEPRESENCE_SCORING_MODEL.md) | Likelihood, confidence, and reason-code scoring |
| [SDK backlog](TRUEPRESENCE_SDK_IMPLEMENTATION_BACKLOG.md) | Detailed workstream status and acceptance notes |
| [Dashboard evidence](TRUEPRESENCE_DASHBOARD.md) | Privacy-safe dashboard evidence display |

## Roadmap Table

| Workstream | Status | Priority | Branch name | Notes |
|---|---|---|---|---|
| SDK contracts | Implemented v0 | P0 | `feature/sdk-core-contracts` | Current contracts include privacy-safe request models and probabilistic response fields. Keep schema changes backward-aware. |
| Privacy-preserving feature model v0 | Implemented v0; needs hardening | P0 | `feature/privacy-allowlist-hardening` | Continue expanding allowlist and denylist tests for renamed content fields, nested metadata, and future feature sections. |
| Backend evaluation endpoint | Implemented v0 | P0 | `feature/web-sdk-evaluate-endpoint` | `/api/v1/truepresence/evaluate-interaction` is active through the mounted API. Remaining work is operational monitoring and versioning. |
| Browser JavaScript SDK | Implemented v0 | P0 | `feature/browser-js-sdk` | Current SDK collects derived metrics and excludes raw content by default. Remaining work is packaging, versioning, and field coverage. |
| Human plausibility detectors | Implemented v0 | P0 | `feature/human-plausibility-detectors` | Current detectors emit reason codes and weak-signal contributions. Continue calibration against more human-like and edge-case fixtures. |
| Calibrated scoring model | Implemented v0 | P0 | `feature/scoring-model` | Deterministic probabilistic scoring is active. Future work is trained or telemetry-backed calibration after a larger corpus exists. |
| README product positioning | Implemented v0 | P0 | `docs/product-positioning` | README now frames TruePresence as a privacy-preserving interaction authenticity SDK. |
| Agentic-control detectors | Implemented v0; needs hardening | P1 | `feature/agentic-control-detectors` | Separate agentic-control channel exists. Needs production threshold tuning, more browser-agent traces, and false-positive analysis. |
| Evidence artifact linkage | Implemented v0; needs durable linkage | P1 | `feature/evidence-artifact-linkage` | SDK evidence artifacts map from `evidence_packet_id`, but the default store is process-local. Needs durable tenant-scoped persistence and retention controls. |
| Testing harness | Implemented v0; needs broader coverage | P1 | `feature/evaluation-harness` | Fixture and scenario runner exist. Needs broader surfaces, dashboard payload checks, and reporting for false positive/negative behavior. |
| Challenge framework | Implemented v0 modules; API/UI incomplete | P1 | `feature/challenge-framework` | Challenge modules exist, but SDK-facing start/complete routes and dashboard observability are not complete. |
| Telegram community signals | Implemented v0; needs production hardening | P1 | `feature/telegram-community-signals` | Metadata-only signals exist. Needs calibration, tenant policy tuning, and ongoing no-content evidence review. |
| Telegram safety escalation | Implemented v0; needs operational hardening | P1 | `feature/telegram-safety-escalation` | Metadata-only safety cards exist. Needs lawful-provider workflow validation, retention, and escalation policy review. |
| Dashboard evidence cards | Implemented v0; needs production data validation | P1 | `feature/dashboard-evidence-cards` | Dashboard distinguishes Web SDK, Telegram, and safety cards without raw content display. Needs validation against real tenant data and durable SDK artifacts. |
| Risk provider connectors | Planned; not yet implemented as provider connectors | P2 | `feature/risk-provider-connectors` | General provider connector package is not present yet. Provider scores must enter evidence without bypassing TruePresence scoring. |

## Priority Definitions

| Priority | Meaning |
|---|---|
| P0 | Required to preserve the SDK privacy contract and core product claims. |
| P1 | Needed for production readiness, calibration, and operator trust. |
| P2 | Integration expansion after the core SDK, evidence, and dashboard surfaces are stable. |

## Status Definitions

| Status | Meaning |
|---|---|
| Implemented v0 | Exists in code/docs/tests as a first-pass implementation, but may still need hardening. |
| Needs hardening | Functional baseline exists; remaining work is calibration, coverage, operationalization, or policy refinement. |
| Planned | Product direction is known, but implementation has not started or is only represented by data-shape placeholders. |
| Not yet implemented | No active product implementation exists in the canonical runtime path. |
