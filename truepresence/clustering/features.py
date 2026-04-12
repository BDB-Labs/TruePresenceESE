def extract_features(session_trace: dict) -> dict:
    return {
        "avg_key_interval": session_trace.get("avg_key_interval", 0.0),
        "paste_ratio": session_trace.get("paste_ratio", 0.0),
        "response_latency_mean": session_trace.get("latency", 0.0),
        "latency_variance": session_trace.get("latency_var", 0.0),
        "cursor_entropy": session_trace.get("entropy", 0.0),
        "challenge_failure_rate": session_trace.get("fail_rate", 0.0),
    }
