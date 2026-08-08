"""Regression tests for production database migration behavior."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from aeon_db import Base, migrate_database
from alembic import command


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_fresh_database_migration_creates_current_model_tables(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'fresh.db'}"
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())

    assert set(Base.metadata.tables).issubset(tables)
    assert engine.connect().execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "e4a7b9c2d1f0"
    workspace_columns = {column["name"] for column in inspect(engine).get_columns("workspaces")}
    assert {"llm_provider", "llm_model"}.issubset(workspace_columns)


def test_legacy_schema_is_preserved_and_stamped(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tenants (id, slug, name, plan, created_at, updated_at) "
                "VALUES ('tenant-1', 'legacy', 'Legacy', 'free', '2026-01-01', '2026-01-01')"
            )
        )

    monkeypatch.setenv("AEON_DATABASE_URL", database_url)
    migrate_database()

    with engine.connect() as connection:
        assert connection.execute(text("SELECT id FROM tenants WHERE slug='legacy'")).scalar_one() == "tenant-1"
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "e4a7b9c2d1f0"
