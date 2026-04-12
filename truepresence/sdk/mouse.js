let lastMove = null;

export function initMouseTracker(sendEvent) {
  document.addEventListener("mousemove", (e) => {
    const now = performance.now();
    const delta = lastMove
      ? { dx: e.clientX - lastMove.x, dy: e.clientY - lastMove.y, dt: now - lastMove.t }
      : null;
    lastMove = { x: e.clientX, y: e.clientY, t: now };
    sendEvent({ event_type: "cursor_move", payload: delta });
  });
}
