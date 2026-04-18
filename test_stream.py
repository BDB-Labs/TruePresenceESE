#!/usr/bin/env python3
"""Simple TruePresence test without server dependencies"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Test the streaming evaluator
print("=== TruePresence Stream Evaluator Test ===\n")

from truepresence.ese_stream import evaluate_incremental, rolling_window  # noqa: E402

# Simulate a session with normal typing
session_id = "test-session-001"

print("Test 1: Simulate human typing (10 keystrokes)")
for i in range(10):
    result = evaluate_incremental(session_id, {
        "event_type": "key_timing",
        "payload": {"interval_ms": 80 + (i % 20)}
    })
print(f"  Score: {result['live_score']} | Decision: {result['decision']}")
print(f"  Signals: liveness={result['signals']['liveness']:.2f}, ai_med={result['signals']['ai_mediation']:.2f}")

# Reset
rolling_window.clear()

print("\nTest 2: Simulate AI-mediated paste")
for _i in range(5):
    result = evaluate_incremental(session_id, {
        "event_type": "clipboard",
        "payload": {"pasted": True}
    })
print(f"  Score: {result['live_score']} | Decision: {result['decision']}")
print(f"  Signals: liveness={result['signals']['liveness']:.2f}, ai_med={result['signals']['ai_mediation']:.2f}")

# Reset
rolling_window.clear()

print("\nTest 3: New session with low activity (relay suspicion)")
result = evaluate_incremental(session_id, {
    "event_type": "key_timing",
    "payload": {"interval_ms": 50}
})
print(f"  Score: {result['live_score']} | Decision: {result['decision']}")
print(f"  Signals: relay_risk={result['signals']['relay_risk']:.2f}")

# Reset
rolling_window.clear()

print("\nTest 4: Mixed behavior (realistic human)")
for i in range(15):
    result = evaluate_incremental(session_id, {
        "event_type": "key_timing",
        "payload": {"interval_ms": 60 + (i % 40)}
    })
# Add one paste
result = evaluate_incremental(session_id, {
    "event_type": "clipboard",
    "payload": {"pasted": True}
})
print(f"  Score: {result['live_score']} | Decision: {result['decision']}")
print(f"  All signals: {result['signals']}")

print("\n=== Tests Complete ===")
print("\nExpected behaviors:")
print("- More keystrokes -> higher liveness -> allow")
print("- More paste -> higher AI mediation -> step_up/reject")  
print("- Very low activity -> relay risk spikes -> step_up")
print("- Mixed behavior -> uncertainty zone allows")
