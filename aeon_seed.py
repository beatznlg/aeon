"""
AEON OS — Demo Data Seeder
==========================
Programmatically populate a workspace with realistic demo records
(anomalies, incidents, DR plans, backup policies, automation policies,
runbooks and a SIEM integration) so the dashboard is immediately useful
during a demo.

Usage:
    # From Python
    from aeon_seed import seed_demo_workspace
    seed_demo_workspace("<workspace_id>")

    # From CLI
    python aeon_seed.py <workspace_id>
    python aeon_seed.py                       # creates a full demo admin user
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from aeon_db import (
    Anomaly,
    AutomationBudget,
    BackupJob,
    BackupPolicy,
    DRDrill,
    DRPlan,
    Incident,
    IncidentRunbook,
    Membership,
    RestoreJob,
    SiemExportLog,
    SiemIntegration,
    User,
    Workspace,
    add_audit_log,
    create_anomaly,
    create_automation_budget,
    create_automation_policy,
    create_backup_job,
    create_backup_policy,
    create_dr_drill,
    create_dr_plan,
    create_incident,
    create_incident_runbook,
    create_restore_job,
    create_siem_export_log,
    create_siem_integration,
    get_db,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _minutes_ago(minutes: int) -> datetime:
    return _now() - timedelta(minutes=minutes)


def _find_or_create_anomaly(workspace_id: str, title: str, **kwargs: Any) -> Anomaly:
    db = get_db()
    with db.session() as s:
        existing = s.query(Anomaly).filter_by(workspace_id=str(workspace_id), title=title).first()
        if existing:
            return existing
    return create_anomaly(workspace_id=str(workspace_id), title=title, **kwargs)


def _find_or_create_runbook(workspace_id: str, name: str, **kwargs: Any) -> IncidentRunbook:
    db = get_db()
    with db.session() as s:
        existing = s.query(IncidentRunbook).filter_by(workspace_id=str(workspace_id), name=name).first()
        if existing:
            return existing
    return create_incident_runbook(workspace_id=str(workspace_id), name=name, **kwargs)


def _find_or_create_incident(workspace_id: str, title: str, **kwargs: Any) -> Incident:
    db = get_db()
    with db.session() as s:
        existing = s.query(Incident).filter_by(workspace_id=str(workspace_id), title=title).first()
        if existing:
            return existing
    return create_incident(workspace_id=str(workspace_id), title=title, **kwargs)


def _find_or_create_backup_policy(workspace_id: str, name: str, **kwargs: Any) -> BackupPolicy:
    db = get_db()
    with db.session() as s:
        existing = s.query(BackupPolicy).filter_by(workspace_id=str(workspace_id), name=name).first()
        if existing:
            return existing
    return create_backup_policy(workspace_id=str(workspace_id), name=name, **kwargs)


def _find_or_create_dr_plan(workspace_id: str, name: str, **kwargs: Any) -> DRPlan:
    db = get_db()
    with db.session() as s:
        existing = s.query(DRPlan).filter_by(workspace_id=str(workspace_id), name=name).first()
        if existing:
            return existing
    return create_dr_plan(workspace_id=str(workspace_id), name=name, **kwargs)


def _find_or_create_siem(workspace_id: str, name: str, **kwargs: Any) -> SiemIntegration:
    db = get_db()
    with db.session() as s:
        existing = s.query(SiemIntegration).filter_by(workspace_id=str(workspace_id), name=name).first()
        if existing:
            return existing
    return create_siem_integration(workspace_id=str(workspace_id), name=name, **kwargs)


def _find_or_create_automation_policy(workspace_id: str, name: str, **kwargs: Any) -> Any:
    from aeon_db import AutomationPolicy

    db = get_db()
    with db.session() as s:
        existing = s.query(AutomationPolicy).filter_by(workspace_id=str(workspace_id), name=name).first()
        if existing:
            return existing
    return create_automation_policy(workspace_id=str(workspace_id), name=name, **kwargs)


def _find_or_create_backup_job(workspace_id: str, key: str, **kwargs: Any) -> BackupJob:
    db = get_db()
    with db.session() as s:
        existing = s.query(BackupJob).filter_by(workspace_id=str(workspace_id), storage_key=key).first()
        if existing:
            return existing
    return create_backup_job(workspace_id=str(workspace_id), storage_key=key, **kwargs)


def _find_or_create_restore_job(workspace_id: str, key: str, **kwargs: Any) -> RestoreJob:
    db = get_db()
    with db.session() as s:
        existing = s.query(RestoreJob).filter_by(workspace_id=str(workspace_id), backup_job_id=kwargs.get("backup_job_id")).first()
        if existing:
            return existing
    return create_restore_job(workspace_id=str(workspace_id), **kwargs)


def _find_or_create_dr_drill(workspace_id: str, key: str, **kwargs: Any) -> DRDrill:
    db = get_db()
    with db.session() as s:
        existing = s.query(DRDrill).filter_by(workspace_id=str(workspace_id), plan_id=kwargs.get("plan_id"), status=kwargs.get("status", "pending")).first()
        if existing:
            return existing
    return create_dr_drill(workspace_id=str(workspace_id), **kwargs)


def _find_or_create_automation_budget(workspace_id: str, name: str, **kwargs: Any) -> AutomationBudget:
    db = get_db()
    with db.session() as s:
        existing = s.query(AutomationBudget).filter_by(workspace_id=str(workspace_id), name=name).first()
        if existing:
            return existing
    return create_automation_budget(workspace_id=str(workspace_id), name=name, **kwargs)


def _find_or_create_siem_export_log(workspace_id: str, key: str, **kwargs: Any) -> SiemExportLog:
    db = get_db()
    with db.session() as s:
        existing = s.query(SiemExportLog).filter_by(workspace_id=str(workspace_id), event_id=kwargs.get("event_id")).first()
        if existing:
            return existing
    return create_siem_export_log(workspace_id=str(workspace_id), **kwargs)


def seed_demo_workspace(workspace_id: str) -> dict[str, Any]:
    """Seed a workspace with demo data. Idempotent by title/name keys."""
    db = get_db()
    ws = db.get_workspace(workspace_id)
    if not ws:
        raise ValueError(f"workspace {workspace_id} not found")

    created: dict[str, int] = {}

    # --- Anomalies (staggered timestamps for realistic charts) --------------
    anomaly_1 = _find_or_create_anomaly(
        workspace_id=str(workspace_id),
        title="Unusual API latency spike",
        anomaly_type="spike",
        severity="warning",
        description="Average /api/chat latency increased by 240% over the last 15 minutes.",
        score=0.72,
        source_rule_id="rule-latency-001",
        source_metric="api.latency.p95",
        metadata={"service": "api-gateway", "region": "us-east-1"},
    )
    anomaly_2 = _find_or_create_anomaly(
        workspace_id=str(workspace_id),
        title="Possible credential brute-force attempt",
        anomaly_type="pattern",
        severity="critical",
        description="30 failed login attempts from a single IP in 5 minutes.",
        score=0.91,
        source_rule_id="rule-auth-002",
        source_metric="auth.failed_logins",
        metadata={"ip": "203.0.113.42", "source": "login"},
    )
    anomaly_3 = _find_or_create_anomaly(
        workspace_id=str(workspace_id),
        title="Model drift detected",
        anomaly_type="drift",
        severity="info",
        description="RAG embedding distribution shifted by 0.3σ since last week.",
        score=0.45,
        source_rule_id="rule-ml-003",
        source_metric="rag.embedding_drift",
        metadata={"model": "text-embedding-3-small"},
    )

    # Override created_at to stagger demo timeline
    for anomaly, minutes_ago in [(anomaly_1, 30), (anomaly_2, 15), (anomaly_3, 5)]:
        if anomaly and anomaly.created_at and anomaly.created_at > _minutes_ago(minutes_ago - 1):
            anomaly.created_at = _minutes_ago(minutes_ago)
            db = get_db()
            with db.session() as s:
                s.add(anomaly)
                s.commit()

    created["anomalies"] = 3

    # --- Runbooks -----------------------------------------------------------
    runbook = _find_or_create_runbook(
        workspace_id=str(workspace_id),
        name="Auto-remediation: Latency Spike",
        description="Automatically scale API replicas and notify on-call when latency spikes.",
        triggers=[
            {"type": "anomaly", "rule_id": "rule-latency-001"},
            {"type": "metric", "metric": "api.latency.p95", "threshold": 500},
        ],
        actions=[
            {"type": "scale", "service": "api-gateway", "replicas": 3},
            {"type": "notify", "channel": "pager", "message": "API latency spike detected"},
        ],
        enabled=True,
    )
    created["runbooks"] = 1

    # --- Incidents ----------------------------------------------------------
    incident_1 = _find_or_create_incident(
        workspace_id=str(workspace_id),
        title="API latency degradation",
        severity="warning",
        status="open",
        root_cause_anomaly_id=anomaly_1.id,
        runbook_id=runbook.id,
        metadata={"assigned_team": "platform", "priority": "p2"},
    )
    _find_or_create_incident(
        workspace_id=str(workspace_id),
        title="Suspicious login activity",
        severity="critical",
        status="open",
        root_cause_anomaly_id=anomaly_2.id,
        metadata={"assigned_team": "security", "priority": "p1"},
    )
    created["incidents"] = 2

    # --- Backup policies ----------------------------------------------------
    backup_policy_1 = _find_or_create_backup_policy(
        workspace_id=str(workspace_id),
        name="Daily Postgres Snapshot",
        schedule="0 2 * * *",
        retention_days=30,
        target="s3",
        target_config={"bucket": "aeon-demo-backups", "region": "us-east-1"},
        encryption_enabled=True,
        enabled=True,
        next_run_at=_now(),
    )
    backup_policy_2 = _find_or_create_backup_policy(
        workspace_id=str(workspace_id),
        name="Hourly WAL Archive",
        schedule="0 * * * *",
        retention_days=7,
        target="s3",
        target_config={"bucket": "aeon-demo-wal", "region": "us-east-1"},
        encryption_enabled=True,
        enabled=True,
        next_run_at=_now(),
    )
    created["backup_policies"] = 2

    # --- DR plans ------------------------------------------------------------
    dr_plan = _find_or_create_dr_plan(
        workspace_id=str(workspace_id),
        name="Primary Region Failover",
        rto_minutes=60,
        rpo_minutes=15,
        target_region="us-east-1",
        failover_regions=["us-west-2", "eu-central-1"],
        contact_info={
            "oncall": "demo-oncall@example.com",
            "slack": "#incidents",
            "runbook_url": "https://wiki.example.com/dr",
        },
        enabled=True,
    )
    created["dr_plans"] = 1

    # --- Automation policies ------------------------------------------------
    _find_or_create_automation_policy(
        workspace_id=str(workspace_id),
        name="Block risky outbound webhooks",
        effect="block",
        description="Prevent automation rules from calling non-allowlisted hosts.",
        rules={
            "condition": {"field": "action.type", "operator": "eq", "value": "webhook"},
            "allowed_hosts": ["*.trusted.example.com"],
        },
        enabled=True,
    )
    _find_or_create_automation_policy(
        workspace_id=str(workspace_id),
        name="Require approval for destructive actions",
        effect="require_approval",
        description="Pause workflows that delete resources until an admin approves.",
        rules={
            "condition": {"field": "action.type", "operator": "in", "value": ["delete", "terminate"]},
        },
        enabled=True,
    )
    created["automation_policies"] = 2

    # --- SIEM integration ----------------------------------------------------
    siem = _find_or_create_siem(
        workspace_id=str(workspace_id),
        name="Demo Splunk HEC",
        provider="splunk",
        endpoint_url="https://hec.splunk.example.com/services/collector/event",
        auth_type="token",
        api_token="demo-token-123",
        event_filters=["audit", "anomaly", "incident", "dlp"],
        log_level="all",
        batch_size=100,
        enabled=True,
    )
    created["siem_integrations"] = 1

    # --- Backup jobs (audit evidence) ----------------------------------------
    backup_job_1 = _find_or_create_backup_job(
        workspace_id=str(workspace_id),
        key="s3://aeon-demo-backups/full-2026-08-17.bak",
        policy_id=backup_policy_1.id,
        status="completed",
        storage_key="s3://aeon-demo-backups/full-2026-08-17.bak",
        metadata={"size_bytes": 104857600, "duration_s": 142},
    )
    _find_or_create_backup_job(
        workspace_id=str(workspace_id),
        key="s3://aeon-demo-wal/archive-2026-08-17-0200.log",
        policy_id=backup_policy_2.id,
        status="failed",
        storage_key="s3://aeon-demo-wal/archive-2026-08-17-0200.log",
        metadata={"error": "WAL archive timed out", "duration_s": 300},
    )
    created["backup_jobs"] = 2

    # --- Restore job ----------------------------------------------------------
    _find_or_create_restore_job(
        workspace_id=str(workspace_id),
        key=f"restore-{backup_job_1.id}",
        backup_job_id=backup_job_1.id,
        status="completed",
        metadata={"target_region": "us-west-2", "duration_s": 95},
    )
    created["restore_jobs"] = 1

    # --- DR drills (evidence) -------------------------------------------------
    _find_or_create_dr_drill(
        workspace_id=str(workspace_id),
        key=f"drill-passed-{dr_plan.id}",
        plan_id=dr_plan.id,
        status="passed",
        score=0.94,
        findings=[
            {"check": "RTO met", "ok": True},
            {"check": "RPO within window", "ok": True},
        ],
    )
    _find_or_create_dr_drill(
        workspace_id=str(workspace_id),
        key=f"drill-warning-{dr_plan.id}",
        plan_id=dr_plan.id,
        status="warning",
        score=0.78,
        findings=[
            {"check": "Failover completed", "ok": True},
            {"check": "Data sync lag", "ok": False, "note": "12 min lag vs 15 min RPO"},
        ],
    )
    created["dr_drills"] = 2

    # --- Automation budgets ---------------------------------------------------
    _find_or_create_automation_budget(
        workspace_id=str(workspace_id),
        name="Monthly webhook budget",
        period="monthly",
        limit_value=1000,
        action="block",
        enabled=True,
    )
    _find_or_create_automation_budget(
        workspace_id=str(workspace_id),
        name="Daily execution cap",
        period="daily",
        limit_value=500,
        action="warn",
        enabled=True,
    )
    created["automation_budgets"] = 2

    # --- SIEM export logs -----------------------------------------------------
    _find_or_create_siem_export_log(
        workspace_id=str(workspace_id),
        key=f"export-anomaly-{anomaly_1.id}",
        integration_id=siem.id,
        event_type="anomaly",
        event_id=anomaly_1.id,
        status="success",
        http_status=200,
        payload_size=4096,
    )
    _find_or_create_siem_export_log(
        workspace_id=str(workspace_id),
        key=f"export-incident-{incident_1.id}",
        integration_id=siem.id,
        event_type="incident",
        event_id=incident_1.id,
        status="success",
        http_status=200,
        payload_size=5120,
    )
    created["siem_export_logs"] = 2

    # --- Audit trail (governance evidence) ------------------------------------
    add_audit_log(
        action="workspace.seeded",
        module="demo",
        user_id=None,
        workspace_id=str(workspace_id),
        email="admin@demo.local",
        metadata={"seed": "aeon_seed"},
        timestamp=_minutes_ago(45),
    )
    add_audit_log(
        action="automation.policy.updated",
        module="automations",
        user_id=None,
        workspace_id=str(workspace_id),
        email="admin@demo.local",
        metadata={"policy": "Block risky outbound webhooks"},
        timestamp=_minutes_ago(30),
    )
    add_audit_log(
        action="dr.drill.completed",
        module="dr",
        user_id=None,
        workspace_id=str(workspace_id),
        email="admin@demo.local",
        metadata={"plan": "Primary Region Failover", "score": 0.94},
        timestamp=_minutes_ago(20),
    )
    add_audit_log(
        action="auth.login",
        module="security",
        user_id=None,
        workspace_id=str(workspace_id),
        email="admin@demo.local",
        metadata={"method": "password"},
        timestamp=_minutes_ago(10),
    )
    created["audit_logs"] = 4

    return {
        "ok": True,
        "workspace_id": str(workspace_id),
        "created": created,
    }


def seed_demo_user(email: str, password: str, name: str) -> dict[str, Any]:
    """Create or locate a demo admin user and workspace, then seed demo data."""
    from werkzeug.security import generate_password_hash

    db = get_db()
    with db.session() as s:
        user = s.query(User).filter_by(email=email.lower()).first()
        if not user:
            user = User(
                email=email.lower(),
                name=name,
                password=generate_password_hash(password),
                role="ADMIN",
            )
            s.add(user)
            s.flush()

        workspace = (
            s.query(Workspace)
            .join(Membership)
            .filter(Membership.user_id == user.id)
            .first()
        )
        if not workspace:
            workspace = Workspace(
                slug=f"ws-{user.id[:8]}",
                name=f"{name}'s Workspace",
                plan="enterprise",
            )
            s.add(workspace)
            s.flush()
            membership = Membership(
                workspace_id=workspace.id,
                user_id=user.id,
                role="ADMIN",
            )
            s.add(membership)
        s.commit()

        workspace_id = str(workspace.id)
        user_id = str(user.id)

    seed_summary = seed_demo_workspace(workspace_id)

    from aeon_auth import create_access_token

    token = create_access_token(user_id, user.email, user.role, workspace_id)

    return {
        "ok": True,
        "user": {
            "id": user_id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "workspace_id": workspace_id,
        },
        "token": token,
        **seed_summary,
    }


if __name__ == "__main__":
    import sys

    from aeon_db import init_db

    init_db()

    # If first arg looks like a UUID, seed that workspace directly.
    if len(sys.argv) > 1 and len(sys.argv[1]) >= 32 and "-" in sys.argv[1]:
        result = seed_demo_workspace(sys.argv[1])
        print(result)
        sys.exit(0)

    demo_email = sys.argv[1] if len(sys.argv) > 1 else "admin@demo.local"
    demo_password = sys.argv[2] if len(sys.argv) > 2 else "demo123"
    demo_name = sys.argv[3] if len(sys.argv) > 3 else "Demo Admin"
    result = seed_demo_user(demo_email, demo_password, demo_name)
    print(result)
