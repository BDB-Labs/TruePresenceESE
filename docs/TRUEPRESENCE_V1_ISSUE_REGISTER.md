# TruePresence V1 Issue Register

This register is the current observed issue list from the end-to-end wiring
analysis. It covers findings from optional cleanup through production blockers.
It is not a formal guarantee that no additional defects exist; live Telegram,
database-backed, WebSocket, browser, and load tests can add new entries.

## Severity Legend

- P0 Production blocking: prevents a production launch or can make production
  report success while a core path is broken.
- P1 High: serious correctness, security, durability, or load risk.
- P2 Medium: important gap with bounded blast radius or workaround.
- P3 Low: maintainability, clarity, or operational polish.
- P4 Optional: nice-to-have or roadmap-level improvement.

## Fixed In Current Pass

| ID | Severity | Area | Issue | Evidence | Remediation |
|----|----------|------|-------|----------|-------------|
| V1-P0-001 | P0 | Web Guard API | `/api/v1/evaluate` rejected the engine response because `reasoning_trace` allowed only string values while the engine emits `reason_codes` as a list. | `truepresence/api/server.py`, `truepresence/decision/engine.py` | Widened API contract and added regression coverage. |
| V1-P0-002 | P0 | Runtime state | Redis fallback failed when the Redis package existed but Redis was unavailable because `_memory_store` was not initialized. | `truepresence/runtime/distributed.py` | Initialized memory fallback consistently and added regression coverage. |
| V1-P0-003 | P0 | Deployment | Docker exec-form command passed literal `${PORT:-8000}` to Uvicorn. | `deploy/Dockerfile` | Switched to shell command with runtime port expansion. |
| V1-P0-004 | P0 | Readiness | Deployment health could pass while required dependencies were broken. | `truepresence/main.py`, `deploy/Dockerfile` | Added `/ready` and pointed container health checks at it. |
| V1-P0-005 | P0 | Docs/Ops | Deployment docs omitted required production env vars. | `deploy/README.md`, `docs/TRUEPRESENCE_STARTUP.md` | Updated production env and verification guidance. |

## Open Production Blockers

| ID | Severity | Area | Issue | Evidence | Remediation |
|----|----------|------|-------|----------|-------------|
| V1-P0-006 | P0 | Product scope | TruePresence V1 expectations are not yet frozen against a product narrative. ESE 1.0 readiness and TruePresence product readiness are currently easy to confuse. | `MILESTONE_1_0_0.md`, `docs/TRUEPRESENCE_V1_ARCHITECTURE.md` | Write and approve a V1 launch narrative/checklist for surfaces, tenants, enforcement, audit, and SLOs. |
| V1-P0-007 | P0 | CI/deploy | Render deploy workflows run Node commands at repo root for a Python backend and are duplicated with a misspelled file. | `.github/workflows/render-deploy.yml`, `.github/workflows/render-depoly.yml` | Replace with a Python backend deploy workflow or disable until configured. |

## Open High-Severity Issues

| ID | Severity | Area | Issue | Evidence | Remediation |
|----|----------|------|-------|----------|-------------|
| V1-P1-001 | P1 | Telegram security | Webhook authenticity is optional. If no webhook secret is set, requests are accepted. | `truepresence/adapters/telegram_bot.py` | Require webhook secret in production and bind tenant identity to the verified webhook route/token. |
| V1-P1-002 | P1 | Telegram execution | Webhook responses omit execution outcome, so moderation failures can appear successful. | `truepresence/adapters/telegram_bot.py` | Include execution status in responses/logs and expose failed execution metrics. |
| V1-P1-003 | P1 | Telegram load | Synchronous DB calls run inside async webhook processing. | `truepresence/adapters/telegram_bot.py` | Move DB operations to `asyncio.to_thread` or an async DB client, then load test. |
| V1-P1-004 | P1 | Telegram durability | Moderation execution has no idempotent outbox/retry model. | `docs/telegram_production_readiness_assessment.md` | Persist action intents with idempotency keys and retry state before calling Telegram. |
| V1-P1-005 | P1 | WebSocket scaling | WebSocket connections, events, modes, and challenge cooldowns are process-local. | `truepresence/api/ws_server.py` | Move shared session/challenge state to Redis or formally make WebSocket single-replica. |
| V1-P1-006 | P1 | WebSocket security | JWT is passed in the query string, increasing leakage through logs and URLs. | `truepresence/api/ws_server.py` | Prefer cookie/subprotocol/header-based auth where supported, and sanitize logs. |
| V1-P1-007 | P1 | Config durability | Detector config updates only affect the running process. | `truepresence/adapters/telegram_bot.py` | Persist config per tenant and reload consistently across replicas. |
| V1-P1-008 | P1 | Token storage | Bot token decrypt failure falls back to stored plaintext, which can silently use ciphertext as a token. | `truepresence/adapters/telegram_bot.py` | Make legacy plaintext migration explicit and fail closed for encrypted-looking values. |
| V1-P1-009 | P1 | Observability | Health surfaces do not yet expose enough dependency, webhook, queue, and enforcement metrics for operations. | `truepresence/main.py`, `truepresence/adapters/telegram_bot.py` | Add metrics and structured logs for latency, parse failures, decisions, and Telegram outcomes. |

## Open Medium-Severity Issues

| ID | Severity | Area | Issue | Evidence | Remediation |
|----|----------|------|-------|----------|-------------|
| V1-P2-001 | P2 | Telegram enforcement | Ban cooldown lookup uses `tenant:user`, but writes use only `user_id`, so repeated bans are not rate-limited. | `truepresence/adapters/telegram.py` | Use one tenant-scoped key format and add tests for repeat actions. |
| V1-P2-002 | P2 | Telegram maintainability | `build_response` contains unreachable duplicate logic after an unconditional return. | `truepresence/adapters/telegram.py` | Remove dead code after cooldown fix. |
| V1-P2-003 | P2 | Telegram feature completeness | Group member scan endpoint is a placeholder. | `truepresence/adapters/telegram_bot.py` | Implement, hide behind feature flag, or remove from V1. |
| V1-P2-004 | P2 | Telegram feature completeness | Full group audit endpoint returns `audit_queued` without queue/work execution. | `truepresence/adapters/telegram_bot.py` | Implement worker-backed audit or remove from V1. |
| V1-P2-005 | P2 | Browser/admin wiring | CORS does not allow tenant/admin headers for direct browser calls. | `truepresence/main.py` | Add required headers or keep all browser admin traffic behind Next.js proxy. |
| V1-P2-006 | P2 | Dashboard accuracy | Main dashboard status cards are static. | `truepresence/ui/src/app/dashboard/page.tsx` | Wire cards to backend health/review/tenant data. |
| V1-P2-007 | P2 | UI config | Dashboard API proxy silently defaults to production URL when env is missing. | `truepresence/ui/src/app/api/_lib/backend.ts` | Require explicit backend URL outside production or show config error. |
| V1-P2-008 | P2 | Load readiness | No load tests cover REST evaluate, Telegram webhook, WebSocket, DB pool pressure, Redis outage, or Telegram API failure. | Test inventory | Add focused load/soak tests before external launch. |

## Open Low And Optional Issues

| ID | Severity | Area | Issue | Evidence | Remediation |
|----|----------|------|-------|----------|-------------|
| V1-P3-001 | P3 | Error clarity | Missing `JWT_SECRET` can surface as router wiring failure instead of a clear startup config error. | `truepresence/main.py`, `truepresence/api/auth.py` | Add startup config validation with explicit messages. |
| V1-P3-002 | P3 | API health | `/api/health` checks orchestrator status but not database dependencies. | `truepresence/api/server.py` | Either scope name as runtime health or add dependency checks. |
| V1-P3-003 | P3 | Versioning | Telegram health reports static version metadata. | `truepresence/adapters/telegram_bot.py` | Pull version from package metadata or build env. |
| V1-P3-004 | P3 | State semantics | Redis fallback is useful for local mode but should be explicit in production policy. | `truepresence/runtime/distributed.py` | Decide whether production without Redis is supported. |
| V1-P4-001 | P4 | Product UX | Admin review queue should show richer explanation cards and rollback controls. | Product roadmap | Add after core correctness/security gates. |
| V1-P4-002 | P4 | Operations UX | Tenant playbooks, canary policy mode, and policy-tuning assistant are not implemented. | Product roadmap | Treat as post-V1 unless explicitly required. |

## Recommended Fix Order

1. Close all P0 issues, including workflow cleanup and V1 launch narrative.
2. Harden Telegram webhook security, execution reporting, idempotency, and DB behavior.
3. Decide WebSocket scale boundary and move shared state if multi-replica is required.
4. Persist tenant config and moderation audit artifacts.
5. Add load, soak, and browser E2E checks.
6. Remove or implement placeholder V1 endpoints.
7. Improve dashboard accuracy and operations UX.
