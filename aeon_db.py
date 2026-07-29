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
    Float,
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


# === Anomaly & Incident models (Phase 46) ===================================
class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    anomaly_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False, default="warning")
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    score = Column(Float, nullable=False, default=0.0)
    source_rule_id = Column(String(255), nullable=True)
    source_metric = Column(String(100), nullable=True)
    metadata_json = Column("metadata", JSON, default=dict)
    dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class IncidentRunbook(Base):
    __tablename__ = "incident_runbooks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    triggers = Column(JSON, nullable=False, default=list)
    actions = Column(JSON, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    severity = Column(String(20), nullable=False, default="warning")
    status = Column(String(50), nullable=False, default="open")
    root_cause_anomaly_id = Column(String(36), ForeignKey("anomalies.id"), nullable=True)
    runbook_id = Column(String(36), ForeignKey("incident_runbooks.id"), nullable=True)
    assignee_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    metadata_json = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


# === Disaster Recovery models (Phase 47) ====================================
class BackupPolicy(Base):
    __tablename__ = "backup_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    schedule = Column(String(50), nullable=False, default="0 2 * * *")
    retention_days = Column(Integer, nullable=False, default=30)
    target = Column(String(50), nullable=False, default="local")
    target_config = Column(JSON, nullable=False, default=dict)
    encryption_enabled = Column(Boolean, nullable=False, default=True)
    enabled = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class BackupJob(Base):
    __tablename__ = "backup_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    policy_id = Column(String(36), ForeignKey("backup_policies.id"), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="pending")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    checksum = Column(String(255), nullable=True)
    storage_key = Column(String(1024), nullable=True)
    metadata_json = Column("metadata", JSON, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class RestoreJob(Base):
    __tablename__ = "restore_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    backup_job_id = Column(String(36), ForeignKey("backup_jobs.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column("metadata", JSON, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class DRPlan(Base):
    __tablename__ = "dr_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    rto_minutes = Column(Integer, nullable=False, default=60)
    rpo_minutes = Column(Integer, nullable=False, default=60)
    target_region = Column(String(50), nullable=False, default="primary")
    failover_regions = Column(JSON, nullable=False, default=list)
    contact_info = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True)
    last_drill_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class DRDrill(Base):
    __tablename__ = "dr_drills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    plan_id = Column(String(36), ForeignKey("dr_plans.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    findings = Column(JSON, nullable=False, default=list)
    score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


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
    created_at: datetime | None = None,
) -> AutomationExecution:
    """Persist a single automation execution row."""
    db = get_db()
    with db.session() as s:
        execution = AutomationExecution(
            rule_id=rule_id,
            workspace_id=str(workspace_id),
            status=status,
            result=result,
            created_at=created_at,
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
    timestamp: datetime | None = None,
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
            timestamp=timestamp,
        )
        s.add(log)
        s.commit()
        return log


# === Anomaly / incident helpers ==============================================

def create_anomaly(
    workspace_id: str,
    anomaly_type: str,
    severity: str,
    title: str,
    description: str | None = None,
    score: float = 0.0,
    source_rule_id: str | None = None,
    source_metric: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Anomaly:
    """Persist and return a new anomaly record."""
    db = get_db()
    with db.session() as s:
        anomaly = Anomaly(
            workspace_id=str(workspace_id),
            anomaly_type=anomaly_type,
            severity=severity,
            title=title,
            description=description,
            score=score,
            source_rule_id=source_rule_id,
            source_metric=source_metric,
            metadata_json=metadata or {},
        )
        s.add(anomaly)
        s.commit()
        return anomaly


def list_anomalies(
    workspace_id: str,
    dismissed: bool | None = None,
    severity: str | None = None,
    limit: int = 100,
) -> list[Anomaly]:
    """Return anomalies for a workspace."""
    db = get_db()
    with db.session() as s:
        q = s.query(Anomaly).filter_by(workspace_id=str(workspace_id))
        if dismissed is not None:
            q = q.filter_by(dismissed=dismissed)
        if severity is not None:
            q = q.filter_by(severity=severity)
        return q.order_by(Anomaly.created_at.desc()).limit(limit).all()


def get_anomaly(anomaly_id: str) -> Anomaly | None:
    """Fetch a single anomaly by ID."""
    db = get_db()
    with db.session() as s:
        return s.query(Anomaly).filter_by(id=str(anomaly_id)).first()


def dismiss_anomaly(anomaly_id: str) -> Anomaly | None:
    """Mark an anomaly as dismissed."""
    db = get_db()
    with db.session() as s:
        anomaly = s.query(Anomaly).filter_by(id=str(anomaly_id)).first()
        if anomaly:
            anomaly.dismissed = True
            s.commit()
        return anomaly


def create_incident(
    workspace_id: str,
    title: str,
    severity: str,
    status: str = "open",
    root_cause_anomaly_id: str | None = None,
    runbook_id: str | None = None,
    assignee_user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Incident:
    """Persist and return a new incident record."""
    db = get_db()
    with db.session() as s:
        incident = Incident(
            workspace_id=str(workspace_id),
            title=title,
            severity=severity,
            status=status,
            root_cause_anomaly_id=root_cause_anomaly_id,
            runbook_id=runbook_id,
            assignee_user_id=assignee_user_id,
            metadata_json=metadata or {},
        )
        s.add(incident)
        s.commit()
        return incident


def get_incident(incident_id: str) -> Incident | None:
    """Fetch a single incident by ID."""
    db = get_db()
    with db.session() as s:
        return s.query(Incident).filter_by(id=str(incident_id)).first()


def list_incidents(
    workspace_id: str,
    status: str | None = None,
    limit: int = 100,
) -> list[Incident]:
    """Return incidents for a workspace."""
    db = get_db()
    with db.session() as s:
        q = s.query(Incident).filter_by(workspace_id=str(workspace_id))
        if status is not None:
            q = q.filter_by(status=status)
        return q.order_by(Incident.created_at.desc()).limit(limit).all()


def update_incident(
    incident: Incident,
    status: str | None = None,
    assignee_user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Incident:
    """Update incident status/assignee and commit."""
    if status is not None:
        incident.status = status
        if status == "resolved":
            incident.resolved_at = _now()
    if assignee_user_id is not None:
        incident.assignee_user_id = assignee_user_id
    if metadata is not None:
        incident.metadata_json = metadata
    db = get_db()
    with db.session() as s:
        s.add(incident)
        s.commit()
        return incident


def create_incident_runbook(
    workspace_id: str,
    name: str,
    triggers: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    description: str | None = None,
    enabled: bool = True,
) -> IncidentRunbook:
    """Persist and return a new incident runbook."""
    db = get_db()
    with db.session() as s:
        runbook = IncidentRunbook(
            workspace_id=str(workspace_id),
            name=name,
            description=description,
            triggers=triggers,
            actions=actions,
            enabled=enabled,
        )
        s.add(runbook)
        s.commit()
        return runbook


def get_incident_runbook(runbook_id: str) -> IncidentRunbook | None:
    """Fetch a single runbook by ID."""
    db = get_db()
    with db.session() as s:
        return s.query(IncidentRunbook).filter_by(id=str(runbook_id)).first()


def list_incident_runbooks(workspace_id: str, enabled_only: bool = False) -> list[IncidentRunbook]:
    """Return runbooks for a workspace."""
    db = get_db()
    with db.session() as s:
        q = s.query(IncidentRunbook).filter_by(workspace_id=str(workspace_id))
        if enabled_only:
            q = q.filter_by(enabled=True)
        return q.order_by(IncidentRunbook.created_at.desc()).all()


def update_incident_runbook(
    runbook: IncidentRunbook,
    name: str | None = None,
    description: str | None = None,
    triggers: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    enabled: bool | None = None,
) -> IncidentRunbook:
    """Update a runbook in place and commit."""
    if name is not None:
        runbook.name = name
    if description is not None:
        runbook.description = description
    if triggers is not None:
        runbook.triggers = triggers
    if actions is not None:
        runbook.actions = actions
    if enabled is not None:
        runbook.enabled = enabled
    db = get_db()
    with db.session() as s:
        s.add(runbook)
        s.commit()
        return runbook


def delete_incident_runbook(runbook_id: str) -> bool:
    """Delete a runbook and return True if a row was removed."""
    db = get_db()
    with db.session() as s:
        q = s.query(IncidentRunbook).filter_by(id=str(runbook_id))
        deleted = q.delete()
        s.commit()
        return bool(deleted)


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


# === Disaster Recovery helpers ===============================================

def create_backup_policy(
    workspace_id: str,
    name: str,
    schedule: str = "0 2 * * *",
    retention_days: int = 30,
    target: str = "local",
    target_config: dict[str, Any] | None = None,
    encryption_enabled: bool = True,
    enabled: bool = True,
    next_run_at: datetime | None = None,
) -> BackupPolicy:
    db = get_db()
    with db.session() as s:
        policy = BackupPolicy(
            workspace_id=str(workspace_id),
            name=name,
            schedule=schedule,
            retention_days=int(retention_days),
            target=target,
            target_config=target_config or {},
            encryption_enabled=encryption_enabled,
            enabled=enabled,
            next_run_at=next_run_at,
        )
        s.add(policy)
        s.commit()
        return policy


def get_backup_policy(policy_id: str, workspace_id: str | None = None) -> BackupPolicy | None:
    db = get_db()
    with db.session() as s:
        q = s.query(BackupPolicy).filter_by(id=str(policy_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        return q.first()


def list_backup_policies(workspace_id: str, enabled_only: bool = False) -> list[BackupPolicy]:
    db = get_db()
    with db.session() as s:
        q = s.query(BackupPolicy).filter_by(workspace_id=str(workspace_id))
        if enabled_only:
            q = q.filter_by(enabled=True)
        return q.order_by(BackupPolicy.created_at.desc()).all()


def update_backup_policy(
    policy: BackupPolicy,
    name: str | None = None,
    schedule: str | None = None,
    retention_days: int | None = None,
    target: str | None = None,
    target_config: dict[str, Any] | None = None,
    encryption_enabled: bool | None = None,
    enabled: bool | None = None,
    next_run_at: datetime | None = None,
    last_run_at: datetime | None = None,
) -> BackupPolicy:
    if name is not None:
        policy.name = name
    if schedule is not None:
        policy.schedule = schedule
    if retention_days is not None:
        policy.retention_days = int(retention_days)
    if target is not None:
        policy.target = target
    if target_config is not None:
        policy.target_config = target_config
    if encryption_enabled is not None:
        policy.encryption_enabled = encryption_enabled
    if enabled is not None:
        policy.enabled = enabled
    if next_run_at is not None:
        policy.next_run_at = next_run_at
    if last_run_at is not None:
        policy.last_run_at = last_run_at
    db = get_db()
    with db.session() as s:
        s.add(policy)
        s.commit()
        return policy


def delete_backup_policy(policy_id: str, workspace_id: str | None = None) -> bool:
    db = get_db()
    with db.session() as s:
        q = s.query(BackupPolicy).filter_by(id=str(policy_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        deleted = q.delete()
        s.commit()
        return bool(deleted)


def create_backup_job(
    workspace_id: str,
    policy_id: str | None,
    status: str = "pending",
    storage_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BackupJob:
    db = get_db()
    with db.session() as s:
        job = BackupJob(
            workspace_id=str(workspace_id),
            policy_id=str(policy_id) if policy_id else None,
            status=status,
            storage_key=storage_key,
            metadata_json=metadata or {},
        )
        s.add(job)
        s.commit()
        return job


def get_backup_job(job_id: str, workspace_id: str | None = None) -> BackupJob | None:
    db = get_db()
    with db.session() as s:
        q = s.query(BackupJob).filter_by(id=str(job_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        return q.first()


def list_backup_jobs(workspace_id: str, limit: int = 100) -> list[BackupJob]:
    db = get_db()
    with db.session() as s:
        return (
            s.query(BackupJob)
            .filter_by(workspace_id=str(workspace_id))
            .order_by(BackupJob.created_at.desc())
            .limit(limit)
            .all()
        )


def update_backup_job(
    job: BackupJob,
    status: str | None = None,
    size_bytes: int | None = None,
    checksum: str | None = None,
    storage_key: str | None = None,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> BackupJob:
    if status is not None:
        job.status = status
    if size_bytes is not None:
        job.size_bytes = size_bytes
    if checksum is not None:
        job.checksum = checksum
    if storage_key is not None:
        job.storage_key = storage_key
    if metadata is not None:
        job.metadata_json = metadata
    if error_message is not None:
        job.error_message = error_message
    if started_at is not None:
        job.started_at = started_at
    if completed_at is not None:
        job.completed_at = completed_at
    db = get_db()
    with db.session() as s:
        s.add(job)
        s.commit()
        return job


def delete_backup_job(job_id: str, workspace_id: str | None = None) -> bool:
    db = get_db()
    with db.session() as s:
        q = s.query(BackupJob).filter_by(id=str(job_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        deleted = q.delete()
        s.commit()
        return bool(deleted)


def create_restore_job(
    workspace_id: str,
    backup_job_id: str,
    status: str = "pending",
    metadata: dict[str, Any] | None = None,
) -> RestoreJob:
    db = get_db()
    with db.session() as s:
        job = RestoreJob(
            workspace_id=str(workspace_id),
            backup_job_id=str(backup_job_id),
            status=status,
            metadata_json=metadata or {},
        )
        s.add(job)
        s.commit()
        return job


def get_restore_job(job_id: str, workspace_id: str | None = None) -> RestoreJob | None:
    db = get_db()
    with db.session() as s:
        q = s.query(RestoreJob).filter_by(id=str(job_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        return q.first()


def list_restore_jobs(workspace_id: str, limit: int = 100) -> list[RestoreJob]:
    db = get_db()
    with db.session() as s:
        return (
            s.query(RestoreJob)
            .filter_by(workspace_id=str(workspace_id))
            .order_by(RestoreJob.created_at.desc())
            .limit(limit)
            .all()
        )


def update_restore_job(
    job: RestoreJob,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> RestoreJob:
    if status is not None:
        job.status = status
    if metadata is not None:
        job.metadata_json = metadata
    if error_message is not None:
        job.error_message = error_message
    if started_at is not None:
        job.started_at = started_at
    if completed_at is not None:
        job.completed_at = completed_at
    db = get_db()
    with db.session() as s:
        s.add(job)
        s.commit()
        return job


def create_dr_plan(
    workspace_id: str,
    name: str,
    rto_minutes: int = 60,
    rpo_minutes: int = 60,
    target_region: str = "primary",
    failover_regions: list[str] | None = None,
    contact_info: dict[str, Any] | None = None,
    enabled: bool = True,
) -> DRPlan:
    db = get_db()
    with db.session() as s:
        plan = DRPlan(
            workspace_id=str(workspace_id),
            name=name,
            rto_minutes=int(rto_minutes),
            rpo_minutes=int(rpo_minutes),
            target_region=target_region,
            failover_regions=failover_regions or [],
            contact_info=contact_info or {},
            enabled=enabled,
        )
        s.add(plan)
        s.commit()
        return plan


def get_dr_plan(plan_id: str, workspace_id: str | None = None) -> DRPlan | None:
    db = get_db()
    with db.session() as s:
        q = s.query(DRPlan).filter_by(id=str(plan_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        return q.first()


def list_dr_plans(workspace_id: str, enabled_only: bool = False) -> list[DRPlan]:
    db = get_db()
    with db.session() as s:
        q = s.query(DRPlan).filter_by(workspace_id=str(workspace_id))
        if enabled_only:
            q = q.filter_by(enabled=True)
        return q.order_by(DRPlan.created_at.desc()).all()


def update_dr_plan(
    plan: DRPlan,
    name: str | None = None,
    rto_minutes: int | None = None,
    rpo_minutes: int | None = None,
    target_region: str | None = None,
    failover_regions: list[str] | None = None,
    contact_info: dict[str, Any] | None = None,
    enabled: bool | None = None,
    last_drill_at: datetime | None = None,
) -> DRPlan:
    if name is not None:
        plan.name = name
    if rto_minutes is not None:
        plan.rto_minutes = int(rto_minutes)
    if rpo_minutes is not None:
        plan.rpo_minutes = int(rpo_minutes)
    if target_region is not None:
        plan.target_region = target_region
    if failover_regions is not None:
        plan.failover_regions = failover_regions
    if contact_info is not None:
        plan.contact_info = contact_info
    if enabled is not None:
        plan.enabled = enabled
    if last_drill_at is not None:
        plan.last_drill_at = last_drill_at
    db = get_db()
    with db.session() as s:
        s.add(plan)
        s.commit()
        return plan


def delete_dr_plan(plan_id: str, workspace_id: str | None = None) -> bool:
    db = get_db()
    with db.session() as s:
        q = s.query(DRPlan).filter_by(id=str(plan_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        deleted = q.delete()
        s.commit()
        return bool(deleted)


def create_dr_drill(
    workspace_id: str,
    plan_id: str,
    status: str = "pending",
    findings: list[dict[str, Any]] | None = None,
    score: float = 0.0,
) -> DRDrill:
    db = get_db()
    with db.session() as s:
        drill = DRDrill(
            workspace_id=str(workspace_id),
            plan_id=str(plan_id),
            status=status,
            findings=findings or [],
            score=float(score),
        )
        s.add(drill)
        s.commit()
        return drill


def get_dr_drill(drill_id: str, workspace_id: str | None = None) -> DRDrill | None:
    db = get_db()
    with db.session() as s:
        q = s.query(DRDrill).filter_by(id=str(drill_id))
        if workspace_id is not None:
            q = q.filter_by(workspace_id=str(workspace_id))
        return q.first()


def list_dr_drills(workspace_id: str, limit: int = 100) -> list[DRDrill]:
    db = get_db()
    with db.session() as s:
        return (
            s.query(DRDrill)
            .filter_by(workspace_id=str(workspace_id))
            .order_by(DRDrill.created_at.desc())
            .limit(limit)
            .all()
        )


def update_dr_drill(
    drill: DRDrill,
    status: str | None = None,
    findings: list[dict[str, Any]] | None = None,
    score: float | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> DRDrill:
    if status is not None:
        drill.status = status
    if findings is not None:
        drill.findings = findings
    if score is not None:
        drill.score = float(score)
    if started_at is not None:
        drill.started_at = started_at
    if completed_at is not None:
        drill.completed_at = completed_at
    db = get_db()
    with db.session() as s:
        s.add(drill)
        s.commit()
        return drill
