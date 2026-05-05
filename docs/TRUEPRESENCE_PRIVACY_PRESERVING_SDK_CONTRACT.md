# TruePresence Privacy-Preserving SDK Contract

## Purpose

TruePresence must evaluate interaction authenticity without collecting actual user content.

The product goal is not to record what a person types, reads, or submits. The product goal is to measure whether an interaction unfolds in a way that is consistent with human operation, scripted automation, or agentic AI control.

## Core Principle

> Collect behavior-derived features, not content.

TruePresence should never need raw field values, raw keystrokes, passwords, message text, payment data, medical text, or free-form user content to produce its core human-presence and automation-risk signals.

## What The SDK May Collect

The SDK may collect derived timing, rhythm, and interaction metrics such as:

- typing duration for a protected challenge or field;
- mean inter-key interval;
- inter-key interval variance / standard deviation;
- burst count and pause distribution;
- characters-per-minute estimate;
- correction count and correction rate;
- paste event count;
- time from field focus to first input;
- time from prompt render to first interaction;
- time from final interaction to submit;
- pointer movement entropy;
- pointer path curvature summary;
- click hesitation timing;
- scroll cadence summaries;
- focus / blur sequence metadata;
- challenge response latency;
- whether response timing was physically plausible for a human to read and respond.

These features should be computed locally where practical and transmitted as aggregate metrics.

## What The SDK Must Not Collect By Default

The SDK must not collect by default:

- actual typed text;
- raw key values;
- passwords;
- payment card data;
- Social Security numbers or government IDs;
- private messages;
- medical, legal, or other sensitive free-text content;
- complete pointer trails tied to a persistent identity;
- long-term biometric profiles unless explicitly enabled by the integrating site with appropriate disclosure and consent.

## Field-Level Controls

Integrating sites must be able to opt fields in or out explicitly.

Recommended HTML controls:

```html
<input data-truepresence="challenge" />
<input data-truepresence="timing-only" />
<textarea data-truepresence-ignore="true"></textarea>
```

Default behavior should ignore sensitive input types, including:

- password;
- payment;
- hidden;
- file;
- fields marked autocomplete for sensitive values where detectable;
- any element marked `data-truepresence-ignore="true"`.

## Challenge Design

TruePresence challenges should measure interaction process rather than private knowledge.

Examples:

- type a displayed phrase;
- click after a visual state change;
- select an indicated visual element;
- complete a short instruction where response time and input rhythm matter.

The system may evaluate whether:

- an answer appeared faster than a human could plausibly read the prompt;
- typing cadence was unnaturally uniform;
- there was no variation, hesitation, or correction where human variation is expected;
- text appeared through paste or script injection rather than typed input;
- interaction sequence resembles DOM automation rather than visual/manual use.

## Output Semantics

TruePresence outputs must be probabilistic and evidence-based.

Recommended signal fields:

```json
{
  "human_presence_likelihood": 0.74,
  "automation_likelihood": 0.22,
  "agentic_control_likelihood": 0.48,
  "confidence": 0.69,
  "reason_codes": [
    "uniform_typing_cadence",
    "implausible_read_response_time"
  ],
  "evidence_packet_id": "ep_...",
  "recommended_action": "step_up_challenge"
}
```

TruePresence must not claim certainty that an actor is human or non-human. It should state that observed interaction features are more or less consistent with human operation, automation, or agentic control.

## Privacy And Retention Defaults

Recommended defaults:

- raw browser events: in-memory only;
- derived feature windows: short-lived;
- evidence packet: retained according to site policy;
- no raw content retention;
- no persistent behavioral identity profile by default.

## Implementation Requirement

Any web SDK, testing SDK, Telegram adapter, or future surface adapter should map its telemetry into this privacy-preserving feature model before evidence packets are built.

TruePresence should be able to explain a decision without exposing what the user typed.

## Product Language

Preferred wording:

> TruePresence records how an interaction unfolds, not what a user types.

Avoid wording such as:

- "proves the user is human";
- "identifies bots with certainty";
- "records user typing";
- "behavioral biometric identity" unless a separate explicit feature is designed, disclosed, consented to, and governed.
