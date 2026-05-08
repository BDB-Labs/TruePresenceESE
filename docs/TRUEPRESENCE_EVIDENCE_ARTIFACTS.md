# TruePresence SDK Evidence Artifacts

## Purpose

SDK and browser evaluations return an `evidence_packet_id`. That ID now maps to a retrievable SDK evidence artifact for audit, support, and product debugging.

The artifact is content-minimized. It records derived evaluation evidence and scoring outputs, not raw user content.

## Artifact Contents

SDK evidence artifacts include:

- `evidence_packet_id`;
- `session_id`;
- `tenant_id`;
- `surface`;
- `created_at`;
- feature summaries;
- detector signals;
- reason codes;
- likelihoods;
- confidence;
- recommended action;
- scoring metadata.

Feature summaries are the privacy-preserving SDK feature sections, such as typing cadence metrics, challenge timing, pointer aggregates, agentic-control aggregates, environment hints, and session-continuity aggregates.

## Privacy Boundary

Artifacts must not store:

- raw typed text;
- raw key values;
- passwords;
- payment data;
- private messages;
- raw pointer trails;
- media files or media previews.

Unsafe SDK payloads are rejected before scoring and before artifact storage. The privacy guard remains the authority for schema allowlist enforcement and raw-content rejection.

## Retrieval Semantics

SDK/web evidence artifacts can be retrieved with:

```text
GET /api/v1/truepresence/evidence/{evidence_packet_id}
```

The response includes derived metrics, detector-signal metadata, reason codes, likelihoods, confidence, recommended action, and scoring metadata. It does not echo raw submitted content.

Unknown artifact IDs return `404`.

## Production Persistence

SDK evidence artifacts use a storage abstraction with two implementations:

- `InMemorySdkEvidenceArtifactStore` for tests and local development.
- `PostgresSdkEvidenceArtifactStore` for durable runtime persistence.

Production deployments should run the Alembic migration that creates `sdk_evidence_artifacts`. The table stores one row per `evidence_packet_id` with tenant, session, surface, timestamp, minimized feature summaries, detector signals, reason codes, likelihoods, confidence, recommended action, and scoring metadata.

The runtime store selector uses the DB-backed store when database configuration is present outside test/development mode. Local tests can still use the in-memory store, and store-specific tests can inject a SQLite connection to verify persistence semantics without requiring production infrastructure.

The `TRUEPRESENCE_SDK_EVIDENCE_STORE` environment variable can force store selection:

- `postgres`, `db`, or `database` for DB-backed storage;
- `memory`, `in_memory`, or `test` for process-local storage.

`TRUEPRESENCE_SDK_EVIDENCE_AUTO_INIT=1` can initialize the DB schema from the store for simple deployments, but Alembic remains the preferred production migration path.

## Retention

Retention should be tenant-configurable. Default production retention should be short and aligned with the purpose of auditability, dispute handling, or operational troubleshooting. Artifacts should be deleted when they are no longer needed for those purposes.

The placeholder configuration value is `TRUEPRESENCE_SDK_EVIDENCE_RETENTION_DAYS`, with a default of 30 days. This change defines the policy hook but does not perform destructive cleanup automatically.
