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

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    """Get a raw psycopg2 connection."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable not set")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


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
