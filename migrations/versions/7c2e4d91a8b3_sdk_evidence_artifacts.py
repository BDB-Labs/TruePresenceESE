"""sdk evidence artifacts

Revision ID: 7c2e4d91a8b3
Revises: 589e8232c19f
Create Date: 2026-05-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c2e4d91a8b3"
down_revision: Union[str, Sequence[str], None] = "589e8232c19f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sdk_evidence_artifacts (
            evidence_packet_id VARCHAR(255) PRIMARY KEY,
            tenant_id VARCHAR(100) NOT NULL DEFAULT 'default',
            session_id VARCHAR(255) NOT NULL,
            surface VARCHAR(100) NOT NULL DEFAULT 'web',
            created_at TIMESTAMPTZ NOT NULL,
            feature_summaries JSONB NOT NULL DEFAULT '{}'::jsonb,
            detector_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
            reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
            likelihoods JSONB NOT NULL DEFAULT '{}'::jsonb,
            confidence DOUBLE PRECISION NOT NULL,
            recommended_action VARCHAR(100) NOT NULL,
            scoring_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        );

        CREATE INDEX IF NOT EXISTS idx_sdk_evidence_tenant_created
            ON sdk_evidence_artifacts (tenant_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_sdk_evidence_session
            ON sdk_evidence_artifacts (session_id);
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS sdk_evidence_artifacts")
