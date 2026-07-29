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
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
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


class AutomationExecution(Base):
    __tablename__ = "automation_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(255), nullable=True, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    status = Column(String(50), nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class AutomationPolicy(Base):
    __tablename__ = "automation_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    effect = Column(String(50), nullable=False, default="block")  # block, require_approval
    rules = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class AutomationBudget(Base):
    __tablename__ = "automation_budgets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    rule_id = Column(String(255), nullable=True, index=True)
    period = Column(String(50), nullable=False)  # hour, day, month, total
    limit_value = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False, default="block")  # block, warn
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


# === SSO / SCIM models ========================================================
class SsoProvider(Base):
    __tablename__ = "sso_providers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    protocol = Column(String(10), nullable=False)  # "saml" or "oidc"
    name = Column(String(255), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    attribute_mapping = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class ScimToken(Base):
    __tablename__ = "scim_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    description = Column(String(255), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class WorkspaceSecurityConfig(Base):
    __tablename__ = "workspace_security_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True, unique=True)
    pii_redaction_enabled = Column(Boolean, nullable=False, default=True)
    phi_redaction_enabled = Column(Boolean, nullable=False, default=False)
    data_region = Column(String(50), nullable=False, default="global")
    kms_key_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class IdentityLink(Base):
    __tablename__ = "identity_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    provider_id = Column(String(36), ForeignKey("sso_providers.id"), nullable=False, index=True)
    external_id = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("provider_id", "external_id", name="uq_provider_external_id"),
    )


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


def add_automation_execution(
    rule_id: str,
    workspace_id: str,
    status: str,
    result: dict[str, Any] | None = None,
) -> AutomationExecution:
    """Persist a single automation execution row."""
    db = get_db()
    with db.session() as s:
        execution = AutomationExecution(
            rule_id=rule_id,
            workspace_id=str(workspace_id),
            status=status,
            result=result,
        )
        s.add(execution)
        s.commit()
        return execution


def list_automation_executions(
    workspace_id: str,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return recent automation executions for a workspace as plain dicts."""
    db = get_db()
    with db.session() as s:
        q = s.query(AutomationExecution).filter_by(workspace_id=str(workspace_id))
        if since is not None:
            q = q.filter(AutomationExecution.created_at >= since)
        rows = (
            q.order_by(AutomationExecution.created_at.desc())
            .limit(1000)
            .all()
        )
        return [
            {
                "id": row.id,
                "rule_id": row.rule_id,
                "workspace_id": row.workspace_id,
                "status": row.status,
                "result": row.result,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]


def get_workspace_security_config(workspace_id: str) -> Optional["WorkspaceSecurityConfig"]:
    """Fetch the security/residency configuration for a workspace."""
    db = get_db()
    with db.session() as s:
        return s.query(WorkspaceSecurityConfig).filter_by(workspace_id=str(workspace_id)).first()


def upsert_workspace_security_config(
    workspace_id: str,
    *,
    pii_redaction_enabled: bool | None = None,
    phi_redaction_enabled: bool | None = None,
    data_region: str | None = None,
    kms_key_id: str | None = None,
) -> WorkspaceSecurityConfig:
    """Create or update a workspace security configuration record."""
    db = get_db()
    with db.session() as s:
        cfg = s.query(WorkspaceSecurityConfig).filter_by(workspace_id=str(workspace_id)).first()
        if cfg is None:
            cfg = WorkspaceSecurityConfig(workspace_id=str(workspace_id))
            s.add(cfg)
        if pii_redaction_enabled is not None:
            cfg.pii_redaction_enabled = pii_redaction_enabled
        if phi_redaction_enabled is not None:
            cfg.phi_redaction_enabled = phi_redaction_enabled
        if data_region is not None:
            cfg.data_region = data_region
        if kms_key_id is not None:
            cfg.kms_key_id = kms_key_id
        s.commit()
        return cfg


def add_audit_log(
    action: str,
    module: str,
    user_id: str | None,
    workspace_id: str | None,
    email: str | None,
    metadata: dict[str, Any] | None = None,
    pii_redacted: bool = False,
) -> AuditLog:
    """Persist a single audit log row locally."""
    db = get_db()
    with db.session() as s:
        log = AuditLog(
            user_id=str(user_id) if user_id else None,
            email=email,
            action=action,
            module=module,
            workspace_id=str(workspace_id) if workspace_id else None,
            metadata_json=metadata or {},
            pii_redacted=pii_redacted,
        )
        s.add(log)
        s.commit()
        return log


# === Automation policy helpers =================================================

def create_automation_policy(
    workspace_id: str,
    name: str,
    effect: str,
    rules: dict[str, Any] | None = None,
    description: str | None = None,
    enabled: bool = True,
) -> AutomationPolicy:
    """Create and return a new automation policy for a workspace."""
    db = get_db()
    with db.session() as s:
        policy = AutomationPolicy(
            workspace_id=str(workspace_id),
            name=name,
            description=description,
            effect=effect,
            rules=rules or {},
            enabled=enabled,
        )
        s.add(policy)
        s.commit()
        return policy


def get_automation_policy(policy_id: str, workspace_id: str | None = None) -> AutomationPolicy | None:
    """Fetch a single policy by id, optionally scoped to a workspace."""
    db = get_db()
    with db.session() as s:
        q = s.query(AutomationPolicy).filter_by(id=str(policy_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        return q.first()


def list_automation_policies(workspace_id: str, enabled_only: bool = True) -> list[AutomationPolicy]:
    """Return policies for a workspace as ORM objects."""
    db = get_db()
    with db.session() as s:
        q = s.query(AutomationPolicy).filter_by(workspace_id=str(workspace_id))
        if enabled_only:
            q = q.filter_by(enabled=True)
        return q.order_by(AutomationPolicy.created_at.desc()).all()


def update_automation_policy(
    policy: AutomationPolicy,
    name: str | None = None,
    effect: str | None = None,
    rules: dict[str, Any] | None = None,
    description: str | None = None,
    enabled: bool | None = None,
) -> AutomationPolicy:
    """Update an existing automation policy in place."""
    if name is not None:
        policy.name = name
    if effect is not None:
        policy.effect = effect
    if rules is not None:
        policy.rules = rules
    if description is not None:
        policy.description = description
    if enabled is not None:
        policy.enabled = enabled
    db = get_db()
    with db.session() as s:
        s.add(policy)
        s.commit()
        return policy


def delete_automation_policy(policy_id: str, workspace_id: str | None = None) -> bool:
    """Delete a policy and return True if a row was removed."""
    db = get_db()
    with db.session() as s:
        q = s.query(AutomationPolicy).filter_by(id=str(policy_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        deleted = q.delete()
        s.commit()
        return bool(deleted)


def count_automation_policies(workspace_id: str) -> int:
    """Return the number of enabled policies in a workspace."""
    db = get_db()
    with db.session() as s:
        return s.query(AutomationPolicy).filter_by(
            workspace_id=str(workspace_id), enabled=True
        ).count()


# === Automation budget helpers =================================================

def create_automation_budget(
    workspace_id: str,
    name: str,
    period: str,
    limit_value: int,
    action: str = "block",
    rule_id: str | None = None,
    enabled: bool = True,
) -> AutomationBudget:
    """Create and return a new automation budget for a workspace."""
    db = get_db()
    with db.session() as s:
        budget = AutomationBudget(
            workspace_id=str(workspace_id),
            name=name,
            rule_id=str(rule_id) if rule_id else None,
            period=period,
            limit_value=int(limit_value),
            action=action,
            enabled=enabled,
        )
        s.add(budget)
        s.commit()
        return budget


def get_automation_budget(budget_id: str, workspace_id: str | None = None) -> AutomationBudget | None:
    """Fetch a single budget by id, optionally scoped to a workspace."""
    db = get_db()
    with db.session() as s:
        q = s.query(AutomationBudget).filter_by(id=str(budget_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        return q.first()


def list_automation_budgets(workspace_id: str, enabled_only: bool = True) -> list[AutomationBudget]:
    """Return budgets for a workspace as ORM objects."""
    db = get_db()
    with db.session() as s:
        q = s.query(AutomationBudget).filter_by(workspace_id=str(workspace_id))
        if enabled_only:
            q = q.filter_by(enabled=True)
        return q.order_by(AutomationBudget.created_at.desc()).all()


def update_automation_budget(
    budget: AutomationBudget,
    name: str | None = None,
    period: str | None = None,
    limit_value: int | None = None,
    action: str | None = None,
    rule_id: str | None = None,
    enabled: bool | None = None,
) -> AutomationBudget:
    """Update an existing automation budget in place."""
    if name is not None:
        budget.name = name
    if period is not None:
        budget.period = period
    if limit_value is not None:
        budget.limit_value = int(limit_value)
    if action is not None:
        budget.action = action
    if rule_id is not None:
        budget.rule_id = str(rule_id) if rule_id else None
    if enabled is not None:
        budget.enabled = enabled
    db = get_db()
    with db.session() as s:
        s.add(budget)
        s.commit()
        return budget


def delete_automation_budget(budget_id: str, workspace_id: str | None = None) -> bool:
    """Delete a budget and return True if a row was removed."""
    db = get_db()
    with db.session() as s:
        q = s.query(AutomationBudget).filter_by(id=str(budget_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        deleted = q.delete()
        s.commit()
        return bool(deleted)


def count_automation_executions(
    workspace_id: str,
    rule_id: str | None = None,
    since: datetime | None = None,
) -> int:
    """Return the number of automation executions in a workspace since a given time."""
    db = get_db()
    with db.session() as s:
        q = s.query(AutomationExecution).filter_by(workspace_id=str(workspace_id))
        if rule_id is not None:
            q = q.filter_by(rule_id=str(rule_id))
        if since is not None:
            q = q.filter(AutomationExecution.created_at >= since)
        return q.count()


def query_audit_logs(
    workspace_id: str | None = None,
    action: str | None = None,
    module: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query local audit logs with optional filters."""
    db = get_db()
    with db.session() as s:
        q = s.query(AuditLog)
        if workspace_id:
            q = q.filter(AuditLog.workspace_id == str(workspace_id))
        if action:
            q = q.filter(AuditLog.action == action)
        if module:
            q = q.filter(AuditLog.module == module)
        rows = (
            q.order_by(AuditLog.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "email": row.email,
                "action": row.action,
                "module": row.module,
                "workspace_id": row.workspace_id,
                "metadata": row.metadata_json,
                "pii_redacted": row.pii_redacted,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            }
            for row in rows
        ]
