"""add tamper-evident hash columns to audit_logs

Revision ID: a1b2c3d4e5f6
Revises: e4a7b9c2d1f0
Create Date: 2026-08-21

The audit_logs table was created before the tamper-evident hashing feature.
This migration adds the three columns required for the hash chain so fresh
databases match the ORM model.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "e4a7b9c2d1f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("previous_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("record_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("hash_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_logs", "hash_version")
    op.drop_column("audit_logs", "record_hash")
    op.drop_column("audit_logs", "previous_hash")
