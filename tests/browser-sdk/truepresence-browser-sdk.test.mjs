import assert from "node:assert/strict";
import test from "node:test";

import { TruePresence, TruePresenceSDKError } from "../../truepresence/sdk/index.js";

class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) || [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  removeEventListener(type, handler) {
    const handlers = this.listeners.get(type) || [];
    this.listeners.set(
      type,
      handlers.filter((candidate) => candidate !== handler),
    );
  }

  dispatchEvent(event) {
    event.target = event.target || this;
    for (const handler of this.listeners.get(event.type) || []) {
      handler(event);
    }
    return !event.defaultPrevented;
  }
}

class FakeField extends FakeEventTarget {
  constructor({ type = "text", tagName = "INPUT", autocomplete = "", ignored = false } = {}) {
    super();
    this.type = type;
    this.tagName = tagName;
    this.value = "";
    this.autocomplete = autocomplete;
    this.dataset = {};
    if (ignored) {
      this.dataset.truepresenceIgnore = "true";
    }
  }
}

class FakeForm extends FakeEventTarget {
  constructor(fields = []) {
    super();
    this.fields = fields;
  }

  querySelectorAll(selector) {
    assert.equal(selector, "input, textarea, select");
    return this.fields;
  }
}

class FakeDocument extends FakeEventTarget {
  constructor(form) {
    super();
    this.form = form;
    this.visibilityState = "visible";
  }

  querySelector(selector) {
    return selector === "#signup-form" ? this.form : null;
  }
}

class FakeSessionStorage {
  constructor() {
    this.values = new Map();
  }

  getItem(key) {
    return this.values.get(key) || null;
  }

  setItem(key, value) {
    this.values.set(key, String(value));
  }
}

function event(type, values = {}) {
  return {
    type,
    defaultPrevented: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
    ...values,
  };
}

function createHarness(fields = [new FakeField()]) {
  let now = 1000;
  const calls = [];
  const form = new FakeForm(fields);
  const document = new FakeDocument(form);
  const window = new FakeEventTarget();
  window.location = { hostname: "example.test", pathname: "/signup" };
  window.innerWidth = 1440;
  window.innerHeight = 900;
  window.sessionStorage = new FakeSessionStorage();
  window.matchMedia = () => ({ matches: false });
  const fetch = async (url, options) => {
    calls.push({ url, options, payload: JSON.parse(options.body) });
    return {
      ok: true,
      status: 200,
      json: async () => ({
        human_presence_likelihood: 0.7,
        automation_likelihood: 0.2,
        agentic_control_likelihood: 0.1,
        confidence: 0.6,
        reason_codes: [],
        evidence_packet_id: "ep_test",
        recommended_action: "observe",
        enforcement_mode: "observe",
      }),
    };
  };

  return {
    calls,
    document,
    fields,
    form,
    tick(ms) {
      now += ms;
      return now;
    },
    now: () => now,
    window,
    fetch,
  };
}

function initHarness(harness, overrides = {}) {
  return TruePresence.create().init({
    siteKey: "tp_site_test",
    endpoint: "/api/v1/truepresence/evaluate-interaction",
    document: harness.document,
    window: harness.window,
    fetch: harness.fetch,
    now: harness.now,
    ...overrides,
  });
}

test("SDK initializes with privacy-preserving defaults", () => {
  const harness = createHarness();
  const sdk = initHarness(harness);

  assert.equal(sdk.config.captureContent, false);
  assert.equal(sdk.config.mode, "privacy_preserving");
  assert.match(sdk.sessionId, /^tp_sess_/);
});

test("SDK rejects captureContent true with a clear error", () => {
  const harness = createHarness();

  assert.throws(
    () => initHarness(harness, { captureContent: true }),
    (error) =>
      error instanceof TruePresenceSDKError &&
      error.code === "capture_content_unsupported",
  );
});

test("password, hidden, file, autocomplete-sensitive, and ignored fields are not tracked", () => {
  const fields = [
    new FakeField({ type: "password" }),
    new FakeField({ type: "hidden" }),
    new FakeField({ type: "file" }),
    new FakeField({ autocomplete: "cc-number" }),
    new FakeField({ tagName: "TEXTAREA", ignored: true }),
    new FakeField(),
  ];
  const harness = createHarness(fields);
  const sdk = initHarness(harness);

  sdk.protectForm("#signup-form");

  assert.equal(sdk.getFeatureSnapshot().metadata.tracked_field_count, 1);
});

test("raw typed text and raw key values are not present in the evaluation payload", async () => {
  const field = new FakeField();
  const harness = createHarness([field]);
  const sdk = initHarness(harness);
  sdk.protectForm("#signup-form");

  field.dispatchEvent(event("focus"));
  harness.tick(80);
  field.dispatchEvent(event("keydown", { key: "S" }));
  field.value = "secret private phrase";
  field.dispatchEvent(event("input"));
  await sdk.evaluate();

  const body = JSON.stringify(harness.calls[0].payload);
  assert.equal(body.includes("secret private phrase"), false);
  assert.equal(body.includes('"key"'), false);
  assert.equal(body.includes('"keys"'), false);
  assert.equal(body.includes("typed_text"), false);
});

test("typing cadence features are computed from timing and length metadata", async () => {
  const field = new FakeField();
  const harness = createHarness([field]);
  const sdk = initHarness(harness);
  sdk.protectForm("#signup-form");

  field.dispatchEvent(event("focus"));
  harness.tick(100);
  field.dispatchEvent(event("keydown", { key: "a" }));
  field.value = "a";
  field.dispatchEvent(event("input"));
  harness.tick(120);
  field.dispatchEvent(event("keydown", { key: "b" }));
  field.value = "ab";
  field.dispatchEvent(event("input"));
  harness.tick(180);
  field.dispatchEvent(event("keydown", { key: "Backspace" }));
  field.value = "a";
  field.dispatchEvent(event("input"));

  await sdk.evaluate();
  const { typing, metadata } = harness.calls[0].payload.feature_packet;

  assert.equal(metadata.typing_summary.input_event_count, 3);
  assert.equal(typing.mean_inter_key_interval_ms, 150);
  assert.equal(typing.inter_key_interval_stddev_ms, 30);
  assert.equal(metadata.typing_summary.min_inter_key_interval_ms, 120);
  assert.equal(metadata.typing_summary.max_inter_key_interval_ms, 180);
  assert.equal(typing.correction_count, 2);
  assert.equal(typing.correction_rate, 2 / 3);
  assert.ok(typing.characters_per_minute > 0);
});

test("paste events increment paste count without storing pasted text", async () => {
  const field = new FakeField();
  const harness = createHarness([field]);
  const sdk = initHarness(harness);
  sdk.protectForm("#signup-form");

  field.dispatchEvent(
    event("paste", {
      clipboardData: { getData: () => "PASTED SECRET" },
    }),
  );
  field.value = "pasted value";
  field.dispatchEvent(event("input"));

  await sdk.evaluate();
  const payload = harness.calls[0].payload;
  assert.equal(payload.feature_packet.typing.paste_count, 1);
  assert.equal(JSON.stringify(payload).includes("PASTED SECRET"), false);
  assert.equal(JSON.stringify(payload).includes("pasted value"), false);
});

test("challenge-marked fields produce process-only challenge timing features", async () => {
  const field = new FakeField();
  field.dataset.truepresence = "challenge";
  field.dataset.truepresenceExpectedReadingMs = "1500";
  const harness = createHarness([field]);
  const sdk = initHarness(harness);
  sdk.protectForm("#signup-form");

  harness.tick(250);
  field.dispatchEvent(event("focus"));
  harness.tick(100);
  field.dispatchEvent(event("keydown", { key: "x" }));
  field.value = "x";
  field.dispatchEvent(event("input"));
  harness.tick(1150);

  await sdk.evaluate();
  const { challenge } = harness.calls[0].payload.feature_packet;

  assert.equal(challenge.challenge_type, "typing_cadence");
  assert.equal(challenge.expected_reading_time_ms, 1500);
  assert.equal(challenge.prompt_render_to_first_input_ms, 350);
  assert.equal(challenge.response_latency_ms, 1500);
});

test("pointer summary is reduced to aggregate metrics", async () => {
  const harness = createHarness();
  const sdk = initHarness(harness);
  sdk.protectForm("#signup-form");

  harness.document.dispatchEvent(event("pointermove", { clientX: 10, clientY: 10 }));
  harness.tick(30);
  harness.document.dispatchEvent(event("pointermove", { clientX: 20, clientY: 15 }));
  harness.tick(70);
  harness.document.dispatchEvent(event("click", { clientX: 20, clientY: 15 }));
  await sdk.evaluate();

  const payload = harness.calls[0].payload;
  assert.equal(payload.feature_packet.pointer.pointer_movement_count, 2);
  assert.equal(payload.feature_packet.pointer.click_count, 1);
  assert.ok(payload.feature_packet.pointer.click_hesitation_ms >= 0);
  assert.equal(JSON.stringify(payload).includes("clientX"), false);
  assert.equal(JSON.stringify(payload).includes('"x"'), false);
});

test("evaluate posts to the configured endpoint and returns backend response", async () => {
  const harness = createHarness();
  const sdk = initHarness(harness);
  sdk.protectForm("#signup-form");

  const result = await sdk.evaluate();

  assert.equal(harness.calls[0].url, "/api/v1/truepresence/evaluate-interaction");
  assert.equal(harness.calls[0].payload.session_id, sdk.sessionId);
  assert.equal(harness.calls[0].payload.feature_packet.site_id, "tp_site_test");
  assert.equal(result.evidence_packet_id, "ep_test");
});

test("network failure returns a structured error result and calls onError", async () => {
  const harness = createHarness();
  const errors = [];
  const sdk = initHarness(harness, {
    fetch: async () => {
      throw new Error("offline");
    },
    onError: (error) => errors.push(error),
  });

  const result = await sdk.evaluate();

  assert.equal(result.ok, false);
  assert.equal(result.error.code, "network_error");
  assert.equal(errors.length, 1);
  assert.equal(errors[0].code, "network_error");
});

test("beforeSend cannot inject raw content into the payload", async () => {
  const harness = createHarness();
  const sdk = initHarness(harness, {
    beforeSend: (payload) => ({
      ...payload,
      feature_packet: {
        ...payload.feature_packet,
        typing: {
          ...payload.feature_packet.typing,
          typed_text: "SHOULD NOT LEAVE SDK",
        },
      },
    }),
  });

  await sdk.evaluate();

  const body = JSON.stringify(harness.calls[0].payload);
  assert.equal(body.includes("typed_text"), false);
  assert.equal(body.includes("SHOULD NOT LEAVE SDK"), false);
});
