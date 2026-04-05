# Release Governance Starter

Starter vertical repository for release-governance workflows built on top of ESE.

It contributes:

- a release-governance config pack
- a rollout-safety policy check
- a go-live artifact view
- a release-evidence integration

## Install

```bash
pip install -e ./starters/release_governance_starter
```

## Use

```bash
ese packs
ese policies
ese views
ese integrations
```

Generate a portable starter config:

```bash
ese task "Review the staged rollout plan for billing cutover" \
  --template release-readiness \
  --execution-mode demo \
  --artifacts-dir artifacts
```

Publish release evidence:

```bash
ese publish \
  --integration release-governance-bundle \
  --artifacts-dir artifacts \
  --target ./release-evidence
```
