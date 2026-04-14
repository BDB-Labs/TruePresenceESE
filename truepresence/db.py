"""
TruePresence Database

PostgreSQL connection and schema management.
DATABASE_URL is injected automatically by Railway when Postgres is added.
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def _build_database_url() -> str:
    """
    Get the database URL — tries DATABASE_URL first, then assembles
    from individual Railway Postgres variables as fallback.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    # Railway injects these individually when DATABASE_URL isn't linked
    host = os.environ.get("PGHOST") or os.environ.get("POSTGRES_HOST")
    port = os.environ.get("PGPORT") or os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("PGUSER") or os.environ.get("POSTGRES_USER")
    password = os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    database = os.environ.get("PGDATABASE") or os.environ.get("POSTGRES_DB")

    if all([host, user, password, database]):
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    raise RuntimeError(
        "No database connection info found. Set DATABASE_URL or "
        "PGHOST/PGUSER/PGPASSWORD/PGDATABASE in environment variables."
    )


DATABASE_URL = _build_database_url() if any(
    k in os.environ for k in ["DATABASE_URL", "PGHOST", "POSTGRES_HOST", "POSTGRES_USER"]
) else None


def get_connection():
    """Get a raw psycopg2 connection."""
    url = _build_database_url()
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


@contextmanager
def get_db():
    """Context manager for database connections with auto-commit/rollback."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """
    Initialize database schema.
    Creates tables if they don't exist — safe to run on every startup.
    """
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id          SERIAL PRIMARY KEY,
        email       VARCHAR(255) UNIQUE NOT NULL,
        name        VARCHAR(255) NOT NULL,
        password    VARCHAR(255) NOT NULL,
        role        VARCHAR(50)  NOT NULL DEFAULT 'reviewer',
        tenant_id   VARCHAR(100) NOT NULL DEFAULT 'default',
        active      BOOLEAN      NOT NULL DEFAULT TRUE,
        created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        last_login  TIMESTAMPTZ
    );

    CREATE INDEX IF NOT EXISTS idx_users_email     ON users(email);
    CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_users_role      ON users(role);
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
    logger.info("Database schema initialized")
