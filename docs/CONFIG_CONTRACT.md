# ESE Config Contract (v1)

`ese.config.yaml` is schema-validated before doctor or pipeline execution.

## Top-level keys

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `version` | int | yes | Must be `1`. |
| `mode` | enum | yes | `ensemble` or `solo`. |
| `strict_config` | bool | no | When `true`, reject unknown top-level keys and unknown per-role keys outside `provider`, `model`, `temperature`, and `prompt`. |
| `provider` | object | yes | Global provider/model defaults. |
| `roles` | map | yes | Role-specific overrides. Must contain at least one configured role. |
| `role_order` | list[string] | no | Explicit execution order. Must contain every configured role exactly once. |
| `constraints` | object | no | Doctor/governance policy knobs. |
| `input` | object | no | Human scope and optional additional run context. |
| `output` | object | no | Artifact/output behavior flags. |
| `gating` | object | no | Pipeline failure gating preferences. |
| `runtime` | object | no | Adapter and runtime execution settings. |

## Input object

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `scope` | string | no | Recommended primary task/scope field. Required at execution time unless `--scope` is provided. |
| `prompt` | string | no | Supplemental run context. Used as additional run context, not duplicated again at the adapter layer. |

## Provider object

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | yes | Non-empty provider identifier such as `openai`, `local`, or `my-gateway`. |
| `model` | string | yes | Non-empty default model identifier. |
| `api_key_env` | string | no | Env var name used for auth token lookup. |
| `base_url` | string | no | Optional provider endpoint. Required for `runtime.adapter=custom_api` unless supplied at `runtime.custom_api.base_url`. |

## Role object

Allowed per-role keys in all modes:
- `provider`
- `model`
- `temperature`
- `prompt`

When `strict_config: true`, any other per-role key is rejected.

## Constraints object

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `disallow_same_model_pairs` | list[[string, string]] | no | Additional role pairs that must not resolve to the same model identity in ensemble mode. |
| `require_roles` | list[string] | no | Roles that must exist in the config. |
| `minimum_distinct_models` | int | no | Ensemble-only minimum number of distinct resolved role models. Must be `> 0`. |
| `minimum_specialist_roles` | int | no | Minimum count of configured non-architect/non-implementer roles. Must be `>= 0`. |
| `disallow_same_provider_pairs` | list[[string, string]] | no | Role pairs that must not resolve to the same provider identity in ensemble mode. |
| `require_json_for_roles` | list[string] | no | If any listed role is configured, `output.enforce_json` must be `true`. |

Baseline same-model separation is always enforced in ensemble mode for:
- `architect` / `implementer`
- `implementer` / `adversarial_reviewer`
- `implementer` / `security_auditor`
- `adversarial_reviewer` / `security_auditor`
- `implementer` / `release_manager`

## Runtime object

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `adapter` | string | no | Built-ins: `dry-run`, `openai`, `local`, `custom_api`; or `module:function`. |
| `timeout_seconds` | float | no | Must be `> 0`. |
| `max_retries` | int | no | Must be `>= 0`. |
| `retry_backoff_seconds` | float | no | Must be `> 0`. |
| `max_output_tokens` | int | no | Must be `> 0` when set. |
| `review_isolation` | enum | no | `framed`, `implementation_only`, `scope_only`, or `scope_and_implementation` (default). |
| `openai.base_url` | string | no | Optional OpenAI endpoint override. |
| `local.base_url` | string | no | Optional Ollama/OpenAI-compatible endpoint override. Defaults to `http://localhost:11434/v1`. |
| `local.use_openai_compat_auth` | bool | no | Sends `Bearer ollama` for clients/endpoints that expect OpenAI-style auth headers. Defaults to `true`. |
| `custom_api.base_url` | string | no | Optional custom API endpoint override. |

## Output object

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `artifacts_dir` | string | no | Non-empty directory used by `ese start` unless `--artifacts-dir` overrides it. |
| `enforce_json` | bool | no | When `true` (default), each role artifact must be valid JSON and uses a `.json` extension. |

## Gating object

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `fail_on_high` | bool | no | When `true` (default), pipeline execution stops on `HIGH` or `CRITICAL` findings. Requires `output.enforce_json=true`. |

## Adapter validation rules

When `runtime.adapter=openai`:
- `provider.name` must be `openai`
- all role providers must resolve to `openai`

When `runtime.adapter=local`:
- `provider.name` must be `local`
- all role providers must resolve to `local`
- ESE expects an Ollama-compatible endpoint

When `runtime.adapter=custom_api`:
- `provider.name` must not be `openai`
- `provider.api_key_env` is required
- one of `provider.base_url` or `runtime.custom_api.base_url` is required
- all role providers must resolve to the configured provider name

## Solo and degraded assurance semantics

`mode: solo` remains valid, but its artifacts and reports are marked with `assurance_level: degraded`.
Degraded assurance runs should not be treated as equivalent release evidence to full ensemble runs.

## Validation behavior

Validation is performed by `ese.config.validate_config`.
Doctor policy is then enforced by `ese doctor` and by all execution entry points:
- `ese start`
- `ese task`
- `ese pr`
- `ese rerun`

Violations fail with exit code `2`.
