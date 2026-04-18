from __future__ import annotations

from truepresence.db import _build_database_url


def test_build_database_url_encodes_fallback_credentials(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PGHOST", "db.example.internal")
    monkeypatch.setenv("PGPORT", "5432")
    monkeypatch.setenv("PGUSER", "tenant:user")
    monkeypatch.setenv("PGPASSWORD", "pa:ss/word@prod")
    monkeypatch.setenv("PGDATABASE", "true presence")

    assert (
        _build_database_url()
        == "postgresql://tenant%3Auser:pa%3Ass%2Fword%40prod@db.example.internal:5432/true%20presence"
    )
