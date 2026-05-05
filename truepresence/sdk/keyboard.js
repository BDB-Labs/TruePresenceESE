let lastKeyTime = null;

export function initKeyboardTracker(sendEvent) {
  document.addEventListener("keydown", (e) => {
    const now = performance.now();
    const interval = lastKeyTime ? now - lastKeyTime : null;
    lastKeyTime = now;
    sendEvent({
      event_type: "key_timing",
      payload: {
        interval_ms: interval,
        is_correction_key: e.key === "Backspace" || e.key === "Delete",
      },
    });
  });
}
