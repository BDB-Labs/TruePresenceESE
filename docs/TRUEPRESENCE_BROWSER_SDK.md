# TruePresence Browser SDK

## Purpose

The TruePresence browser SDK collects privacy-preserving interaction summaries from selected web forms and sends those summaries to the TruePresence evaluation endpoint.

The SDK records how an interaction unfolds, not what a user types.

## Installation and usage

The repository ships the SDK as browser-compatible ES modules under `truepresence/sdk/`.

```html
<script type="module">
  import { TruePresence } from "/truepresence/sdk/index.js";

  TruePresence.init({
    siteKey: "tp_site_test",
    endpoint: "/api/v1/truepresence/evaluate-interaction",
    captureContent: false,
    mode: "privacy_preserving",
  });

  TruePresence.protectForm("#signup-form", {
    sensitivity: "medium",
    challenge: "typing_cadence",
  });
</script>
```

## Public API

### `TruePresence.init(config)`

Required:

- `siteKey`: site or tenant identifier sent as `feature_packet.site_id`
- `endpoint`: evaluation endpoint, usually `/api/v1/truepresence/evaluate-interaction`

Defaults:

- `captureContent`: `false`
- `mode`: `privacy_preserving`
- `tenantId`: `default`
- `enforcementMode`: `observe`

Optional:

- `sessionId`: caller-provided session id
- `debug`: enables structured SDK warnings
- `beforeSend(payload)`: last chance to inspect or replace the payload before submission
- `onEvaluation(result)`: called with the backend evaluation response
- `onError(error)`: called with structured SDK/network errors

`captureContent: true` is intentionally unsupported. The SDK throws a clear configuration error rather than collecting content.

### `TruePresence.protectForm(selector, options)`

Attaches privacy-safe listeners to eligible fields in the selected form.

```js
TruePresence.protectForm("#signup-form", {
  challenge: "typing_cadence",
  expectedReadingTimeMs: 1500,
});
```

### `TruePresence.evaluate()`

Finalizes current summaries, posts to the configured endpoint, and returns the parsed backend response.

```js
const result = await TruePresence.evaluate();
```

Network failures return a structured result:

```json
{
  "ok": false,
  "session_id": "tp_sess_...",
  "error": {
    "code": "network_error",
    "message": "TruePresence evaluation request failed."
  }
}
```

## HTML attributes

```html
<input data-truepresence="challenge" />
<input data-truepresence="timing-only" />
<textarea data-truepresence-ignore="true"></textarea>
```

Default ignored fields:

- password inputs
- hidden inputs
- file inputs
- payment/card-like fields where detectable
- sensitive autocomplete fields such as `cc-number`, `cc-csc`, and password autocomplete values
- fields marked `data-truepresence-ignore="true"`

## Privacy model

The SDK does not transmit raw typed text, raw key values, passwords, payment data, private messages, raw textarea content, or raw free-form content.

It collects derived metrics such as:

- mean inter-key interval
- inter-key interval standard deviation
- characters-per-minute estimate from length deltas
- correction count and correction rate
- paste count
- focus-to-first-input timing
- prompt-render-to-first-input timing
- response latency
- pointer movement count and entropy summary
- click hesitation timing
- scroll cadence summary
- visibility/focus changes as aggregate metadata

If `beforeSend` injects obvious raw-content fields such as `typed_text`, `value`, `key`, or `message_body`, the SDK strips them before transmission.

## Example form integration

```html
<form id="signup-form">
  <label>
    Display name
    <input name="display_name" data-truepresence="timing-only" />
  </label>

  <label>
    Verification phrase
    <input data-truepresence="challenge" data-truepresence-expected-reading-ms="1500" />
  </label>

  <label>
    Password
    <input type="password" autocomplete="new-password" />
  </label>

  <textarea data-truepresence-ignore="true"></textarea>
  <button type="submit">Continue</button>
</form>
```

## Example evaluation response

```json
{
  "human_presence_likelihood": 0.72,
  "automation_likelihood": 0.18,
  "agentic_control_likelihood": 0.14,
  "confidence": 0.64,
  "reason_codes": [],
  "evidence_packet_id": "ep_...",
  "recommended_action": "observe",
  "enforcement_mode": "observe"
}
```
