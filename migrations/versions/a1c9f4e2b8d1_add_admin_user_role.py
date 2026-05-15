"""add admin user role

Revision ID: a1c9f4e2b8d1
Revises: 7c2e4d91a8b3
Create Date: 2026-05-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1c9f4e2b8d1"
down_revision: Union[str, Sequence[str], None] = "7c2e4d91a8b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
        ALTER TABLE users ADD CONSTRAINT users_role_check
          CHECK (role IN ('super_admin', 'admin', 'reviewer', 'observer'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
        ALTER TABLE users ADD CONSTRAINT users_role_check
          CHECK (role IN ('super_admin', 'reviewer', 'observer'));
        """
    )
