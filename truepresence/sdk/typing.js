function safeNow(now) {
  return typeof now === "function" ? now() : Date.now();
}

function numeric(value) {
  return Number.isFinite(value) ? value : undefined;
}

function mean(values) {
  if (!values.length) return undefined;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function stddev(values) {
  if (values.length < 2) return 0;
  const avg = mean(values);
  const variance = mean(values.map((value) => (value - avg) ** 2));
  return Math.sqrt(variance);
}

function lengthOfFieldValue(field) {
  return String(field?.value ?? "").length;
}

function dataValue(field, key) {
  return field?.dataset?.[key];
}

export function createTypingCadenceCollector({ now }) {
  const fieldStates = new WeakMap();
  const trackedFields = [];
  let submitAt = null;

  function ensureState(field, options = {}) {
    let state = fieldStates.get(field);
    if (!state) {
      state = {
        correctionCount: 0,
        deleteKeyCount: 0,
        firstInputAt: null,
        focusAt: null,
        inputEventCount: 0,
        intervals: [],
        isChallenge: Boolean(options.isChallenge),
        lastInputAt: null,
        lastKeyAt: null,
        lastLength: null,
        pasteCount: 0,
        promptRenderAt: options.promptRenderAt ?? safeNow(now),
        totalInsertedLength: 0,
        challengeType: options.challengeType || "typing_cadence",
        expectedReadingTimeMs:
          options.expectedReadingTimeMs ??
          (Number(dataValue(field, "truepresenceExpectedReadingMs")) || undefined),
      };
      fieldStates.set(field, state);
      trackedFields.push(field);
    }
    return state;
  }

  function trackField(field, options = {}) {
    const state = ensureState(field, options);

    field.addEventListener("focus", () => {
      state.focusAt = safeNow(now);
      if (state.lastLength === null) {
        state.lastLength = lengthOfFieldValue(field);
      }
    });

    field.addEventListener("keydown", (event) => {
      const timestamp = safeNow(now);
      if (state.lastKeyAt !== null) {
        state.intervals.push(timestamp - state.lastKeyAt);
      }
      state.lastKeyAt = timestamp;
      if (event.key === "Backspace" || event.key === "Delete") {
        state.deleteKeyCount += 1;
        state.correctionCount += 1;
      }
    });

    field.addEventListener("paste", () => {
      state.pasteCount += 1;
    });

    field.addEventListener("input", () => {
      const timestamp = safeNow(now);
      const length = lengthOfFieldValue(field);
      const previousLength = state.lastLength;
      state.inputEventCount += 1;
      if (state.firstInputAt === null) {
        state.firstInputAt = timestamp;
      }
      state.lastInputAt = timestamp;

      if (previousLength !== null) {
        const delta = length - previousLength;
        if (delta > 0) {
          state.totalInsertedLength += delta;
        } else if (delta < 0) {
          state.correctionCount += 1;
        }
      }
      state.lastLength = length;
    });

    return state;
  }

  function markSubmit() {
    submitAt = safeNow(now);
  }

  function summarize(currentNow = safeNow(now)) {
    const aggregate = {
      correctionCount: 0,
      deleteKeyCount: 0,
      firstFocusAt: null,
      firstInputAt: null,
      inputEventCount: 0,
      intervals: [],
      lastInputAt: null,
      pasteCount: 0,
      promptRenderAt: null,
      totalInsertedLength: 0,
    };
    const challenge = {
      firstInputAt: null,
      inputCount: 0,
      promptRenderAt: null,
      expectedReadingTimeMs: undefined,
      challengeType: "typing_cadence",
    };

    for (const field of trackedFields) {
      const state = fieldStates.get(field);
      if (!state) continue;

      aggregate.correctionCount += state.correctionCount;
      aggregate.deleteKeyCount += state.deleteKeyCount;
      aggregate.inputEventCount += state.inputEventCount;
      aggregate.intervals.push(...state.intervals);
      aggregate.pasteCount += state.pasteCount;
      aggregate.totalInsertedLength += state.totalInsertedLength;

      if (state.focusAt !== null && (aggregate.firstFocusAt === null || state.focusAt < aggregate.firstFocusAt)) {
        aggregate.firstFocusAt = state.focusAt;
      }
      if (state.firstInputAt !== null && (aggregate.firstInputAt === null || state.firstInputAt < aggregate.firstInputAt)) {
        aggregate.firstInputAt = state.firstInputAt;
      }
      if (state.lastInputAt !== null && (aggregate.lastInputAt === null || state.lastInputAt > aggregate.lastInputAt)) {
        aggregate.lastInputAt = state.lastInputAt;
      }
      if (
        state.promptRenderAt !== null &&
        (aggregate.promptRenderAt === null || state.promptRenderAt < aggregate.promptRenderAt)
      ) {
        aggregate.promptRenderAt = state.promptRenderAt;
      }

      if (state.isChallenge) {
        challenge.inputCount += state.inputEventCount;
        challenge.expectedReadingTimeMs =
          challenge.expectedReadingTimeMs ?? state.expectedReadingTimeMs;
        challenge.challengeType = state.challengeType || challenge.challengeType;
        if (challenge.promptRenderAt === null || state.promptRenderAt < challenge.promptRenderAt) {
          challenge.promptRenderAt = state.promptRenderAt;
        }
        if (
          state.firstInputAt !== null &&
          (challenge.firstInputAt === null || state.firstInputAt < challenge.firstInputAt)
        ) {
          challenge.firstInputAt = state.firstInputAt;
        }
      }
    }

    const durationMs =
      aggregate.firstInputAt !== null && aggregate.lastInputAt !== null
        ? Math.max(0, aggregate.lastInputAt - aggregate.firstInputAt)
        : undefined;
    const charactersPerMinute =
      durationMs && durationMs > 0
        ? (aggregate.totalInsertedLength / durationMs) * 60000
        : undefined;
    const intervalMean = mean(aggregate.intervals);
    const intervalStddev = stddev(aggregate.intervals);
    const minInterval = aggregate.intervals.length ? Math.min(...aggregate.intervals) : undefined;
    const maxInterval = aggregate.intervals.length ? Math.max(...aggregate.intervals) : undefined;
    const correctionRate =
      aggregate.inputEventCount > 0 ? aggregate.correctionCount / aggregate.inputEventCount : 0;

    const typing = {
      mean_inter_key_interval_ms: numeric(intervalMean),
      inter_key_interval_stddev_ms: numeric(intervalStddev),
      characters_per_minute: numeric(charactersPerMinute),
      correction_count: aggregate.correctionCount,
      correction_rate: correctionRate,
      paste_count: aggregate.pasteCount,
      focus_to_first_input_ms:
        aggregate.firstFocusAt !== null && aggregate.firstInputAt !== null
          ? aggregate.firstInputAt - aggregate.firstFocusAt
          : undefined,
      prompt_render_to_first_input_ms:
        aggregate.promptRenderAt !== null && aggregate.firstInputAt !== null
          ? aggregate.firstInputAt - aggregate.promptRenderAt
          : undefined,
      typing_duration_ms: numeric(durationMs),
    };

    const typingSummary = {
      delete_key_count: aggregate.deleteKeyCount,
      input_event_count: aggregate.inputEventCount,
      last_input_to_submit_ms:
        submitAt !== null && aggregate.lastInputAt !== null ? submitAt - aggregate.lastInputAt : undefined,
      max_inter_key_interval_ms: numeric(maxInterval),
      min_inter_key_interval_ms: numeric(minInterval),
      tracked_field_count: trackedFields.length,
    };

    const challengeSummary =
      challenge.inputCount > 0
        ? {
            challenge_type: challenge.challengeType,
            expected_reading_time_ms: numeric(challenge.expectedReadingTimeMs),
            prompt_render_to_first_input_ms:
              challenge.promptRenderAt !== null && challenge.firstInputAt !== null
                ? challenge.firstInputAt - challenge.promptRenderAt
                : undefined,
            response_latency_ms:
              challenge.promptRenderAt !== null ? currentNow - challenge.promptRenderAt : undefined,
            challenge_duration_ms:
              challenge.promptRenderAt !== null ? currentNow - challenge.promptRenderAt : undefined,
          }
        : null;

    return { challenge: challengeSummary, typing, typingSummary };
  }

  return {
    markSubmit,
    summarize,
    trackField,
    trackedCount: () => trackedFields.length,
  };
}
