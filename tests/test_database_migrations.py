"""Regression tests for production database migration behavior."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from aeon_db import Base, migrate_database
from alembic import command


ALEMBIC_HEAD = "b2c3d4e5f6a7"


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
    assert engine.connect().execute(text("SELECT version_num FROM alembic_version")).scalar_one() == ALEMBIC_HEAD
    workspace_columns = {column["name"] for column in inspect(engine).get_columns("workspaces")}
    assert {"llm_provider", "llm_model"}.issubset(workspace_columns)


def test_migrated_database_has_no_column_drift(tmp_path):
    """Every ORM column must exist in the migrated schema and vice-versa."""
    database_url = f"sqlite:///{tmp_path / 'drift.db'}"
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    orm_tables = set(Base.metadata.tables.keys())

    missing_tables = orm_tables - db_tables
    assert not missing_tables, f"Tables in ORM but missing from migrations: {sorted(missing_tables)}"

    for table_name in sorted(orm_tables):
        orm_cols = {c.name for c in Base.metadata.tables[table_name].columns}
        db_cols = {col["name"] for col in inspector.get_columns(table_name)}
        missing_cols = orm_cols - db_cols
        extra_cols = db_cols - orm_cols
        assert not missing_cols, f"{table_name}: ORM columns missing from DB: {sorted(missing_cols)}"
        assert not extra_cols, f"{table_name}: extra DB columns not in ORM: {sorted(extra_cols)}"


def test_audit_logs_tamper_evident_columns_exist(tmp_path):
    """The tamper-evident audit hash chain columns must survive migration."""
    database_url = f"sqlite:///{tmp_path / 'audit.db'}"
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    audit_cols = {col["name"] for col in inspect(engine).get_columns("audit_logs")}
    assert {"hash_version", "previous_hash", "record_hash"}.issubset(audit_cols)


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
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == ALEMBIC_HEAD
