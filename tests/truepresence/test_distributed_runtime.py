from __future__ import annotations

from truepresence.runtime import distributed


class _UnavailableRedis:
    def ping(self) -> None:
        raise OSError("redis unavailable")


def test_distributed_runtime_uses_memory_fallback_when_redis_connection_fails(monkeypatch) -> None:
    monkeypatch.setattr(distributed, "REDIS_AVAILABLE", True)
    monkeypatch.setattr(distributed.redis.ConnectionPool, "from_url", lambda *args, **kwargs: object())
    monkeypatch.setattr(distributed.redis, "Redis", lambda connection_pool: _UnavailableRedis())

    runtime = distributed.DistributedRuntime()

    assert runtime.available is False
    assert runtime.store_session("session-1", {"value": 1}) is True
    assert runtime.load_session("session-1")["value"] == 1

    health = runtime.health_check()
    assert health["status"] == "using_fallback"
    assert health["redis_connected"] is False
    assert health["active_sessions"] == 1
