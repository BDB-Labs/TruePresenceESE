# TruePresence V1 Architecture

“TruePresence is the product. ESE is the reusable orchestration substrate. This repository currently contains both because TruePresence is being built atop ESE.”

## 1. Purpose

TruePresence is a multi-surface trust and guard system. Its job is to evaluate whether a session, operator, or interaction should be allowed, challenged, stepped up, restricted, blocked, or ejected. V1 makes that reasoning structure explicit without rewriting the existing runtime from scratch.

## 2. Product boundary

`truepresence/` is the product application boundary.
`ese/` is reusable orchestration substrate code.

TruePresence owns:
- evidence contracts
- temporal reasoning
- decision policies
- enforcement mapping
- artifacts and auditability

ESE owns:
- generic orchestration mechanics
- role execution infrastructure
- reusable model/runtime plumbing

## 3. Guard surfaces

V1 supports multiple guard surfaces, beginning with:
- Telegram Guard
- Web Guard SDK + Server Guard API

Surface code should stay narrow. It normalizes events, calls the canonical decision engine, and applies enforcement. It does not make the final trust decision locally.

## 4. Canonical runtime pipeline

The canonical runtime pipeline is:

surface event
-> evidence packet
-> temporal argument graph
-> server-side ensemble decision
-> decision object
-> enforcement action
-> decision artifact

## 5. Evidence packet

The `EvidencePacket` is the canonical product input to the ensemble decision engine. It captures:
- raw events
- challenge data
- timing and behavioral features
- identity references
- session history
- policy and risk context
- provenance

Every evaluation, including deterministic fast-path handling, emits an evidence packet.

## 6. Temporal argument graph

The `ArgumentGraph` is the explicit reasoning layer between raw evidence and a final decision. It stores claims plus support and attack edges so the system can explain why one conclusion was justified over another.

V1 keeps this graph deterministic and lightweight, but makes it the canonical place to represent:
- challenge success versus challenge failure
- human-presence support versus automation risk
- identity-cluster risk
- policy-driven step-up requirements

## 7. Ensemble decision engine

All authoritative decisions are made by the server-side ensemble except for a narrow Tier 0 deterministic fast path. The product-level contract is `TruePresenceDecisionEngine`, which:
- builds the evidence packet
- builds the argument graph
- chooses the evaluation tier
- invokes the server-side ensemble when required
- synthesizes the final decision
- persists the resulting artifacts

## 8. Tier routing (Tier 0 / Tier 1 / Tier 2)

Tier 0:
- deterministic or policy-hardcoded blatant violations
- still emits evidence and decision artifacts
- bypasses expensive ensemble debate

Tier 1:
- normal product evaluation path
- uses the server-side ensemble

Tier 2:
- ambiguous, high-risk, or high-value flows
- uses the ensemble with additional escalation and review pressure

## 9. Decision object

The canonical `DecisionObject` contains:
- decision identity
- session and tenant identity
- surface
- decision state
- recommended enforcement
- confidence and risk level
- reason codes
- artifact and trace references
- tier path metadata

Decision states include:
- `ALLOW`
- `OBSERVE`
- `ELEVATED_OBSERVE`
- `CHALLENGE`
- `STEP_UP_AUTH`
- `RESTRICT`
- `BLOCK`
- `EJECT`

## 10. Enforcement model

Surface enforcement is a product concern. Telegram and future web guard surfaces map the shared decision object into surface-specific actions such as:
- continue
- challenge
- restrict commands
- terminate interaction

Clients may collect telemetry or present challenges, but the server remains authoritative.

## 11. Artifact persistence

Every evaluation emits persisted reasoning artifacts:
- `EvidencePacket`
- `ArgumentGraph`
- `DecisionObject`
- decision artifact

Even Tier 0 actions must emit these artifacts so the audit trail is complete.

## 12. State model

TruePresence keeps:
- per-session temporal history
- cross-session identity linkage
- decision artifacts
- tenant and policy context

Per-session temporal memory must be isolated by `session_id`. Reset operations must target only the requested session unless an explicit administrative global reset path is invoked.

## 13. Model strategy

The server-side ensemble remains authoritative. Different roles may use different models or runtimes, but the product contract is model-agnostic. Reasoning integrity review is a good candidate for a reasoning-optimized model in future iterations.

## 14. Implementation priorities

V1 priorities are:
- make the product boundary visible
- introduce canonical evidence and decision contracts
- keep the server-side ensemble authoritative
- preserve existing useful code behind adapters and shims
- emit complete artifacts for every decision path
- fix correctness and security defects before adding more surface area
