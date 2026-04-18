/**
 * TruePresence JavaScript SDK
 * 
 * This SDK provides a simple JavaScript client for integrating TruePresence
 * bot detection into web and Node.js applications.
 * 
 * Usage:
 * import { TruePresenceClient } from 'truepresence-sdk';
 * 
 * const client = new TruePresenceClient({ apiUrl: 'http://localhost:8000' });
 * const sessionId = await client.createSession();
 * 
 * const result = await client.evaluate({
 *   sessionId,
 *   event: {
 *     eventType: 'key_timing',
 *     timestamp: Date.now(),
 *     payload: { intervalMs: 120 }
 *   }
 * });
 * 
 * if (result.decision === 'block') {
 *   console.log('Bot detected!');
 * }
 */

class TruePresenceClient {
  /**
   * Initialize TruePresence client
   * @param {Object} options - Configuration options
   * @param {string} options.apiUrl - Base URL of the TruePresence API
   * @param {number} options.timeout - Request timeout in ms
   * @param {string} options.mode - Default mode (sdk or gatekeeper)
   */
  constructor(options = {}) {
    this.apiUrl = options.apiUrl || 'http://localhost:8000';
    this.timeout = options.timeout || 30000;
    this.mode = options.mode || 'sdk';
    this.sessionId = null;
  }

  /**
   * Create a new session
   * @param {string} assuranceLevel - Assurance level (A1-A4)
   * @returns {Promise<string>} Session ID
   */
  async createSession(assuranceLevel = 'A1') {
    const response = await this._request('/session/create', {
      method: 'POST',
      body: JSON.stringify({ assurance_level: assuranceLevel })
    });
    this.sessionId = response.session_id;
    return this.sessionId;
  }

  /**
   * Evaluate an event for bot detection
   * @param {Object} options - Evaluation options
   * @param {string} options.sessionId - Session ID
   * @param {string} options.eventType - Type of event
   * @param {number} options.timestamp - Unix timestamp
   * @param {Object} options.payload - Event payload
   * @param {Object} options.features - Behavioral features
   * @param {Object} options.context - Additional context
   * @param {string} options.mode - Evaluation mode
   * @returns {Promise<Object>} Evaluation result
   */
  async evaluate(options = {}) {
    const sessionId = options.sessionId || this.sessionId;
    if (!sessionId) {
      throw new Error('No session ID provided. Call createSession() first.');
    }

    const event = {
      event_type: options.eventType || 'unknown',
      timestamp: options.timestamp || Date.now(),
      payload: options.payload || {}
    };

    if (options.features) {
      event.features = options.features;
    }

    const requestData = {
      mode: options.mode || this.mode,
      session_id: sessionId,
      event
    };

    if (options.context) {
      requestData.context = options.context;
    }

    return this._request('/v1/evaluate', {
      method: 'POST',
      body: JSON.stringify(requestData)
    });
  }

  /**
   * Evaluate a stream of events
   * @param {string} sessionId - Session ID
   * @param {Array} events - Array of event objects
   * @returns {Promise<Array>} Array of evaluation results
   */
  async evaluateStream(sessionId, events) {
    const results = [];
    for (const event of events) {
      const result = await this.evaluate({
        sessionId,
        eventType: event.eventType,
        timestamp: event.timestamp,
        payload: event.payload,
        features: event.features
      });
      results.push(result);
    }
    return results;
  }

  /**
   * Quick check if session is likely a bot
   * @param {string} sessionId - Session ID
   * @param {number} threshold - Bot probability threshold (0-1)
   * @returns {Promise<boolean>} True if likely bot
   */
  async checkBot(sessionId, threshold = 0.5) {
    const result = await this.evaluate({ sessionId });
    return (result.bot_probability || 0) > threshold;
  }

  /**
   * Get connected sessions from identity graph
   * @param {string} sessionId - Session ID to query
   * @returns {Promise<Array>} Array of connected session IDs
   */
  async getSessionCluster(sessionId) {
    const response = await this._request(`/v1/sessions/${sessionId}/cluster`);
    return response.cluster || [];
  }

  /**
   * Reset session memory
   * @param {string} sessionId - Session ID to reset
   * @returns {Promise<boolean>} True if successful
   */
  async resetSession(sessionId) {
    const response = await this._request(`/v1/sessions/${sessionId}/reset`, {
      method: 'POST'
    });
    return response.status === 'reset';
  }

  /**
   * Check API health
   * @returns {Promise<Object>} Health status
   */
  async healthCheck() {
    return this._request('/health');
  }

  /**
   * Internal request handler
   * @private
   */
  async _request(endpoint, options = {}) {
    const url = `${this.apiUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal
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

/**
 * Quick bot check for a single event
 * @param {Object} event - Event object
 * @param {string} apiUrl - API URL
 * @returns {Promise<boolean>} True if likely bot
 */
async function quickCheck(event, apiUrl = 'http://localhost:8000') {
  const client = new TruePresenceClient({ apiUrl });
  const sessionId = await client.createSession();
  const result = await client.evaluate({
    sessionId,
    eventType: event.eventType,
    timestamp: event.timestamp,
    payload: event.payload,
    features: event.features
  });
  return result.decision === 'block';
}

// Export for different environments
if (typeof module !== 'undefined' && module.exports) {
  // Node.js
  module.exports = { TruePresenceClient, quickCheck };
} else if (typeof window !== 'undefined') {
  // Browser
  window.TruePresenceClient = TruePresenceClient;
  window.truepresenceQuickCheck = quickCheck;
}

// ES Module export
export { TruePresenceClient, quickCheck };
export default TruePresenceClient;
