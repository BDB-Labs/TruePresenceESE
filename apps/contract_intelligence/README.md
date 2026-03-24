# Contract Intelligence Pilot

This directory contains the starter scaffold for a domain-specific application
layer built on top of ESE.

The goal is to validate a reusable case-intelligence platform using a first
vertical pack: construction contract management, evaluation, and tracking.

## Current scope

The first slice is a `bid_review` workflow that turns a contract package into:

- document inventory
- contractor-side risk findings
- insurance anomalies
- funding and compliance findings
- decision summary
- obligations preview
- adversarial review challenges

## Folder map

- `domain/`: shared pilot models and enums
- `ingestion/`: early document typing and intake helpers
- `orchestration/`: role catalog, pipeline definition, and prompts
- `schemas/`: JSON schema contracts for stable artifacts
- `api/`: placeholder API surface for the future product shell
- `storage/`: placeholder persistence boundary
- `ui/`: placeholder UI boundary

## Design rule

This package is intentionally not part of the published `ese` distribution yet.
It is a starter layer for product incubation while `ese` remains the generic
execution engine.
