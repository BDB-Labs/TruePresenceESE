# Architecture Review Starter

Starter vertical repository for architecture-review and migration-decision workflows built on top of ESE.

It contributes:

- an architecture-review config pack
- an architecture-scope policy check
- a decision brief artifact view
- a risk-register CSV exporter

## Install

```bash
pip install -e ./starters/architecture_review_starter
```

## Use

```bash
ese packs
ese policies
ese views
ese exporters
```

Run an architecture review workflow:

```bash
ese task "Review the service-boundary changes for the billing migration" \
  --template architecture-deep-dive \
  --execution-mode demo \
  --artifacts-dir artifacts
```
