"""
AEON OS — Database models for Phase 0 Foundation
==================================================
SQLAlchemy ORM models that mirror the existing Supabase schema so the
Python backend can work with Postgres directly (identity, workspaces,
memberships, audit logs) without relying solely on filesystem state.

Env:
  AEON_DATABASE_URL   e.g. postgresql+psycopg2://user:pass@host/db
                        Falls back to a local SQLite file if unset.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

Base = declarative_base()


def _now():
    return datetime.now(timezone.utc)


class UUIDMixin:
    """Mixin that uses a UUID primary key compatible with Postgres and SQLite."""

    @classmethod
    def id_column(cls):
        # Use Postgres native UUID when available; otherwise fall back to string.
        return Column("id", String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), nullable=False, default="free")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    password = Column(Text, nullable=False)
    role = Column(String(50), nullable=False, default="VIEWER")
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), nullable=False, default="free")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    memberships = relationship("Membership", back_populates="workspace", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="VIEWER")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    workspace = relationship("Workspace", back_populates="memberships")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    action = Column(String(255), nullable=False, index=True)
    module = Column(String(255), nullable=True, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    metadata_json = Column("metadata", JSON, default=dict)
    pii_redacted = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_now)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


# === Engine / Session factory =================================================

def get_database_url() -> str:
    url = os.environ.get("AEON_DATABASE_URL")
    if url:
        return url
    # Fallback to a local SQLite database for development/offline use.
    return "sqlite:///aeon_state/aeon.db"


class Database:
    """Thin wrapper around SQLAlchemy engine and session factory.

    Configures connection pooling for Postgres (QueuePool) and keeps a
    simple NullPool for SQLite to avoid threading issues in dev/test.
    """

    def __init__(self, url: str | None = None):
        self.url = url or get_database_url()
        self.engine = create_engine(
            self.url,
            future=True,
            **self._engine_kwargs(self.url),
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    @staticmethod
    def _engine_kwargs(url: str) -> dict[str, Any]:
        """Return engine kwargs tuned for the database dialect."""
        if url.startswith("sqlite") or url.startswith("file:"):
            return {"poolclass": NullPool}
        return {
            "poolclass": QueuePool,
            "pool_size": int(os.environ.get("AEON_DB_POOL_SIZE", "10")),
            "max_overflow": int(os.environ.get("AEON_DB_MAX_OVERFLOW", "20")),
            "pool_pre_ping": True,
            "pool_recycle": int(os.environ.get("AEON_DB_POOL_RECYCLE", "1800")),
        }

    def create_all(self):
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self.SessionLocal()

    def get_user_by_email(self, email: str) -> User | None:
        with self.session() as s:
            return s.query(User).filter_by(email=email).first()

    def get_user_by_id(self, user_id: str) -> User | None:
        with self.session() as s:
            return s.query(User).filter_by(id=str(user_id)).first()

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        with self.session() as s:
            return s.query(Workspace).filter_by(id=str(workspace_id)).first()

    def get_workspace_by_slug(self, slug: str, tenant_id: str | None = None) -> Workspace | None:
        with self.session() as s:
            q = s.query(Workspace).filter_by(slug=slug)
            if tenant_id:
                q = q.filter_by(tenant_id=str(tenant_id))
            return q.first()

    def get_membership(self, workspace_id: str, user_id: str) -> Membership | None:
        with self.session() as s:
            return s.query(Membership).filter_by(workspace_id=str(workspace_id), user_id=str(user_id)).first()

    def list_workspace_members(self, workspace_id: str) -> list[Membership]:
        with self.session() as s:
            return s.query(Membership).filter_by(workspace_id=str(workspace_id)).all()

    def list_user_memberships(self, user_id: str) -> list[Membership]:
        with self.session() as s:
            return s.query(Membership).filter_by(user_id=str(user_id)).all()

    def ensure_default_workspace(self, tenant_id: str | None = None) -> Workspace:
        """Create a default workspace if none exists (idempotent)."""
        with self.session() as s:
            ws = s.query(Workspace).filter_by(slug="default").first()
            if ws:
                return ws
            ws = Workspace(
                id="00000000-0000-0000-0000-000000000000",
                tenant_id=tenant_id or "00000000-0000-0000-0000-000000000000",
                slug="default",
                name="Default Workspace",
                plan="enterprise",
            )
            s.add(ws)
            s.commit()
            return ws


# === Singleton-ish global DB instance ========================================
_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def init_db():
    """Create tables. Safe to call repeatedly."""
    get_db().create_all()
