# TruePresence

**TruePresence is a privacy-preserving interaction authenticity SDK.**

It estimates, for any given web interaction, the likelihood that the actor is a human being, an automated script, or an AI agent in agentic control of a session. It does this without recording what a user types.

> **The SDK records how an interaction unfolds, not what a user types.**

TruePresence produces probabilistic signals — not verdicts. It returns a recommended action based on observed behavioral evidence, and it is designed to be transparent about the limits of that evidence.

---

## How it works

TruePresence observes the *shape* of an interaction: timing intervals, typing rhythm, correction patterns, pointer behavior, and challenge response latency. It computes derived metrics locally in the browser, transmits only those derived features to the evaluation endpoint, and returns a scored response.

The scoring model combines per-signal strength values across independent behavioral categories using a probabilistic aggregation formula. Signals from multiple independent categories increase risk estimates more than multiple signals from the same category. Contradictory evidence (strong human signals coexisting with automation signals) reduces the confidence value rather than being silently ignored.

The response always includes:

| Field | Description |
|---|---|
| `human_presence_likelihood` | Probability-scaled estimate that observed behavior is consistent with a human |
| `automation_likelihood` | Estimate consistent with scripted or injected input |
| `agentic_control_likelihood` | Estimate consistent with an AI agent controlling the session |
| `confidence` | How much weight to place on the above estimates given available evidence |
| `reason_codes` | Identifiers for the specific behavioral signals that fired |
| `recommended_action` | One of: `allow`, `observe`, `soft_challenge`, `step_up_auth`, `manual_review` |
| `evidence_packet_id` | Opaque identifier for this evaluation |

TruePresence does not claim to prove that any actor is human, and it does not claim to detect all automated actors. It states that observed interaction features are more or less consistent with human operation, automation, or agentic control.

---

## Components

### Browser SDK (`truepresence/sdk/index.js`)

An ES module that attaches to web forms, collects privacy-safe derived interaction features, and posts them to the evaluation endpoint. Raw typed text, raw key values, passwords, payment data, and private content are never transmitted.

### Backend evaluation endpoint (`POST /api/v1/truepresence/evaluate-interaction`)

A FastAPI route that accepts an `InteractionFeaturePacket`, runs the behavioral detectors and probabilistic scoring model, and returns a `TruePresenceEvaluationResponse`.

### Privacy guard (`truepresence/sdk/privacy.py`, `truepresence/sdk/privacy.js`)

Server-side and client-side enforcement that rejects payloads containing raw content fields. If a payload contains `typed_text`, `key_values`, `password`, or similar fields, the guard raises before the payload reaches the scoring model.

### Behavioral detectors (`truepresence/detectors/`)

Deterministic Python functions that inspect derived feature values and emit `DetectorSignal` objects. Each signal carries a severity, a confidence value, a contribution target (`automation`, `agentic_control`, or `human_presence`), and a behavioral category. Current detectors:

- `uniform_typing_cadence` — inter-key interval variance near zero
- `paste_or_instant_input` — input appeared faster than manual typing allows
- `zero_correction_pattern` — no corrections at high speed with low variance
- `implausible_read_response_time` — response arrived faster than the human read window

### Scoring model (`truepresence/scoring/model.py`)

Combines detector signals using a calibrated probabilistic model: per-signal strength is computed from severity and confidence, signals within each behavioral category are aggregated via a product-of-complements formula to prevent overcounting, and categories are combined across independent evidence dimensions. Corroboration bonuses apply when multiple independent categories fire. Contradiction penalties apply when strong human evidence coexists with high risk.

### Adapters

TruePresence can be embedded in web surfaces, staging environments, and community platforms. Telegram is one optional adapter (`truepresence/adapters/telegram_bot.py`), not the product center.

---

## Quickstart

### 1. Add the browser SDK to your form

```html
<script type="module">
  import { TruePresence } from "/truepresence/sdk/index.js";

  TruePresence.init({
    siteKey: "tp_site_your_key",
    endpoint: "/api/v1/truepresence/evaluate-interaction",
    captureContent: false,
    mode: "privacy_preserving",
    onEvaluation(result) {
      console.log(result.recommended_action, result.confidence);
    },
  });

  TruePresence.protectForm("#your-form", {
    challenge: "typing_cadence",
    expectedReadingTimeMs: 1500,
  });
</script>
```

### 2. Trigger evaluation on submit

```js
document.querySelector("#your-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const result = await TruePresence.evaluate();
  // result.recommended_action is one of:
  //   allow | observe | soft_challenge | step_up_auth | manual_review
});
```

### 3. Or call the endpoint directly

```http
POST /api/v1/truepresence/evaluate-interaction
Content-Type: application/json

{
  "session_id": "sess_abc123",
  "tenant_id": "default",
  "feature_packet": {
    "surface": "web",
    "typing": {
      "mean_inter_key_interval_ms": 185,
      "inter_key_interval_stddev_ms": 68,
      "characters_per_minute": 210,
      "correction_count": 3,
      "correction_rate": 0.05,
      "paste_count": 0,
      "focus_to_first_input_ms": 430
    },
    "challenge": {
      "response_latency_ms": 3800,
      "expected_reading_time_ms": 1500
    },
    "pointer": {
      "pointer_entropy": 0.71,
      "click_hesitation_ms": 195,
      "scroll_cadence_score": 0.58
    }
  }
}
```

Response:

```json
{
  "human_presence_likelihood": 0.74,
  "automation_likelihood": 0.12,
  "agentic_control_likelihood": 0.09,
  "confidence": 0.68,
  "reason_codes": [],
  "evidence_packet_id": "ep_3f9a...",
  "recommended_action": "observe",
  "enforcement_mode": "observe"
}
```

---

## Privacy

TruePresence is designed so that it never needs to see what a user typed in order to produce its signals.

**Not collected by default:**

- Raw typed text or keystroke values
- Passwords or credential fields
- Payment card data
- Hidden field values
- Private messages or free-form content
- File input content

**What is collected:**

- Aggregate timing metrics (mean and variance of key intervals, not individual keys)
- Typing speed estimate from content length deltas, not actual characters
- Correction counts and rates
- Paste event count (not paste content)
- Focus and response timing
- Pointer movement entropy and hesitation summaries

Password inputs, hidden inputs, file inputs, payment-like fields, and any field marked `data-truepresence-ignore="true"` are excluded automatically.

If a `beforeSend` callback or a direct API call injects raw content fields such as `typed_text`, `key_values`, or `password`, the privacy guard rejects the payload with a validation error before scoring begins.

For the full privacy contract, see [docs/TRUEPRESENCE_PRIVACY_PRESERVING_SDK_CONTRACT.md](docs/TRUEPRESENCE_PRIVACY_PRESERVING_SDK_CONTRACT.md).

---

## Backend setup

Start the backend:

```bash
./start_ese.sh
```

Or directly:

```bash
uvicorn truepresence.main:app --reload
```

Production auth requires `JWT_SECRET`. A development fallback is available only when `TRUEPRESENCE_ALLOW_DEV_AUTH` is also set. See [docs/TRUEPRESENCE_STARTUP.md](docs/TRUEPRESENCE_STARTUP.md) for full startup, database, and deployment guidance.

---

## Documentation

| Document | Description |
|---|---|
| [docs/TRUEPRESENCE_BROWSER_SDK.md](docs/TRUEPRESENCE_BROWSER_SDK.md) | Full browser SDK API reference, HTML attributes, and integration examples |
| [docs/TRUEPRESENCE_PRIVACY_PRESERVING_SDK_CONTRACT.md](docs/TRUEPRESENCE_PRIVACY_PRESERVING_SDK_CONTRACT.md) | Privacy model, data collection boundaries, and output semantics contract |
| [docs/TRUEPRESENCE_SDK_IMPLEMENTATION_BACKLOG.md](docs/TRUEPRESENCE_SDK_IMPLEMENTATION_BACKLOG.md) | Active implementation workstreams and acceptance criteria |
| [docs/TRUEPRESENCE_CODEBASE_MAP.md](docs/TRUEPRESENCE_CODEBASE_MAP.md) | Canonical package paths, active modules, and API entry points |
| [docs/TRUEPRESENCE_V1_ARCHITECTURE.md](docs/TRUEPRESENCE_V1_ARCHITECTURE.md) | Architecture overview and design rationale |
| [docs/TRUEPRESENCE_DECISION_ENGINE.md](docs/TRUEPRESENCE_DECISION_ENGINE.md) | Decision engine and evidence synthesis internals |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

---

## Repository structure

```
truepresence/
  sdk/           # Browser SDK (JS) and Python SDK contracts, privacy guard
  detectors/     # Behavioral detector functions
  scoring/       # Probabilistic scoring model and category weights
  api/           # FastAPI routes including evaluate-interaction
  adapters/      # Surface adapters (Telegram and others)
  decision/      # Decision engine and evidence synthesis
  evidence/      # Evidence packet and argument graph
ese/             # ESE ensemble orchestration substrate (separate concern)
tests/truepresence/   # SDK, scoring, API, and privacy tests
tests/browser-sdk/    # Browser SDK Node.js tests
docs/            # Product and architecture documentation
```

TruePresence is built on ESE (Ensemble Software Engineering), a generic AI orchestration substrate also present in this repository. ESE handles model routing, ensemble execution, and extension mechanics. TruePresence product logic — evidence contracts, behavioral detectors, scoring, enforcement flows — lives entirely under `truepresence/`.

---

## License

See [LICENSE](LICENSE).
