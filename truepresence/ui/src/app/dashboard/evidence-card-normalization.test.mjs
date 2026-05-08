import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const source = readFileSync(new URL("./evidence-card-normalization.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
});
const transpiledModule = { exports: {} };
vm.runInNewContext(outputText, {
  exports: transpiledModule.exports,
  module: transpiledModule,
  require,
});

const {
  EVALUATION_CARD_ALLOWED_FIELDS,
  EVALUATION_CARD_UNSAFE_FIELDS,
  normalizeEvaluationEvidenceCard,
} = transpiledModule.exports;

test("normalization drops unknown and unsafe dashboard evidence fields", () => {
  const normalized = normalizeEvaluationEvidenceCard({
    id: "ev-1",
    eventType: "web_sdk",
    surface: "web",
    risk_level: "medium",
    human_presence_likelihood: 0.8,
    automation_likelihood: 0.2,
    agentic_control_likelihood: 0.1,
    confidence: 0.7,
    reason_codes: ["aggregate_timing"],
    evidence_packet_id: "packet-1",
    decision_id: "decision-1",
    recommended_action: "allow",
    timestamp: "2026-05-08T12:00:00Z",
    typed_text: "private typed text",
    raw_text: "private raw text",
    key_values: ["s", "e", "c", "r", "e", "t"],
    keys: ["s"],
    message: "private message",
    caption: "private caption",
    content: "private content",
    media_url: "https://example.invalid/private-media",
    file_url: "https://example.invalid/private-file",
    thumbnail: "private thumbnail",
    password: "private-password",
    card_number: "4111111111111111",
    unknown_future_field: "private future content",
  });

  assert.deepEqual(
    Object.keys(normalized).sort(),
    [...EVALUATION_CARD_ALLOWED_FIELDS].sort(),
  );
  for (const unsafeField of EVALUATION_CARD_UNSAFE_FIELDS) {
    assert.equal(Object.hasOwn(normalized, unsafeField), false);
  }
  assert.equal(JSON.stringify(normalized).includes("private"), false);
});

test("normalization tolerates malformed card values without rendering free-form text", () => {
  const normalized = normalizeEvaluationEvidenceCard(
    {
      id: "4111111111111111",
      eventType: "unknown",
      surface: "raw content with spaces",
      risk_level: "high because the user wrote private content",
      confidence: 1.4,
      reason_codes: ["provider_signal", "caption contains raw content", { message: "secret" }],
      evidence_packet_id: "https://example.invalid/media.jpg",
      recommended_action: "admin_review",
      timestamp: "not a timestamp",
    },
    {
      fallbackEventType: "safety",
      fallbackId: "fallback-card",
      fallbackSurface: "telegram",
    },
  );

  assert.equal(normalized.id, "fallback-card");
  assert.equal(normalized.eventType, "safety");
  assert.equal(normalized.surface, "telegram");
  assert.equal(normalized.risk_level, undefined);
  assert.equal(normalized.confidence, undefined);
  assert.equal(JSON.stringify(normalized.reason_codes), JSON.stringify(["provider_signal"]));
  assert.equal(normalized.evidence_packet_id, undefined);
  assert.equal(normalized.recommended_action, "admin_review");
  assert.equal(normalized.timestamp, undefined);
  assert.equal(JSON.stringify(normalized).includes("raw content"), false);
});
