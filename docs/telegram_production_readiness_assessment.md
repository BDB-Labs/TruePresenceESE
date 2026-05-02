# Telegram Bot Production Readiness & Ops/Admin Interactivity Assessment

Date: 2026-04-18
Scope: `truepresence/adapters/telegram.py`, `truepresence/adapters/telegram_bot.py`, `truepresence/surfaces/telegram/adapter.py`

## Executive verdict

**Current readiness: NOT production-ready (high risk).**

The implementation has a promising architecture (event parsing -> decision engine -> enforcement, plus manual review pathways), but correctness, security, tenancy, and operational durability gaps remain.

## Readiness scorecard

- **Reliability:** 4/10
- **Security & abuse resistance:** 3/10
- **Observability & operations:** 4/10
- **Admin interactivity UX:** 5/10
- **Scalability:** 4/10
- **Maintainability:** 5/10

## Complete issue register (all severities)

### Critical (P0)

1. **Undefined variable crash in primary message path**
   - `message_velocity` is referenced but never computed in `_parse_message`.
   - Impact: parsing fails for message updates and is wrapped into `EvidenceError`.
   - Evidence: `truepresence/adapters/telegram.py` lines 247 and 252.

2. **Unsafe admin surface (missing AuthN/AuthZ)**
   - Admin/config/review endpoints are callable without authentication/authorization.
   - Impact: unauthorized moderation and policy manipulation.
   - Evidence: explicit TODO in config endpoint (`truepresence/adapters/telegram_bot.py` lines 643-645), plus exposed review/config/group endpoints.

3. **Tenant trust boundary bypass**
   - Tenant routing is derived from untrusted `X-Tenant-ID` header with no signature or token binding.
   - Impact: tenant spoofing and cross-tenant action risk.
   - Evidence: `truepresence/adapters/telegram_bot.py` line 495.

### High (P1)

4. **Review lifecycle inconsistency from ephemeral service instances**
   - `/resolve`, `/execute`, and `/config` instantiate new `TelegramProtectionService` per request.
   - Impact: in-memory review state is not shared; resolve/execute flows can fail unexpectedly.
   - Evidence: `truepresence/adapters/telegram_bot.py` lines 572, 598, 628.

5. **In-memory-only persistence for operationally critical state**
   - Reviews, sessions, protected groups, and admin chats are kept in process memory.
   - Impact: restart causes state loss and weak audit continuity.
   - Evidence: `truepresence/adapters/telegram_bot.py` lines 63-67, 253-273.

6. **Multi-tenant configuration leakage risk in singleton flow**
   - Module-level `service` is initialized once with default tenant config; `process_update` can be called for other tenants while retaining adapter config loaded at startup.
   - Impact: wrong detector configuration may be applied to non-default tenants.
   - Evidence: singleton service (`line 474`), adapter built in constructor (`line 59`), tenant arg in `process_update` (`line 127`).

7. **No webhook authenticity verification**
   - No verification of Telegram secret token/signature on webhook requests.
   - Impact: forged webhook events.
   - Evidence: webhook endpoint processes JSON directly without token validation (`truepresence/adapters/telegram_bot.py` lines 489-500).

8. **Potential HTML formatting injection in admin notifications**
   - Notification uses `parse_mode: HTML` while including user-controlled text/fields without escaping.
   - Impact: malformed notification content or formatting abuse.
   - Evidence: `truepresence/adapters/telegram_bot.py` lines 447-459.

### Medium (P2)

9. **`message_text` appended twice to recent-message buffer**
   - `_parse_message` appends the same text two times.
   - Impact: skewed similarity behavior and noisy signal quality.
   - Evidence: `truepresence/adapters/telegram.py` lines 218 and 222.

10. **Duplicate `return` statement**
    - `_analyze_content` has duplicate `return results`.
    - Impact: dead code smell, maintainability issue.
    - Evidence: `truepresence/adapters/telegram.py` lines 321 and 323.

11. **Ban cooldown not tenant-aware/distributed**
    - `_ban_actions` is a process-local global keyed by user id only.
    - Impact: inconsistent moderation across replicas and tenants.
    - Evidence: `truepresence/adapters/telegram.py` lines 21, 467-491.

12. **Rate limiting path is effectively inactive in current enforcement wiring**
    - `build_response` accepts `user_id`, but guard adapter `enforce()` does not pass it.
    - Impact: intended cooldown behavior is not applied for most decisions.
    - Evidence: `truepresence/surfaces/telegram/adapter.py` lines 42-53; `truepresence/adapters/telegram.py` lines 450-477.

13. **No explicit HTTP timeouts/retry policy for Telegram API calls**
    - Async client is created without explicit timeout/retry strategy.
    - Impact: possible hanging calls and brittle network handling.
    - Evidence: `truepresence/adapters/telegram_bot.py` line 70; API calls at lines 361 and 462.

14. **No client shutdown lifecycle**
    - `httpx.AsyncClient()` is never closed.
    - Impact: resource leak in long-running service.
    - Evidence: client creation in constructor (`line 70`) without shutdown hook.

15. **`protect_group` endpoint ignores tenant header**
    - Endpoint calls `service.register_group(...)` without tenant parameter.
    - Impact: registrations can silently land in default tenant scope.
    - Evidence: `truepresence/adapters/telegram_bot.py` lines 533-536.

16. **Review extraction tied mostly to `message` update shape**
    - Manual review payload extraction uses `update.get("message", {})` only.
    - Impact: incomplete context for edited messages or non-message review-trigger events.
    - Evidence: `truepresence/adapters/telegram_bot.py` lines 402-408.

### Low (P3)

17. **Import-time logging configuration side effect**
    - `logging.basicConfig(...)` executes at import.
    - Impact: can unexpectedly override host app logging behavior.
    - Evidence: `truepresence/adapters/telegram_bot.py` lines 31-35.

18. **Unused/shared orchestrator not meaningfully used for logic decisions**
    - `orchestrator` appears primarily for status metadata.
    - Impact: cognitive overhead and unclear ownership boundaries.
    - Evidence: assignment at line 54; status references at lines 223-224.

19. **Heuristic account-age mapping is coarse and undocumented for calibration cadence**
    - Uses fixed ID-range buckets.
    - Impact: weak precision over time.
    - Evidence: `truepresence/adapters/telegram.py` lines 371-397.

20. **Hardcoded health version value**
    - Health endpoint returns static `truepresence_version: "1.0.0"`.
    - Impact: operational ambiguity when deployed version differs.
    - Evidence: `truepresence/adapters/telegram_bot.py` lines 722-725.

### Informational (P4)

21. **Good architectural separation exists**
    - Parsing, decision engine evaluation, and response adaptation are separated.
    - Evidence: `truepresence/surfaces/telegram/adapter.py` lines 19-53.

22. **Manual-review queue and admin notification concept is present**
    - Review creation and notification fan-out are implemented.
    - Evidence: `truepresence/adapters/telegram_bot.py` lines 392-420 and 425-467.

23. **Tenant-specific detector configuration scaffolding is present**
    - Environment-driven detector and threshold loading is implemented.
    - Evidence: `truepresence/adapters/telegram_bot.py` lines 76-125.

## Production hardening plan

### Phase 1: Correctness and tenancy safety (1–3 days)
- Fix `message_velocity` computation and use.
- Remove duplicate append and duplicate return.
- Introduce tenant service registry (shared state per tenant) and stop creating ephemeral per-request services.
- Ensure all tenant-scoped endpoints pass/validate tenant explicitly.

### Phase 2: Security and persistence (3–7 days)
- Implement admin AuthN/AuthZ for all control endpoints.
- Verify webhook authenticity (Telegram secret token + optional source checks).
- Move reviews/sessions/groups/config/actions into durable store.
- Escape/sanitize admin notification content when using HTML parse mode.

### Phase 3: Operations and resilience (1–2 weeks)
- Add structured logging + correlation IDs.
- Add metrics: parse failures, decision latency, review queue age, enforcement success/failures, per-tenant volumes.
- Configure explicit HTTP timeouts + retries with backoff/circuit breaking.
- Add startup/shutdown hooks (`http_client.aclose()`), dependency-aware readiness checks.

## Innovative operations/admin interactivity roadmap

1. **Explainable Review Inbox**
   - Card view per incident: matched patterns, confidence composition, model/policy provenance.

2. **Reversible moderation controls**
   - One-tap actions: warn/kick/ban/delete with TTL presets and rollback controls.

3. **Policy-tuning copilot**
   - Suggest threshold/pattern updates based on moderator feedback loops and false-positive hotspots.

4. **Canary moderation mode**
   - Side-by-side comparison of current vs candidate policy on live traffic with divergence dashboard.

5. **Tenant playbooks**
   - Opinionated presets for common abuse profiles (scam-heavy, piracy-heavy, raid defense).

6. **Ops command center**
   - Queue SLA timers, reviewer workload balancing, escalation routing, and incident drill-down.

## Minimum release gates

- All P0/P1 issues remediated.
- Authenticated and authorized admin/control API surface.
- Durable state for review lifecycle and moderation actions.
- End-to-end tests for tenant isolation, webhook authenticity, review resolve/execute lifecycle.
- SLOs + dashboards in place before external rollout.

## Remaining unfinished issues (after recent code hardening)

The following items are still open and should be treated as next-wave work:

1. **No durable persistence for moderation state**
   - `pending_reviews`, sessions, and group/admin mappings remain in memory only.
   - Risk: restart/data-loss and weak audit continuity.

2. **Tenant identity still header-driven**
   - `X-Tenant-ID` is still accepted from request headers; webhook secret helps but tenant identity itself is not cryptographically bound to source.
   - Risk: tenant-routing ambiguity, especially in shared-secret deployments.

3. **Admin auth is coarse-grained shared token**
   - Current control-plane auth is simple token matching, without role scopes, per-endpoint permissions, rotation policy, or audit identity.
   - Risk: operational/security limitations for production governance.

4. **No distributed/idempotent moderation execution controls**
   - Actions are executed directly against Telegram API without explicit idempotency keys or outbox/retry orchestration.
   - Risk: duplicate or missed actions under retries/failures.

5. **No durable config-write path**
   - `/config/detectors` still returns “would be saved” and does not persist detector configuration.
   - Risk: runtime drift and non-repeatable operations.

6. **Global/process-local ban cooldown remains**
   - `_ban_actions` is now tenant-keyed, but still process-local and non-distributed.
   - Risk: inconsistent enforcement across replicas.

7. **Webhook and outbound robustness gaps**
   - Timeout and lightweight retries are configured, but there is still no circuit-breaker/outbox delivery model.
   - Risk: degraded behavior during transient upstream failures.

8. **Review payload extraction path is narrow**
   - Manual-review extraction now supports `message` and `edited_message`, but not broader Telegram update variants.
   - Risk: incomplete context for non-message variants.

9. **Lifecycle API style warning**
   - Shutdown uses `@router.on_event("shutdown")`, which is deprecated in FastAPI in favor of lifespan handlers.
   - Risk: future compatibility debt.

10. **Operational metadata gaps**
    - Health endpoint version can be environment-driven, but there is still no dependency-aware readiness probe.
    - Risk: weaker production observability/diagnostics.
