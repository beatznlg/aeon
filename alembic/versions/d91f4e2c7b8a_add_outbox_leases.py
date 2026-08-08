"""add durable outbox lifecycle and leases

Revision ID: d91f4e2c7b8a
Revises: cc7e2a1b4f90
Create Date: 2026-08-06
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d91f4e2c7b8a"
down_revision: str | Sequence[str] | None = "cc7e2a1b4f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
    )
    op.add_column(
        "outbox_events",
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_lease_until", "outbox_events", ["lease_until"])
    op.execute(
        sa.text(
            "UPDATE outbox_events SET status = CASE "
            "WHEN published_at IS NOT NULL THEN 'published' ELSE 'pending' END"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_lease_until", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_column("outbox_events", "lease_until")
    op.drop_column("outbox_events", "lease_owner")
    op.drop_column("outbox_events", "status")
