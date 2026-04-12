import { initKeyboardTracker } from "./keyboard.js";
import { initMouseTracker } from "./mouse.js";
import { initFocusTracker } from "./focus.js";
import { initClipboardTracker } from "./clipboard.js";

export function initTruePresence(config) {
  const sessionId = crypto.randomUUID();
  const ws = new WebSocket(`${config.wsEndpoint.replace(/\/$/, "")}/ws/${sessionId}`);

  ws.onmessage = (msg) => {
    const data = JSON.parse(msg.data);
    if (data.type === "trust_update" && config.onUpdate) {
      config.onUpdate(data.data);
    }
    if (data.type === "challenge" && config.onChallenge) {
      config.onChallenge(data.challenge);
    }
  };

  function sendEvent(event) {
    ws.send(JSON.stringify({
      session_id: sessionId,
      timestamp: Date.now(),
      ...event,
    }));
  }

  initKeyboardTracker(sendEvent);
  initMouseTracker(sendEvent);
  initFocusTracker(sendEvent);
  initClipboardTracker(sendEvent);

  return { sessionId, sendEvent, ws };
}
