export function initClipboardTracker(sendEvent) {
  document.addEventListener("paste", () => {
    sendEvent({ event_type: "clipboard", payload: { pasted: true } });
  });
}
