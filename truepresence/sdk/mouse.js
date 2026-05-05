let movementCount = 0;
let lastEmit = 0;

export function initMouseTracker(sendEvent) {
  document.addEventListener("mousemove", (e) => {
    const now = performance.now();
    movementCount += 1;
    if (movementCount % 20 === 0 || now - lastEmit > 1000) {
      lastEmit = now;
      sendEvent({
        event_type: "pointer_summary",
        payload: { pointer_movement_count: movementCount },
      });
    }
  });
}
