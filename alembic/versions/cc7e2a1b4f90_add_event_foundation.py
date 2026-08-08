"""add event foundation tables

Revision ID: cc7e2a1b4f90
Revises: 8f0a6c7d1e2b
Create Date: 2026-08-05
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cc7e2a1b4f90"
down_revision: str | Sequence[str] | None = "8f0a6c7d1e2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("schema_uri", sa.String(length=1024), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_tenant_id", "outbox_events", ["tenant_id"])
    op.create_index("ix_outbox_events_workspace_id", "outbox_events", ["workspace_id"])
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_available_created", "outbox_events", ["available_at", "created_at"])
    op.create_index(
        "ix_outbox_events_workspace_created",
        "outbox_events",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_outbox_events_aggregate_version",
        "outbox_events",
        ["aggregate_type", "aggregate_id", "aggregate_version"],
    )

    op.create_table(
        "event_consumptions",
        sa.Column("consumer_name", sa.String(length=255), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="received"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("consumer_name", "event_id"),
    )
    op.create_index("ix_event_consumptions_event_id", "event_consumptions", ["event_id"])
    op.create_index("ix_event_consumptions_status", "event_consumptions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_event_consumptions_status", table_name="event_consumptions")
    op.drop_index("ix_event_consumptions_event_id", table_name="event_consumptions")
    op.drop_table("event_consumptions")
    op.drop_index("ix_outbox_events_aggregate_version", table_name="outbox_events")
    op.drop_index("ix_outbox_events_workspace_created", table_name="outbox_events")
    op.drop_index("ix_outbox_events_available_created", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_index("ix_outbox_events_workspace_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_tenant_id", table_name="outbox_events")
    op.drop_table("outbox_events")
