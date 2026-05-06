# TruePresence Scoring Model

## Purpose

TruePresence scoring is deterministic calibration, not machine learning. The model combines derived behavioral features and detector signals into likelihoods, confidence, reason codes, and a recommended action.

The model evaluates how an interaction unfolds. It does not require raw typed content.

## Likelihoods Are Independent

The response likelihoods are independent signals, not normalized classes:

- `human_presence_likelihood` estimates how consistent the observed interaction is with human operation.
- `automation_likelihood` estimates how consistent the interaction is with scripted or mechanical automation.
- `agentic_control_likelihood` estimates how consistent the interaction is with agentic AI control.

These values do not need to sum to `1.0`. A contradictory or sparse session can have multiple moderate likelihoods, and a strong generic automation session should not automatically produce high agentic-control likelihood.

## Product Of Complements

The model uses product-of-complements aggregation:

```text
combined = 1 - product(1 - signal_strength)
```

This behaves like a probabilistic OR for independent evidence. Additional signals can increase risk, but the result remains bounded in `[0, 1]` and naturally saturates as evidence accumulates.

Each detector signal first receives a deterministic strength:

```text
signal_strength = severity_weight * confidence
```

Severity and category weights are configured in `truepresence/scoring/weights.py`.

## Category-Aware Aggregation

Signals are grouped by category before being combined across categories. The model first combines repeated signals within the same category, then applies category weights and combines independent categories.

This prevents one detector family from overcounting the same underlying behavior. For example, many typing-cadence signals should not create runaway risk by themselves. Cross-category corroboration, such as typing cadence plus input method plus environment evidence, is stronger because the signals come from independent behavioral surfaces.

Risk categories also receive a small corroboration bonus when multiple independent risk categories are present. This bonus is capped.

## Human Support And Contradiction

Human-like aggregate features reduce risk. Examples include natural typing interval variation, corrections, no paste activity, plausible focus-to-input timing, plausible challenge latency, pointer entropy, click hesitation, and scroll cadence summaries.

Human-presence detector signals can also add support. When strong human evidence coexists with high risk, the model treats the session as contradictory and reduces confidence. Contradiction does not erase risk; it communicates that the evidence is mixed.

## Confidence Is Not Likelihood

Confidence estimates how much trust to place in the score. It is based on:

- evidence sufficiency, using the number of risk categories and risk signals;
- contradiction handling;
- adjusted risk strength.

Low evidence caps confidence even if one signal appears suspicious. Confidence can also fall when high-risk and strong human-like signals coexist.

## Recommended Action

`recommended_action` uses both risk and confidence:

- low risk with enough confidence can allow;
- low confidence keeps the action cautious;
- high risk with limited confidence avoids jumping straight to the most aggressive action;
- high risk with high confidence can escalate to step-up authentication or manual review.

This keeps deterministic scoring conservative when evidence is sparse or contradictory.

## Calibration Fixtures

Initial deterministic scenario fixtures live in `tests/truepresence/fixtures/`:

- `human_like_session.json`;
- `scripted_bot_session.json`;
- `low_evidence_session.json`;
- `contradictory_session.json`.

Fixtures contain derived metrics and detector signal metadata only. They must not contain raw text, raw input values, transcripts, prompts, comments, messages, or other free-form user content.
