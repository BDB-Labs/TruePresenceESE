# Pipeline State Contract

After `ese start`, `ese task`, `ese pr`, or `ese rerun`, ESE writes:
- `ese_summary.md`
- `pipeline_state.json`
- `ese_config.snapshot.yaml`

## Deterministic role ordering

Execution order is deterministic:
1. If `role_order` is configured, ESE uses it exactly.
2. Otherwise, built-in roles follow the fixed ESE order when present.
3. Custom roles run after built-ins in their declared order.

## Review isolation contract

`runtime.review_isolation` controls upstream context exposure:
- `architect` receives no upstream role context
- `implementer` receives only `architect`
- specialist roles receive:
  - `framed`: `architect` + `implementer`
  - `implementation_only`: `implementer`
  - `scope_only`: no upstream role context
  - `scope_and_implementation`: `implementer`
- fallback/custom roles do not receive `architect` by default unless `framed` is selected

Prompts render explicit sections:
- `Scope`
- `Additional Run Context`
- upstream sections such as `Architect Plan`, `Implementer Output`, or `Upstream Artifact (...)`
- `Operator Feedback`

Prompt blocks are truncated with `[...truncated for size...]` when needed for size safety.

## Role artifact contract

When `output.enforce_json=true`, role artifacts use the `.json` extension and must satisfy the role report contract documented in `docs/ROLE_REPORT_CONTRACT.md`.

## `pipeline_state.json` schema

```json
{
  "run_id": "9e2c2f0f7cf1476a9b0de9fb90fbbf2a",
  "status": "completed",
  "assurance_level": "standard",
  "mode": "ensemble",
  "provider": "openai",
  "adapter": "dry-run",
  "scope": "...",
  "config_snapshot": "artifacts/ese_config.snapshot.yaml",
  "state_contract_version": 2,
  "report_contract_version": 2,
  "parent_run_id": "optional-parent-run-id",
  "start_role": "implementer",
  "failed_roles": ["optional", "failed", "roles"],
  "role_models": {
    "architect": "openai:gpt-5",
    "implementer": "openai:gpt-5-mini"
  },
  "artifacts": {
    "architect": "artifacts/01_architect.json",
    "implementer": "artifacts/02_implementer.json"
  },
  "execution": [
    {
      "role": "architect",
      "model": "openai:gpt-5",
      "artifact": "artifacts/01_architect.json",
      "strategy": "serial",
      "started_at": "2026-03-27T12:00:00Z",
      "completed_at": "2026-03-27T12:00:02Z",
      "duration_ms": 2048
    }
  ]
}
```

## Lineage semantics

- `run_id` is unique per pipeline invocation
- `assurance_level` is:
  - `standard` for ensemble runs
  - `degraded` for solo runs
- `parent_run_id` is set when a rerun resumes from prior state
- `start_role` is set when rerunning from a specific role
- seeded upstream execution entries are preserved with `strategy: "seeded"`

## Partial failure support

If a parallel specialist batch partially succeeds and partially fails:
- completed artifacts remain on disk
- `pipeline_state.json` is still written
- `status` becomes `failed`
- `failure` describes the batch failure
- `failed_roles` lists the roles that failed

Reports should remain readable from that saved partial state.

## Stability guarantees

For state/report contract version `2`:
- top-level lineage and assurance keys shown above are stable
- execution ordering rules are stable
- review isolation semantics are stable
- partial-failure persistence is stable
