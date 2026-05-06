import { normalizeChallengeFeatures } from "./challenge.js";
import { createPointerSummaryCollector } from "./pointer.js";
import {
  assertPrivacySafePayload,
  cloneJsonSafe,
  isEligibleField,
  stripRawContent,
} from "./privacy.js";
import { createTypingCadenceCollector } from "./typing.js";

const SDK_VERSION = "0.2.0";

export class TruePresenceSDKError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "TruePresenceSDKError";
    this.code = code;
    this.details = details;
  }
}

function defaultNow() {
  if (globalThis.performance?.now) {
    return globalThis.performance.now();
  }
  return Date.now();
}

function randomSessionId() {
  const random =
    globalThis.crypto?.randomUUID?.() ||
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `tp_sess_${random}`;
}

function sessionStorageFor(win) {
  try {
    return win?.sessionStorage || null;
  } catch {
    return null;
  }
}

function sessionIdFor(siteKey, win) {
  const storage = sessionStorageFor(win);
  const key = `truepresence:${siteKey}:session_id`;
  if (storage) {
    const existing = storage.getItem(key);
    if (existing) return existing;
  }
  const created = randomSessionId();
  if (storage) {
    storage.setItem(key, created);
  }
  return created;
}

function resolveDocument(config) {
  return config.document || globalThis.document;
}

function resolveWindow(config) {
  return config.window || globalThis.window || globalThis;
}

function resolveFetch(config) {
  const fetchFn = config.fetch || globalThis.fetch;
  return typeof fetchFn === "function" ? fetchFn.bind(globalThis) : null;
}

function pageContext(win, doc) {
  return {
    hostname: win?.location?.hostname || undefined,
    pathname: win?.location?.pathname || undefined,
    referrer_present: Boolean(doc?.referrer),
    visibility_state: doc?.visibilityState || undefined,
  };
}

function environmentFeatures(win, doc) {
  return {
    automation_framework_hint: Boolean(win?._phantom || win?.callPhantom),
    headless_browser_hint: Boolean(win?.navigator?.webdriver),
    reduced_motion_enabled: Boolean(win?.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches),
    timezone_offset_minutes: new Date().getTimezoneOffset(),
    viewport_height: win?.innerHeight,
    viewport_width: win?.innerWidth,
    webdriver_detected: Boolean(win?.navigator?.webdriver),
  };
}

function mean(values) {
  if (!values.length) return undefined;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function stddev(values) {
  if (values.length < 2) return 0;
  const avg = mean(values);
  const variance = mean(values.map((value) => (value - avg) ** 2));
  return Math.sqrt(variance);
}

function actionBurstFeatures(actionTimestamps, startedAt) {
  const sorted = [...new Set(actionTimestamps)]
    .filter((timestamp) => Number.isFinite(timestamp))
    .sort((a, b) => a - b);
  if (!sorted.length) {
    return {
      action_burst_count: 0,
      burst_interval_stddev_ms: undefined,
      idle_to_action_latency_ms: undefined,
      mean_burst_interval_ms: undefined,
    };
  }

  const burstStarts = [];
  let currentBurstStart = sorted[0];
  let currentBurstSize = 1;
  for (let index = 1; index < sorted.length; index += 1) {
    const gap = sorted[index] - sorted[index - 1];
    if (gap <= 250) {
      currentBurstSize += 1;
      continue;
    }
    if (currentBurstSize >= 2) {
      burstStarts.push(currentBurstStart);
    }
    currentBurstStart = sorted[index];
    currentBurstSize = 1;
  }
  if (currentBurstSize >= 2) {
    burstStarts.push(currentBurstStart);
  }

  const burstIntervals = [];
  for (let index = 1; index < burstStarts.length; index += 1) {
    burstIntervals.push(burstStarts[index] - burstStarts[index - 1]);
  }

  return {
    action_burst_count: burstStarts.length,
    burst_interval_stddev_ms: burstIntervals.length ? stddev(burstIntervals) : undefined,
    idle_to_action_latency_ms: sorted[0] - startedAt,
    mean_burst_interval_ms: mean(burstIntervals),
  };
}

function agenticFeatures({ pointerAgentic, startedAt, typingAgentic }) {
  const actionTimestamps = [
    ...(typingAgentic?._action_timestamps || []),
    ...(pointerAgentic?._action_timestamps || []),
  ];
  return {
    ...actionBurstFeatures(actionTimestamps, startedAt),
    exploratory_action_count: pointerAgentic?.exploratory_action_count,
    large_instant_delta_count: typingAgentic?.large_instant_delta_count,
    route_directness_score: pointerAgentic?.route_directness_score,
    structured_retry_count: typingAgentic?.structured_retry_count,
    submit_after_instant_input_ms: typingAgentic?.submit_after_instant_input_ms,
    validation_repair_count: typingAgentic?.validation_repair_count,
  };
}

function pruneUndefined(value) {
  if (Array.isArray(value)) {
    return value.map(pruneUndefined);
  }
  if (value && typeof value === "object") {
    const pruned = {};
    for (const [key, child] of Object.entries(value)) {
      if (child === undefined || child === null) continue;
      pruned[key] = pruneUndefined(child);
    }
    return pruned;
  }
  return value;
}

export class TruePresenceBrowserSDK {
  constructor() {
    this.config = null;
    this.document = null;
    this.fetchFn = null;
    this.focusBlurCount = 0;
    this.forms = new Set();
    this.initialized = false;
    this.now = defaultNow;
    this.pointerCollector = null;
    this.sessionId = null;
    this.startedAt = null;
    this.typingCollector = null;
    this.window = null;
  }

  init(config = {}) {
    if (!config.siteKey) {
      throw new TruePresenceSDKError("missing_site_key", "TruePresence.init requires siteKey.");
    }
    if (!config.endpoint) {
      throw new TruePresenceSDKError("missing_endpoint", "TruePresence.init requires endpoint.");
    }
    if (config.captureContent === true) {
      throw new TruePresenceSDKError(
        "capture_content_unsupported",
        "captureContent:true is not supported by the privacy-preserving browser SDK.",
      );
    }

    this.document = resolveDocument(config);
    this.window = resolveWindow(config);
    this.fetchFn = resolveFetch(config);
    this.now = config.now || defaultNow;
    this.startedAt = this.now();
    this.sessionId = config.sessionId || sessionIdFor(config.siteKey, this.window);
    this.config = {
      captureContent: false,
      debug: false,
      enforcementMode: "observe",
      mode: "privacy_preserving",
      tenantId: "default",
      ...config,
      captureContent: false,
      mode: "privacy_preserving",
    };

    this.typingCollector = createTypingCadenceCollector({ now: this.now });
    this.pointerCollector = createPointerSummaryCollector({
      document: this.document,
      now: this.now,
    });
    this.pointerCollector.start();
    this.window?.addEventListener?.("focus", () => {
      this.focusBlurCount += 1;
    });
    this.window?.addEventListener?.("blur", () => {
      this.focusBlurCount += 1;
    });
    this.document?.addEventListener?.("visibilitychange", () => {
      this.focusBlurCount += 1;
    });

    this.initialized = true;
    return this;
  }

  protectForm(selector, options = {}) {
    this.#requireInitialized();
    const form = typeof selector === "string" ? this.document?.querySelector?.(selector) : selector;
    if (!form) {
      throw new TruePresenceSDKError("form_not_found", "TruePresence.protectForm target was not found.", {
        selector,
      });
    }

    const fields = Array.from(form.querySelectorAll?.("input, textarea, select") || []).filter(
      isEligibleField,
    );
    const promptRenderAt = this.now();
    for (const field of fields) {
      const mode = field?.dataset?.truepresence;
      const isChallenge = mode === "challenge" || options.challenge === "typing_cadence";
      this.typingCollector.trackField(field, {
        challengeType: options.challenge || "typing_cadence",
        expectedReadingTimeMs: options.expectedReadingTimeMs,
        isChallenge,
        promptRenderAt,
      });
    }

    form.addEventListener?.("submit", () => {
      this.typingCollector.markSubmit();
      if (options.evaluateOnSubmit !== false) {
        void this.evaluate({ reason: "submit" });
      }
    });

    this.forms.add(form);
    return { form, trackedFields: fields.length };
  }

  getFeatureSnapshot() {
    this.#requireInitialized();
    return this.#featurePacket();
  }

  buildEvaluationPayload() {
    this.#requireInitialized();
    const payload = {
      enforcement_mode: this.config.enforcementMode,
      session_id: this.sessionId,
      tenant_id: this.config.tenantId,
      feature_packet: this.#featurePacket(),
    };

    const safeBasePayload = pruneUndefined(stripRawContent(payload));
    assertPrivacySafePayload(safeBasePayload);

    let candidate = safeBasePayload;
    if (typeof this.config.beforeSend === "function") {
      candidate = this.config.beforeSend(cloneJsonSafe(safeBasePayload)) || safeBasePayload;
    }

    const safePayload = pruneUndefined(stripRawContent(candidate));
    assertPrivacySafePayload(safePayload);
    return safePayload;
  }

  async evaluate() {
    this.#requireInitialized();
    const payload = this.buildEvaluationPayload();
    if (!this.fetchFn) {
      return this.#handleError("fetch_unavailable", "No fetch implementation is available.");
    }

    try {
      const response = await this.fetchFn(this.config.endpoint, {
        body: JSON.stringify(payload),
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const parsed = await response.json();
      if (!response.ok) {
        return this.#handleError("http_error", "TruePresence evaluation endpoint returned an error.", {
          payload: parsed,
          status: response.status,
        });
      }
      if (typeof this.config.onEvaluation === "function") {
        this.config.onEvaluation(parsed);
      }
      return parsed;
    } catch (error) {
      return this.#handleError("network_error", "TruePresence evaluation request failed.", {
        cause: error instanceof Error ? error.message : String(error),
      });
    }
  }

  #featurePacket() {
    const typingSnapshot = this.typingCollector.summarize(this.now());
    const challenge = normalizeChallengeFeatures(typingSnapshot.challenge);
    const pointer = this.pointerCollector.summarize();
    const pointerAgentic = this.pointerCollector.summarizeAgentic();
    return pruneUndefined({
      agentic: agenticFeatures({
        pointerAgentic,
        startedAt: this.startedAt,
        typingAgentic: typingSnapshot.agentic,
      }),
      challenge,
      environment: environmentFeatures(this.window, this.document),
      metadata: {
        mode: this.config.mode,
        sdk_version: SDK_VERSION,
        tracked_field_count: this.typingCollector.trackedCount(),
        typing_summary: typingSnapshot.typingSummary,
      },
      page_context: pageContext(this.window, this.document),
      pointer,
      session_continuity: {
        focus_blur_count: this.focusBlurCount,
        session_age_ms: this.now() - this.startedAt,
      },
      session_id: this.sessionId,
      site_id: this.config.siteKey,
      surface: "web",
      tenant_id: this.config.tenantId,
      typing: typingSnapshot.typing,
    });
  }

  #handleError(code, message, details = {}) {
    const error = { code, details, message };
    if (typeof this.config?.onError === "function") {
      this.config.onError(error);
    }
    if (this.config?.debug && globalThis.console?.warn) {
      globalThis.console.warn("TruePresence SDK error", error);
    }
    return { error, ok: false, session_id: this.sessionId };
  }

  #requireInitialized() {
    if (!this.initialized) {
      throw new TruePresenceSDKError("not_initialized", "Call TruePresence.init before using the SDK.");
    }
  }
}

export const TruePresence = {
  create() {
    return new TruePresenceBrowserSDK();
  },
  init(config) {
    return defaultInstance.init(config);
  },
  protectForm(selector, options) {
    return defaultInstance.protectForm(selector, options);
  },
  evaluate() {
    return defaultInstance.evaluate();
  },
  getFeatureSnapshot() {
    return defaultInstance.getFeatureSnapshot();
  },
  buildEvaluationPayload() {
    return defaultInstance.buildEvaluationPayload();
  },
};

const defaultInstance = new TruePresenceBrowserSDK();

export function initTruePresence(config) {
  return TruePresence.init(config);
}

if (globalThis.window && !globalThis.window.TruePresence) {
  globalThis.window.TruePresence = TruePresence;
}
