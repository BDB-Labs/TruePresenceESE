# ESE Extensibility

ESE should remain the orchestration substrate, not the vertical application.

## Core boundary

The `ese` package owns:

- role sequencing and parallel execution
- runtime and provider abstraction
- run artifacts, reruns, and summaries
- reporting and dashboard views
- framework-oriented setup and templates

External application repositories should own:

- domain-specific role catalogs
- domain prompts and schemas
- domain ingestion, persistence, and UI
- pack-specific evaluation datasets

## Config packs

Packs are discovered through the Python entry point group `ese.config_packs`.

Each entry point should load to either:

- a single `ConfigPackDefinition`
- a mapping shaped like `ConfigPackDefinition`
- an iterable of either of the above

Each pack exposes:

- `key`
- `title`
- `summary`
- `preset`
- `goal_profile`
- `roles`

Each role exposes:

- `key`
- `responsibility`
- `prompt`
- optional `temperature`

## Packaging example

```toml
[project.entry-points."ese.config_packs"]
release_ops = "my_product.packs:release_ops_pack"
```

## Operating model

- Keep ESE releaseable with zero external packs installed.
- Treat packs as additive integrations, not core dependencies.
- Put domain tests in the domain repository, not in ESE core.
- Keep the pack contract stable so vertical repos can upgrade ESE without forking it.
