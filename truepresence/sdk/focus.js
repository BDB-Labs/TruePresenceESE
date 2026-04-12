export function initFocusTracker(sendEvent) {
  window.addEventListener("blur", () => {
    sendEvent({ event_type: "blur", payload: {} });
  });
  window.addEventListener("focus", () => {
    sendEvent({ event_type: "focus", payload: {} });
  });
}
