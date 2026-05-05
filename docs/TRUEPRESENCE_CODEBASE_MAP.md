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
  - Existing REST app for `/api/session/create`, `/api/v1/evaluate`, `/api/health`, and session utility routes
  - New SDK/web route: `/api/v1/truepresence/evaluate-interaction` through the top-level mount
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

## New SDK code added in this phase

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
- Deterministic v0 signal fusion:
  - `truepresence/scoring/__init__.py`
  - `truepresence/scoring/model.py`
  - `truepresence/scoring/weights.py`
- API route:
  - `truepresence/api/server.py` adds `POST /v1/truepresence/evaluate-interaction`, exposed as `/api/v1/truepresence/evaluate-interaction` by `truepresence/main.py`.

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
