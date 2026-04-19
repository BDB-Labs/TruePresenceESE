"""
TruePresence Database

PostgreSQL connection and schema management.
DATABASE_URL is injected automatically by Railway when Postgres is added.
"""

import logging
import os
from contextlib import contextmanager
from urllib.parse import quote

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
        safe_user = quote(user, safe="")
        safe_password = quote(password, safe="")
        safe_database = quote(database, safe="")
        return f"postgresql://{safe_user}:{safe_password}@{host}:{port}/{safe_database}"

    raise RuntimeError(
        "No database connection info found. Set DATABASE_URL or "
        "PGHOST/PGUSER/PGPASSWORD/PGDATABASE in environment variables."
    )


DATABASE_URL = _build_database_url() if any(
    k in os.environ for k in ["DATABASE_URL", "PGHOST", "POSTGRES_HOST", "POSTGRES_USER"]
) else None


from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

# Global pool instance
_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        url = _build_database_url()
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            dsn=url,
            cursor_factory=RealDictCursor
        )
        logger.info("Database connection pool initialized (min=1, max=20)")
    return _pool

def get_connection():
    """Get a connection from the pool."""
    return _get_pool().getconn()

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
        _get_pool().putconn(conn)


def init_db():
    """
    Initialize database schema.
    Creates tables if they don't exist — safe to run on every startup.
    """
    schema = \"\"\"
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

    CREATE TABLE IF NOT EXISTS user_warnings (
        id          SERIAL PRIMARY KEY,
        user_id     BIGINT NOT NULL,
        tenant_id   VARCHAR(100) NOT NULL DEFAULT 'default',
        reason      TEXT,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS telegram_bot_tokens (
        bot_token   TEXT PRIMARY KEY,
        tenant_id   VARCHAR(100) NOT NULL DEFAULT 'default'
    );

    CREATE TABLE IF NOT EXISTS telegram_protected_groups (
        group_id    BIGINT NOT NULL,
        tenant_id   VARCHAR(100) NOT NULL DEFAULT 'default',
        PRIMARY KEY (group_id, tenant_id)
    );

    CREATE TABLE IF NOT EXISTS telegram_admin_chats (
        chat_id     BIGINT NOT NULL,
        tenant_id   VARCHAR(100) NOT NULL DEFAULT 'default',
        PRIMARY KEY (chat_id, tenant_id)
    );

    CREATE TABLE IF NOT EXISTS telegram_user_sessions (
        session_id  VARCHAR(255) PRIMARY KEY,
        tenant_id   VARCHAR(100) NOT NULL DEFAULT 'default',
        data        JSONB,
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS telegram_pending_reviews (
        review_id   VARCHAR(255) PRIMARY KEY,
        tenant_id   VARCHAR(100) NOT NULL DEFAULT 'default',
        data        JSONB,
        status      VARCHAR(50) NOT NULL DEFAULT 'pending',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_users_email     ON users(email);
    CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_users_role      ON users(role);
    CREATE INDEX IF NOT EXISTS idx_warns_user_tenant ON user_warnings(user_id, tenant_id);
    \"\"\"


    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
    logger.info("Database schema initialized")
