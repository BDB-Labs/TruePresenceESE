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

## Persistence Caveat

This first pass uses a storage abstraction with a process-local in-memory implementation. It is suitable for tests and local/non-DB deployments, but it is not durable across process restarts.

Production persistence should replace the in-memory store with a durable backend, such as a database table or evidence-artifact object store, while preserving the same content-minimized schema and retention controls.

## Retention

Retention should be tenant-configurable. Default production retention should be short and aligned with the purpose of auditability, dispute handling, or operational troubleshooting. Artifacts should be deleted when they are no longer needed for those purposes.
