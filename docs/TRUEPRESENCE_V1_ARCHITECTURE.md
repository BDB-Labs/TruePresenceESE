# TruePresence V1 Architecture

TruePresence is the product boundary. `ese/` remains the orchestration substrate that supports ensemble workflows and CLI-driven software engineering use cases.

## Runtime Flow

1. Surface adapters normalize events into an `EvidencePacket`.
2. The evidence layer builds an `ArgumentGraph` of supporting and attacking claims.
3. The ensemble orchestrator evaluates the packet and graph through the role debate.
4. The decision layer synthesizes the final `DecisionObject` and `DecisionArtifact`.
5. Surfaces enforce the decision in a surface-specific way.

## Product Packages

- `truepresence/evidence/`: Evidence packet and argument graph contracts.
- `truepresence/decision/`: Decision router, state model, reason codes, and engine.
- `truepresence/ensemble/`: Product-facing orchestration layer over the existing runtime.
- `truepresence/surfaces/`: Surface-specific adapters and SDK contracts.
- `truepresence/memory/session_timeline.py`: Temporal memory for behavioral drift and windows.
- `truepresence/identity/graph.py`: Product-facing identity graph import path.

## Core Contract

`TruePresenceDecisionEngine.evaluate(session_id, surface, event, ...)` returns:

- `DecisionObject`
- `EvidencePacket`
- `DecisionArtifact`

This keeps surface code narrow while preserving the underlying ensemble runtime as an internal implementation detail.
