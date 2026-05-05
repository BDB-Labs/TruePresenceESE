function safeNow(now) {
  return typeof now === "function" ? now() : Date.now();
}

function shannonEntropy(counts) {
  const total = counts.reduce((sum, count) => sum + count, 0);
  if (!total) return 0;
  const entropy = counts.reduce((sum, count) => {
    if (!count) return sum;
    const probability = count / total;
    return sum - probability * Math.log2(probability);
  }, 0);
  return entropy / Math.log2(counts.length);
}

export function createPointerSummaryCollector({ document, now }) {
  let clickCount = 0;
  let clickHesitationTotal = 0;
  let clickHesitationCount = 0;
  let lastMove = null;
  let lastMoveAt = null;
  let movementCount = 0;
  let scrollCount = 0;
  let lastScrollAt = null;
  const directionBins = new Array(8).fill(0);
  const scrollIntervals = [];

  function onMove(event) {
    const timestamp = safeNow(now);
    movementCount += 1;
    if (lastMove) {
      const dx = Number(event.clientX || 0) - lastMove.x;
      const dy = Number(event.clientY || 0) - lastMove.y;
      if (dx || dy) {
        const angle = Math.atan2(dy, dx);
        const normalized = angle < 0 ? angle + Math.PI * 2 : angle;
        const bin = Math.min(7, Math.floor((normalized / (Math.PI * 2)) * 8));
        directionBins[bin] += 1;
      }
    }
    lastMove = {
      x: Number(event.clientX || 0),
      y: Number(event.clientY || 0),
    };
    lastMoveAt = timestamp;
  }

  function onClick() {
    const timestamp = safeNow(now);
    clickCount += 1;
    if (lastMoveAt !== null) {
      clickHesitationTotal += Math.max(0, timestamp - lastMoveAt);
      clickHesitationCount += 1;
    }
  }

  function onScroll() {
    const timestamp = safeNow(now);
    scrollCount += 1;
    if (lastScrollAt !== null) {
      scrollIntervals.push(timestamp - lastScrollAt);
    }
    lastScrollAt = timestamp;
  }

  function start() {
    document?.addEventListener?.("pointermove", onMove);
    document?.addEventListener?.("mousemove", onMove);
    document?.addEventListener?.("click", onClick);
    document?.addEventListener?.("scroll", onScroll);
  }

  function stop() {
    document?.removeEventListener?.("pointermove", onMove);
    document?.removeEventListener?.("mousemove", onMove);
    document?.removeEventListener?.("click", onClick);
    document?.removeEventListener?.("scroll", onScroll);
  }

  function summarize() {
    const meanClickHesitation =
      clickHesitationCount > 0 ? clickHesitationTotal / clickHesitationCount : undefined;
    const scrollCadenceScore =
      scrollIntervals.length > 1 ? Math.min(1, scrollIntervals.length / (scrollCount || 1)) : undefined;

    return {
      click_count: clickCount,
      click_hesitation_ms: meanClickHesitation,
      pointer_entropy: shannonEntropy(directionBins),
      pointer_movement_count: movementCount,
      scroll_cadence_score: scrollCadenceScore,
    };
  }

  return { start, stop, summarize };
}
