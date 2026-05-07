# TruePresence Codebase Map

## Canonical runtime package path

- Canonical Python runtime package: `truepresence/`
- `pyproject.toml` declares package name `truepresence-ese`, console script `truepresence = "truepresence.main:main"`, and setuptools package discovery for `truepresence*`, `ese*`, and `ese_core*`.
- No active `truepresenceese/truepresenceese` package path was found. New SDK-core Python work belongs under `truepresence/`, not a legacy `truepresenceese/` path.

## Active API and FastAPI entry points

- `truepresence/main.py`
  - Top-level FastAPI app factory: `create_app()`
  - Runtime app: `app = create_app()`
  - Mounts `truepresence.api.server.app` at `/api`
  - Includes WebSocket, Telegram, and auth routers when wiring succeeds
  - Exposes `/health` and `/ready`
- `truepresence/api/server.py`
  - REST app for `/api/session/create`, `/api/v1/evaluate`, `/api/health`, SDK evaluation, SDK evidence cards, and session utility routes
  - SDK/web route: `/api/v1/truepresence/evaluate-interaction` through the top-level mount
  - SDK evidence artifact route: `/api/v1/truepresence/evidence/{evidence_packet_id}`
  - SDK dashboard evidence route: `/api/v1/truepresence/evidence/cards`
- `truepresence/api/ws_server.py`
  - WebSocket router for session streams
- `truepresence/api/auth.py`
  - Auth and admin-user router mounted at `/auth`
- `truepresence/adapters/telegram_bot.py`
  - Telegram router mounted at `/telegram`
  - Existing admin status, config, protected group, and review queue endpoints

## Active decision, evidence, and runtime modules

- Decision engine:
  - `truepresence/decision/engine.py`
  - `truepresence/decision/decision_object.py`
  - `truepresence/decision/synthesizer.py`
  - `truepresence/decision/tier_router.py`
  - `truepresence/decision/reason_codes.py`
- Evidence packet and argument graph:
  - `truepresence/evidence/packet.py`
  - `truepresence/evidence/packet_builder.py`
  - `truepresence/evidence/argument_graph.py`
  - `truepresence/evidence/claims.py`
- Runtime wiring:
  - `truepresence/runtime/wiring.py`
  - `truepresence/core/runtime.py`
  - `truepresence/runtime/distributed.py`
  - `truepresence/ese_runtime.py`

## SDK, scoring, and detector modules

- SDK contracts and privacy-safe features:
  - `truepresence/sdk/__init__.py`
  - `truepresence/sdk/contracts.py`
  - `truepresence/sdk/features.py`
  - `truepresence/sdk/privacy.py`
  - `truepresence/sdk/evaluation.py`
- Privacy-safe human plausibility detectors:
  - `truepresence/detectors/__init__.py`
  - `truepresence/detectors/human_plausibility.py`
  - `truepresence/detectors/typing_cadence.py`
  - `truepresence/detectors/reading_time.py`
  - `truepresence/detectors/agentic_control.py`
  - `truepresence/detectors/telegram_community.py`
- Deterministic v0 signal fusion:
  - `truepresence/scoring/__init__.py`
  - `truepresence/scoring/model.py`
  - `truepresence/scoring/weights.py`
- API route:
  - `truepresence/api/server.py` exposes `POST /v1/truepresence/evaluate-interaction`, `GET /v1/truepresence/evidence/{evidence_packet_id}`, and `GET /v1/truepresence/evidence/cards` through the top-level `/api` mount.

## Evidence, testing, challenge, and dashboard modules

- SDK evidence artifacts:
  - `truepresence/evidence/sdk_artifacts.py`
  - `docs/TRUEPRESENCE_EVIDENCE_ARTIFACTS.md`
- Evaluation harness:
  - `truepresence/testing/fixtures.py`
  - `truepresence/testing/scenarios.py`
  - `truepresence/testing/reporting.py`
  - `docs/TRUEPRESENCE_TESTING_HARNESS.md`
- Challenge framework modules:
  - `truepresence/challenges/engine.py`
  - `truepresence/challenges/orchestrator.py`
  - `truepresence/challenges/injector.py`
  - `truepresence/challenges/response.py`
  - `truepresence/challenges/scoring.py`
  - `truepresence/challenges/validator.py`
- Dashboard evidence cards:
  - `truepresence/ui/src/app/dashboard/page.tsx`
  - `truepresence/ui/src/app/dashboard/evaluation-card.tsx`
  - `truepresence/ui/src/app/api/dashboard/evidence/route.ts`
  - `docs/TRUEPRESENCE_DASHBOARD.md`

## Telegram community and safety modules

- Telegram community signals:
  - `truepresence/surfaces/telegram/community.py`
  - `truepresence/detectors/telegram_community.py`
  - `docs/TRUEPRESENCE_TELEGRAM_COMMUNITY_SIGNALS.md`
- Telegram safety escalation:
  - `truepresence/safety/policy.py`
  - `truepresence/safety/escalation.py`
  - `truepresence/safety/evidence_minimization.py`
  - `docs/TRUEPRESENCE_TELEGRAM_SAFETY.md`

## Browser JavaScript SDK

- Public browser SDK entry point:
  - `truepresence/sdk/index.js`
- Privacy and feature collectors:
  - `truepresence/sdk/privacy.js`
  - `truepresence/sdk/typing.js`
  - `truepresence/sdk/pointer.js`
  - `truepresence/sdk/challenge.js`
- Legacy-compatible privacy-safe event helpers:
  - `truepresence/sdk/keyboard.js`
  - `truepresence/sdk/mouse.js`
  - `truepresence/sdk/focus.js`
  - `truepresence/sdk/clipboard.js`
- Browser SDK docs and example:
  - `docs/TRUEPRESENCE_BROWSER_SDK.md`
  - `examples/browser-sdk/basic-form.html`
- Browser SDK tests:
  - `tests/browser-sdk/truepresence-browser-sdk.test.mjs`

## Legacy or transitional package paths discovered

- `truepresence/sdk/*.js`
  - Browser SDK JavaScript files live beside the Python SDK-core modules under the canonical `truepresence/sdk/` package path.
- `truepresence/surfaces/web_guard/sdk_protocol.py`
  - Existing web guard Pydantic protocol for browser events and decision envelopes. Phase 1 adds the SDK-first interaction evaluation path without replacing this transitional protocol.
- `truepresence/surfaces/telegram/` and `truepresence/adapters/telegram*`
  - Telegram remains one adapter surface, not the center of the SDK-core path.
- `ese/` and `ese_core/`
  - Included by setuptools for the broader ESE toolkit and CLI, but not the canonical TruePresence runtime package for this SDK work.

## Documentation link map

| Document | Role |
|---|---|
| [README](../README.md) | Product overview, quickstart, and repository structure |
| [Browser SDK](TRUEPRESENCE_BROWSER_SDK.md) | Browser SDK integration and API reference |
| [Privacy contract](TRUEPRESENCE_PRIVACY_PRESERVING_SDK_CONTRACT.md) | Privacy-safe feature, denylist, and response semantics |
| [Scoring model](TRUEPRESENCE_SCORING_MODEL.md) | Likelihood, confidence, category aggregation, and reason-code model |
| [SDK backlog](TRUEPRESENCE_SDK_IMPLEMENTATION_BACKLOG.md) | Completed v0 work and remaining roadmap backlog |
| [Roadmap](TRUEPRESENCE_ROADMAP.md) | Priority-ranked workstream table |
| [Dashboard evidence](TRUEPRESENCE_DASHBOARD.md) | Privacy-safe dashboard evidence-card behavior |
