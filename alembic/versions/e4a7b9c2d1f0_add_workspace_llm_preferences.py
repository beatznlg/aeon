"""add workspace-scoped non-secret LLM preferences

Revision ID: e4a7b9c2d1f0
Revises: d91f4e2c7b8a
Create Date: 2026-08-07
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4a7b9c2d1f0"
down_revision: str | Sequence[str] | None = "d91f4e2c7b8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("llm_provider", sa.String(length=50), nullable=True))
    op.add_column("workspaces", sa.Column("llm_model", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "llm_model")
    op.drop_column("workspaces", "llm_provider")
