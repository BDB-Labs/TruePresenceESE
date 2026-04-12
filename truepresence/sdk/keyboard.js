let lastKeyTime = null;

export function initKeyboardTracker(sendEvent) {
  document.addEventListener("keydown", (e) => {
    const now = performance.now();
    const interval = lastKeyTime ? now - lastKeyTime : null;
    lastKeyTime = now;
    sendEvent({
      event_type: "key_timing",
      payload: { key: e.key, interval_ms: interval },
    });
  });
}
