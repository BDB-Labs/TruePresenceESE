/**
 * TruePresence JavaScript SDK
 *
 * Provides a JavaScript client for integrating TruePresence bot detection into web and Node.js applications.
 *
 * REST routes are mounted at `/api` on the TruePresence server. Pass either `apiOrigin` (server root,
 * e.g. http://localhost:8000) or `apiUrl`/`restBaseUrl` ending in `/api`. When `TRUEPRESENCE_LEGACY_REST_TOKEN`
 * is set on the server, pass the same value as `serviceToken` for legacy REST calls.
 */

class TruePresenceClient {
  /**
   * @param {Object} options
   * @param {string} [options.apiOrigin] - Server origin without /api (e.g. http://localhost:8000)
   * @param {string} [options.apiUrl] - Alias for apiOrigin; may end with /api (normalized)
   * @param {string} [options.restBaseUrl] - Full REST prefix including /api (overrides derived base)
   * @param {string} [options.serviceToken] - Matches server TRUEPRESENCE_LEGACY_REST_TOKEN for legacy REST
   * @param {number} [options.timeout]
   * @param {string} [options.mode]
   */
  constructor(options = {}) {
    const rawUrl = options.apiUrl || options.apiOrigin || "http://localhost:8000";
    const trimmed = rawUrl.replace(/\/$/, "");
    const endsWithApi = trimmed.endsWith("/api");
    this.apiOrigin = endsWithApi ? trimmed.slice(0, -4) || trimmed : trimmed;
    this.restBase =
      options.restBaseUrl || (endsWithApi ? trimmed : `${trimmed}/api`);
    this.serviceToken =
      options.serviceToken || options.legacyRestToken || null;
    this.timeout = options.timeout || 30000;
    this.mode = options.mode || "sdk";
    this.sessionId = null;
  }

  _serviceHeaders() {
    if (!this.serviceToken) return {};
    return { "X-TruePresence-Service-Token": this.serviceToken };
  }

  /**
   * @param {string} assuranceLevel
   * @returns {Promise<string>}
   */
  async createSession(assuranceLevel = "A1") {
    const response = await this._request("/session/create", {
      method: "POST",
      body: JSON.stringify({ assurance_level: assuranceLevel }),
    });
    this.sessionId = response.session_id;
    return this.sessionId;
  }

  /**
   * @param {Object} options
   * @returns {Promise<Object>}
   */
  async evaluate(options = {}) {
    const sessionId = options.sessionId || this.sessionId;
    if (!sessionId) {
      throw new Error("No session ID provided. Call createSession() first.");
    }

    const event = {
      event_type: options.eventType || "unknown",
      timestamp: options.timestamp || Date.now(),
      payload: options.payload || {},
    };

    if (options.features) {
      event.features = options.features;
    }

    const requestData = {
      mode: options.mode || this.mode,
      session_id: sessionId,
      event,
    };

    if (options.context) {
      requestData.context = options.context;
    }

    return this._request("/v1/evaluate", {
      method: "POST",
      body: JSON.stringify(requestData),
    });
  }

  async evaluateStream(sessionId, events) {
    const results = [];
    for (const event of events || []) {
      const result = await this.evaluate({
        sessionId,
        eventType: event.eventType,
        timestamp: event.timestamp,
        payload: event.payload,
        features: event.features,
      });
      results.push(result);
    }
    return results;
  }

  async checkBot(sessionId, threshold = 0.5) {
    const result = await this.evaluate({ sessionId });
    return (result.bot_probability || 0) > threshold;
  }

  async getSessionCluster(sessionId) {
    const response = await this._request(`/v1/sessions/${sessionId}/cluster`);
    return response.cluster || [];
  }

  async resetSession(sessionId) {
    const response = await this._request(`/v1/sessions/${sessionId}/reset`, {
      method: "POST",
    });
    return response.status === "reset";
  }

  async healthCheck() {
    const url = `${this.apiOrigin}/health`;
    const headers = {
      "Content-Type": "application/json",
      ...this._serviceHeaders(),
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: "GET",
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      throw new Error(`TruePresence API error: ${error.message}`);
    }
  }

  async _request(endpoint, options = {}) {
    const url = `${this.restBase}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...this._serviceHeaders(),
      ...options.headers,
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      throw new Error(`TruePresence API error: ${error.message}`);
    }
  }
}

async function quickCheck(event, apiUrl = "http://localhost:8000") {
  const client = new TruePresenceClient({ apiUrl });
  const sessionId = await client.createSession();
  const result = await client.evaluate({
    sessionId,
    eventType: event.eventType,
    timestamp: event.timestamp,
    payload: event.payload,
    features: event.features,
  });
  return result.decision === "block";
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { TruePresenceClient, quickCheck };
} else if (typeof window !== "undefined") {
  window.TruePresenceClient = TruePresenceClient;
  window.truepresenceQuickCheck = quickCheck;
}

export { TruePresenceClient, quickCheck };
export default TruePresenceClient;
