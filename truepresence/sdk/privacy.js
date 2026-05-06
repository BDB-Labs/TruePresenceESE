/**
 * TruePresence Browser SDK — Privacy Guard
 *
 * Two-layer enforcement:
 *
 * Layer 1 — Global raw-content denylist
 *   isRawField() tests every key at every nesting depth.  Covers both the
 *   original disallowed names and the renamed variants (answer, response,
 *   comment, description, body, message, content, etc.).
 *
 * Layer 2 — Section-level allowlists
 *   stripRawContent() applies section allowlists when processing the known
 *   structured sections of feature_packet (typing, challenge, pointer,
 *   environment, session_continuity, page_context, metadata, and
 *   external_risk_provider). Any key not on the allowlist is stripped before
 *   the payload leaves the browser.
 *
 * The server (privacy.py) is the authoritative enforcement boundary.
 * The browser SDK strips defensively so that beforeSend callbacks and
 * integrator mistakes do not reach the server with raw content.
 */

// ---------------------------------------------------------------------------
// Global raw-content denylist
// ---------------------------------------------------------------------------

const DISALLOWED_RAW_FIELDS = new Set([
  // Original names
  "card_number",
  "cardnumber",
  "freeform_content",
  "freeformcontent",
  "key",
  "key_values",
  "keyvalues",
  "keys",
  "message_body",
  "messagebody",
  "password",
  "raw_text",
  "rawtext",
  "ssn",
  "text",
  "typed_text",
  "typedtext",
  "value",
  // Renamed raw-content variants (hardening additions)
  "answer",
  "body",
  "comment",
  "content",
  "description",
  "field_value",
  "input_value",
  "message",
  "prompt",
  "raw_input",
  "raw_value",
  "response",
  "transcript",
  "user_input",
]);

const RAW_CONTENT_FRAGMENTS = [
  "card_number",
  "cardnumber",
  "credit",
  "creditcard",
  "cvc",
  "cvv",
  "freeform",
  "message_body",
  "password",
  "raw_",
  "social_security",
  "ssn",
  "typed_",
];

const SENSITIVE_TYPES = new Set(["password", "hidden", "file", "payment"]);
const SENSITIVE_AUTOCOMPLETE = new Set([
  "cc-csc",
  "cc-exp",
  "cc-exp-month",
  "cc-exp-year",
  "cc-name",
  "cc-number",
  "current-password",
  "new-password",
  "one-time-code",
]);

const SENSITIVE_NAME_FRAGMENTS = [
  "card",
  "cc_",
  "credit",
  "cvc",
  "cvv",
  "password",
  "payment",
  "ssn",
  "social_security",
];

// ---------------------------------------------------------------------------
// Section-level field allowlists
// Used by stripRawContent to enforce closed schemas on known sections.
// ---------------------------------------------------------------------------

const ALLOWED_TYPING_FIELDS = new Set([
  "characters_per_minute",
  "correction_count",
  "correction_rate",
  "focus_to_first_input_ms",
  "inter_key_interval_stddev_ms",
  "last_input_to_submit_ms",
  "mean_inter_key_interval_ms",
  "paste_count",
  "prompt_render_to_first_input_ms",
  "typing_duration_ms",
]);

const ALLOWED_CHALLENGE_FIELDS = new Set([
  "challenge_type",
  "correction_count",
  "expected_reading_time_ms",
  "paste_count",
  "prompt_render_to_first_input_ms",
  "response_latency_ms",
  "submitted_exactly",
  "typing_duration_ms",
]);

const ALLOWED_POINTER_FIELDS = new Set([
  "click_count",
  "click_hesitation_ms",
  "pointer_entropy",
  "pointer_movement_count",
  "scroll_cadence_score",
]);

const ALLOWED_ENVIRONMENT_FIELDS = new Set([
  "automation_framework_hint",
  "headless_browser_hint",
  "reduced_motion_enabled",
  "timezone_offset_minutes",
  "viewport_height",
  "viewport_width",
  "webdriver_detected",
]);

const ALLOWED_SESSION_CONTINUITY_FIELDS = new Set([
  "focus_blur_count",
  "navigation_count",
  "prior_interaction_count",
  "same_device_session_count",
  "session_age_ms",
]);

const ALLOWED_PAGE_CONTEXT_FIELDS = new Set([
  "hostname",
  "pathname",
  "referrer_present",
  "visibility_state",
]);

const ALLOWED_TYPING_SUMMARY_FIELDS = new Set([
  "delete_key_count",
  "input_event_count",
  "last_input_to_submit_ms",
  "max_inter_key_interval_ms",
  "min_inter_key_interval_ms",
  "tracked_field_count",
]);

const ALLOWED_METADATA_FIELDS = new Set([
  "mode",
  "sdk_version",
  "tracked_field_count",
  "typing_summary",
]);

const ALLOWED_EXTERNAL_RISK_PROVIDER_FIELDS = new Set([
  "confidence",
  "provider_id",
  "reason_codes",
  "risk_score",
]);

const ALLOWED_PACKET_FIELDS = new Set([
  "challenge",
  "environment",
  "external_risk_provider",
  "metadata",
  "page_context",
  "pointer",
  "session_continuity",
  "session_id",
  "site_id",
  "surface",
  "tenant_id",
  "typing",
]);

const ALLOWED_REQUEST_FIELDS = new Set([
  "enforcement_mode",
  "feature_packet",
  "session_id",
  "tenant_id",
]);

/** Map from feature_packet section key → its field allowlist. */
const SECTION_ALLOWLISTS = new Map([
  ["typing", ALLOWED_TYPING_FIELDS],
  ["challenge", ALLOWED_CHALLENGE_FIELDS],
  ["pointer", ALLOWED_POINTER_FIELDS],
  ["environment", ALLOWED_ENVIRONMENT_FIELDS],
  ["page_context", ALLOWED_PAGE_CONTEXT_FIELDS],
  ["session_continuity", ALLOWED_SESSION_CONTINUITY_FIELDS],
]);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function normalizeKey(key) {
  return String(key || "")
    .trim()
    .toLowerCase()
    .replace(/[-\s]/g, "_");
}

function attr(element, name) {
  if (!element) return "";
  if (typeof element.getAttribute === "function") {
    return element.getAttribute(name) || "";
  }
  return element[name] || "";
}

export function hasIgnoreAttribute(element) {
  return (
    element?.dataset?.truepresenceIgnore === "true" ||
    attr(element, "data-truepresence-ignore") === "true"
  );
}

export function isSensitiveField(element) {
  if (!element) return true;
  if (hasIgnoreAttribute(element)) return true;

  const type = normalizeKey(element.type || attr(element, "type") || "");
  if (SENSITIVE_TYPES.has(type)) return true;

  const autocomplete = String(element.autocomplete || attr(element, "autocomplete") || "")
    .trim()
    .toLowerCase();
  if (SENSITIVE_AUTOCOMPLETE.has(autocomplete)) return true;

  const descriptor = `${attr(element, "name")} ${attr(element, "id")} ${attr(
    element,
    "aria-label",
  )}`
    .toLowerCase()
    .replace(/[-\s]/g, "_");
  return SENSITIVE_NAME_FRAGMENTS.some((fragment) => descriptor.includes(fragment));
}

export function isEligibleField(element) {
  if (!element || isSensitiveField(element)) return false;
  const tagName = String(element.tagName || "").toUpperCase();
  return tagName === "INPUT" || tagName === "TEXTAREA";
}

/**
 * Return true if the key name matches the global raw-content denylist.
 * Checks exact normalized name and substring fragments.
 */
function isRawField(key) {
  const normalized = normalizeKey(key);
  if (DISALLOWED_RAW_FIELDS.has(normalized)) return true;
  return RAW_CONTENT_FRAGMENTS.some((fragment) => normalized.includes(fragment));
}

// ---------------------------------------------------------------------------
// stripRawContent
// Defensive client-side strip.  For known sections, applies the section
// allowlist and removes anything not explicitly permitted.
// ---------------------------------------------------------------------------

/**
 * Strip a section dict to only its allowlisted keys, then recursively apply
 * the global denylist to surviving values.
 */
function stripSection(sectionValue, allowlist, nestedHandlers = new Map()) {
  if (!sectionValue || typeof sectionValue !== "object" || Array.isArray(sectionValue)) {
    return sectionValue;
  }
  const stripped = {};
  for (const [key, child] of Object.entries(sectionValue)) {
    const normalized = normalizeKey(key);
    if (isRawField(key)) continue;
    if (!allowlist.has(normalized)) continue;
    const handler = nestedHandlers.get(normalized);
    stripped[key] = handler ? handler(child) : globalStripRawContent(child);
  }
  return stripped;
}

/** Recursively apply global denylist without allowlist enforcement. */
function globalStripRawContent(value) {
  if (Array.isArray(value)) {
    return value.map((item) => globalStripRawContent(item));
  }
  if (value && typeof value === "object") {
    const stripped = {};
    for (const [key, child] of Object.entries(value)) {
      if (isRawField(key)) continue;
      stripped[key] = globalStripRawContent(child);
    }
    return stripped;
  }
  return value;
}

export function stripRawContent(value) {
  if (Array.isArray(value)) {
    return value.map((item) => stripRawContent(item));
  }

  if (!value || typeof value !== "object") return value;

  // The browser SDK sends evaluation requests, so apply the request envelope
  // allowlist at the root before recursing into feature_packet.
  const stripped = {};
  for (const [key, child] of Object.entries(value)) {
    if (isRawField(key)) continue;

    const normalized = normalizeKey(key);
    if (!ALLOWED_REQUEST_FIELDS.has(normalized)) continue;
    stripped[key] =
      normalized === "feature_packet" ? stripFeaturePacket(child) : globalStripRawContent(child);
  }
  return stripped;
}

function stripMetadata(metadata) {
  return stripSection(
    metadata,
    ALLOWED_METADATA_FIELDS,
    new Map([["typing_summary", (value) => stripSection(value, ALLOWED_TYPING_SUMMARY_FIELDS)]]),
  );
}

function stripExternalRiskProvider(items) {
  if (!Array.isArray(items)) return items;
  return items.map((item) => stripSection(item, ALLOWED_EXTERNAL_RISK_PROVIDER_FIELDS));
}

function stripFeaturePacket(packet) {
  if (!packet || typeof packet !== "object" || Array.isArray(packet)) {
    return packet;
  }

  const stripped = {};
  for (const [key, child] of Object.entries(packet)) {
    if (isRawField(key)) continue;

    const normalized = normalizeKey(key);
    if (!ALLOWED_PACKET_FIELDS.has(normalized)) continue;

    const sectionAllowlist = SECTION_ALLOWLISTS.get(normalized);
    if (sectionAllowlist) {
      stripped[key] = stripSection(child, sectionAllowlist);
    } else if (normalized === "metadata") {
      stripped[key] = stripMetadata(child);
    } else if (normalized === "external_risk_provider") {
      stripped[key] = stripExternalRiskProvider(child);
    } else {
      stripped[key] = globalStripRawContent(child);
    }
  }
  return stripped;
}

// ---------------------------------------------------------------------------
// assertPrivacySafePayload
// Client-side assertion: throws on any raw-content field found.
// The server is the authoritative enforcement boundary; this is a
// belt-and-suspenders check before the payload is transmitted.
// ---------------------------------------------------------------------------

export function assertPrivacySafePayload(value, path = "") {
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertPrivacySafePayload(item, `${path}[${index}]`));
    return;
  }

  if (!value || typeof value !== "object") return;

  for (const [key, child] of Object.entries(value)) {
    const childPath = path ? `${path}.${key}` : key;
    if (isRawField(key)) {
      throw new Error(`Raw content field is not allowed in TruePresence payload: ${childPath}`);
    }
    assertPrivacySafePayload(child, childPath);
  }
}

export function cloneJsonSafe(value) {
  return JSON.parse(JSON.stringify(value));
}
