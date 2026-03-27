# Role Report Contract

When `output.enforce_json=true`, every role artifact must be a JSON object.

## Required top-level fields

| Field | Type | Notes |
| --- | --- | --- |
| `summary` | string | Concise role-level conclusion. Must be non-empty. |
| `confidence` | enum | Required. One of `LOW`, `MEDIUM`, `HIGH`. |
| `assumptions` | list[string] | Required. Explicit assumptions the role relied on. |
| `unknowns` | list[string] | Required. Explicit uncertainties, missing evidence, or open questions. |
| `findings` | list[object] | Required. May be empty. |
| `artifacts` | list[string] | Required. Concrete deliverables produced or recommended. |
| `next_steps` | list[string] | Required. Pragmatic follow-up actions. |
| `code_suggestions` | list[object] | Required. Concrete programmer-facing edits or tests. |

## Optional fields

| Field | Type | Notes |
| --- | --- | --- |
| `evidence_basis` | list[string] | Optional references to concrete evidence such as diffs, tests, logs, configs, or docs used by the role. |

## Finding object

Each finding must include:
- `severity`: `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`
- `title`: non-empty string
- `details`: string

Severity is about impact/urgency, not model certainty.

## Confidence semantics

- `HIGH`: the role had direct evidence and low ambiguity
- `MEDIUM`: the role had enough evidence to make a useful judgment, but some ambiguity remains
- `LOW`: the role is flagging possible risk with limited evidence or significant uncertainty

`confidence` is required so downstream reports can distinguish strong blockers from lower-certainty blockers.

## Assumptions and unknowns

- `assumptions` should capture explicit premises the analysis depends on
- `unknowns` should capture missing evidence, unresolved questions, or scope gaps
- use empty arrays when there are none

Recurring unknowns across multiple roles are aggregated in the run report.

## Code suggestions

Each `code_suggestions` item may include:
- `path`
- `kind`
- `summary`
- `suggestion`
- `snippet`

Use `code_suggestions` for concrete edits, tests, refactors, config changes, or short patch-style snippets.

## Versioning expectations

Role reports participate in the pipeline `report_contract_version`.
Current stable contract version is `2`.
Breaking changes to required fields or semantics must increment the report contract version and be documented in release notes and `docs/PIPELINE_STATE.md`.
