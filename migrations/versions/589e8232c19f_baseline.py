"""baseline

Revision ID: 589e8232c19f
Revises: 
Create Date: 2026-05-02 14:04:39.782794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '589e8232c19f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            email       VARCHAR(255) UNIQUE NOT NULL,
            name        VARCHAR(255) NOT NULL,
            password    VARCHAR(255) NOT NULL,
            role        VARCHAR(50)  NOT NULL DEFAULT 'reviewer' CHECK (role IN ('super_admin', 'reviewer', 'observer')),
            tenant_id   VARCHAR(100) NOT NULL DEFAULT 'default',
            active      BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            last_login  TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS user_warnings (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tenant_id   VARCHAR(100) NOT NULL DEFAULT 'default',
            reason      TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS telegram_bot_tokens (
            tenant_id   VARCHAR(100) PRIMARY KEY DEFAULT 'default',
            bot_token   TEXT NOT NULL
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
        CREATE INDEX IF NOT EXISTS idx_reviews_status ON telegram_pending_reviews(status);
        CREATE INDEX IF NOT EXISTS idx_reviews_created ON telegram_pending_reviews(created_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON telegram_user_sessions(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_updated ON telegram_user_sessions(updated_at);
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS telegram_pending_reviews")
    op.execute("DROP TABLE IF EXISTS telegram_user_sessions")
    op.execute("DROP TABLE IF EXISTS telegram_admin_chats")
    op.execute("DROP TABLE IF EXISTS telegram_protected_groups")
    op.execute("DROP TABLE IF EXISTS telegram_bot_tokens")
    op.execute("DROP TABLE IF EXISTS user_warnings")
    op.execute("DROP TABLE IF EXISTS users")
