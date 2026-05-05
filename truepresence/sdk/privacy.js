const DISALLOWED_RAW_FIELDS = new Set([
  "text",
  "raw_text",
  "rawtext",
  "typed_text",
  "typedtext",
  "value",
  "keys",
  "key_values",
  "keyvalues",
  "key",
  "password",
  "card_number",
  "cardnumber",
  "ssn",
  "message_body",
  "messagebody",
  "freeform_content",
  "freeformcontent",
]);

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

function isRawField(key) {
  const normalized = normalizeKey(key);
  return DISALLOWED_RAW_FIELDS.has(normalized);
}

export function stripRawContent(value) {
  if (Array.isArray(value)) {
    return value.map((item) => stripRawContent(item));
  }

  if (value && typeof value === "object") {
    const stripped = {};
    for (const [key, child] of Object.entries(value)) {
      if (isRawField(key)) continue;
      stripped[key] = stripRawContent(child);
    }
    return stripped;
  }

  return value;
}

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
