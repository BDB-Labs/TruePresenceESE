from __future__ import annotations

import hashlib


def stable_index(session_id: str, count: int) -> int:
    if count <= 0:
        raise ValueError("count must be positive")
    digest = hashlib.sha256(session_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % count


def stable_challenge_id(session_id: str, index: int) -> str:
    digest = hashlib.sha256(f"{session_id}:{index}".encode("utf-8")).hexdigest()
    return f"challenge_{digest[:12]}"
