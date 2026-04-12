from typing import List, Dict
from ese_stream import evaluate_incremental  # to be implemented


def run_attack(test_name: str, events: List[Dict]) -> Dict:
    if not events:
        return {"test": test_name, "final_score": None, "decision": None, "trace": []}
    session_id = events[0]["session_id"]
    results = []
    for e in events:
        res = evaluate_incremental(session_id, e)
        results.append(res)
    final = results[-1] if results else None
    return {
        "test": test_name,
        "final_score": final.get("live_score") if final else None,
        "decision": final.get("decision") if final else None,
        "trace": results,
    }
