"""
AEON OS Phase 47 — Disaster Recovery & Backup Automation
========================================================
Automated workspace backups, restores, retention, and DR drills.

Uses the pluggable storage backend from aeon_storage so backups can be
written to local filesystem or S3-compatible object storage.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from aeon_db import (
    AuditLog,
    BackupJob,
    BackupPolicy,
    DRDrill,
    Membership,
    RestoreJob,
    User,
    Workspace,
    create_backup_job,
    create_dr_drill,
    create_restore_job,
    delete_backup_job,
    get_backup_job,
    get_backup_policy,
    get_db,
    get_dr_plan,
    list_automation_executions,
    list_backup_jobs,
    update_backup_job,
    update_backup_policy,
    update_dr_drill,
    update_dr_plan,
    update_restore_job,
)
from aeon_storage import get_storage

logger = logging.getLogger("aeon_dr")

BACKUP_VERSION = "1.0"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _storage_key(workspace_id: str, job_id: str) -> str:
    return f"backups/{workspace_id}/{job_id}.json.gz"


def _compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _serialize_backup(payload: dict[str, Any]) -> bytes:
    return gzip.compress(json.dumps(payload, default=str, sort_keys=True).encode("utf-8"))


def _deserialize_backup(data: bytes) -> dict[str, Any]:
    return json.loads(gzip.decompress(data).decode("utf-8"))


def _next_run(schedule: str, base: datetime | None = None) -> datetime:
    """Return the next run time for a cron-style schedule.

    If croniter is unavailable, falls back to 24 hours after *base*.
    """
    base = base or _now()
    try:
        from croniter import croniter  # type: ignore[import-untyped]
        return croniter(schedule, base).get_next(datetime)
    except Exception:  # noqa: BLE001
        return base + timedelta(days=1)


class BackupManager:
    """Coordinate backup creation, restoration, and retention for a workspace."""

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id

    def _collect_snapshot(self) -> dict[str, Any]:
        """Collect a minimal but representative snapshot of workspace data."""
        db = get_db()
        snapshot: dict[str, Any] = {
            "workspace": None,
            "users": [],
            "memberships": [],
            "audit_logs": [],
            "automation_executions": [],
        }
        with db.session() as s:
            ws = s.query(Workspace).filter_by(id=self.workspace_id).first()
            if ws:
                snapshot["workspace"] = {
                    "id": ws.id,
                    "name": ws.name,
                    "slug": ws.slug,
                    "plan": ws.plan,
                    "created_at": ws.created_at.isoformat() if ws.created_at else None,
                }
            users = (
                s.query(User.id, User.email, User.name, User.role, User.created_at)
                .join(Membership, User.id == Membership.user_id)
                .filter(Membership.workspace_id == self.workspace_id)
                .all()
            )
            snapshot["users"] = [
                {
                    "id": u.id,
                    "email": u.email,
                    "name": u.name,
                    "role": u.role,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ]
            memberships = s.query(Membership).filter_by(workspace_id=self.workspace_id).all()
            snapshot["memberships"] = [
                {
                    "id": m.id,
                    "user_id": m.user_id,
                    "role": m.role,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in memberships
            ]
            audit_rows = (
                s.query(AuditLog)
                .filter_by(workspace_id=self.workspace_id)
                .order_by(AuditLog.timestamp.desc())
                .limit(1000)
                .all()
            )
            snapshot["audit_logs"] = [
                {
                    "id": a.id,
                    "action": a.action,
                    "module": a.module,
                    "metadata": a.metadata_json,
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                }
                for a in audit_rows
            ]
        snapshot["automation_executions"] = list_automation_executions(self.workspace_id)[:100]
        return snapshot

    def run_backup(self, policy_id: str) -> BackupJob:
        """Execute a backup according to *policy_id* and persist it to storage."""
        policy = get_backup_policy(policy_id, workspace_id=self.workspace_id)
        if not policy:
            raise ValueError(f"Backup policy {policy_id} not found")

        job = create_backup_job(
            workspace_id=self.workspace_id,
            policy_id=policy_id,
            status="running",
        )
        update_backup_job(job, started_at=_now())
        storage_key = _storage_key(self.workspace_id, job.id)

        try:
            snapshot = self._collect_snapshot()
            payload = {
                "version": BACKUP_VERSION,
                "workspace_id": self.workspace_id,
                "policy_id": policy_id,
                "created_at": _now().isoformat(),
                "snapshot": snapshot,
            }
            data = _serialize_backup(payload)
            checksum = _compute_checksum(data)
            storage = get_storage()
            storage.write(storage_key, data)

            update_backup_job(
                job,
                status="completed",
                size_bytes=len(data),
                checksum=checksum,
                storage_key=storage_key,
                metadata=payload,
                completed_at=_now(),
            )

            update_backup_policy(
                policy,
                last_run_at=_now(),
                next_run_at=_next_run(policy.schedule),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Backup failed: policy=%s", policy_id)
            update_backup_job(
                job,
                status="failed",
                error_message=str(exc),
                completed_at=_now(),
            )
        return job

    def verify_backup(self, backup_job_id: str) -> dict[str, Any]:
        """Perform a read-only integrity check without exposing backup contents."""
        job = get_backup_job(backup_job_id, workspace_id=self.workspace_id)
        if not job:
            raise ValueError(f"Backup job {backup_job_id} not found")

        checks: list[dict[str, str]] = []

        def add_check(name: str, status: str, message: str) -> None:
            checks.append({"check": name, "status": status, "message": message})

        add_check(
            "job_status",
            "pass" if job.status == "completed" else "fail",
            "Backup job completed" if job.status == "completed" else f"Backup job status is {job.status}",
        )
        if not job.storage_key:
            add_check("storage_key", "fail", "Backup has no storage key")
            add_check("storage_read", "fail", "Backup object cannot be read without a storage key")
            return {
                "verified": False,
                "backup_job_id": job.id,
                "checked_at": _now().isoformat(),
                "checks": checks,
                "failed_checks": [check["check"] for check in checks if check["status"] == "fail"],
            }

        add_check("storage_key", "pass", "Backup storage key is present")
        data: bytes | None = None
        try:
            data = get_storage().read(job.storage_key)
            add_check("storage_read", "pass", "Backup object is readable")
        except Exception:  # noqa: BLE001
            logger.warning("Backup verification could not read job %s", backup_job_id, exc_info=True)
            add_check("storage_read", "fail", "Backup object could not be read")

        payload: dict[str, Any] | None = None
        if data is not None:
            if job.size_bytes is None:
                add_check("size", "warn", "Backup size was not recorded")
            elif len(data) == job.size_bytes:
                add_check("size", "pass", "Stored size matches the recorded size")
            else:
                add_check("size", "fail", "Stored size does not match the recorded size")

            checksum = _compute_checksum(data)
            if job.checksum and checksum == job.checksum:
                add_check("checksum", "pass", "Backup checksum matches the recorded checksum")
            elif job.checksum:
                add_check("checksum", "fail", "Backup checksum does not match the recorded checksum")
            else:
                add_check("checksum", "fail", "Backup checksum is missing")

            try:
                payload = _deserialize_backup(data)
                if not isinstance(payload, dict):
                    raise ValueError("payload is not an object")
                add_check("payload_format", "pass", "Backup payload is valid gzip-compressed JSON")
            except Exception:  # noqa: BLE001
                logger.warning("Backup verification found an invalid payload for job %s", backup_job_id, exc_info=True)
                add_check("payload_format", "fail", "Backup payload could not be decoded")

        if payload is not None:
            version = payload.get("version")
            add_check(
                "backup_version",
                "pass" if version == BACKUP_VERSION else "fail",
                "Backup format version is supported" if version == BACKUP_VERSION else "Backup format version is unsupported",
            )
            payload_workspace_id = str(payload.get("workspace_id") or "")
            add_check(
                "workspace_scope",
                "pass" if payload_workspace_id == self.workspace_id else "fail",
                "Backup belongs to the requested workspace" if payload_workspace_id == self.workspace_id else "Backup workspace does not match the requested workspace",
            )
            add_check(
                "snapshot_shape",
                "pass" if isinstance(payload.get("snapshot"), dict) else "fail",
                "Backup snapshot is present" if isinstance(payload.get("snapshot"), dict) else "Backup snapshot is missing or invalid",
            )
            if job.policy_id:
                add_check(
                    "policy_scope",
                    "pass" if str(payload.get("policy_id") or "") == str(job.policy_id) else "fail",
                    "Backup policy matches the recorded job" if str(payload.get("policy_id") or "") == str(job.policy_id) else "Backup policy does not match the recorded job",
                )

        failed_checks = [check["check"] for check in checks if check["status"] == "fail"]
        return {
            "verified": not failed_checks,
            "backup_job_id": job.id,
            "checked_at": _now().isoformat(),
            "bytes_read": len(data) if data is not None else None,
            "checks": checks,
            "failed_checks": failed_checks,
        }

    def restore_backup(self, backup_job_id: str) -> RestoreJob:
        """Restore from a verified backup job and return the restore record."""
        job = get_backup_job(backup_job_id, workspace_id=self.workspace_id)
        if not job:
            raise ValueError(f"Backup job {backup_job_id} not found")

        restore = create_restore_job(
            workspace_id=self.workspace_id,
            backup_job_id=backup_job_id,
            status="running",
        )
        update_restore_job(restore, started_at=_now())

        try:
            verification = self.verify_backup(backup_job_id)
            if not verification["verified"]:
                raise ValueError("Backup verification failed")
            if not job.storage_key:
                raise ValueError("Backup job has no storage key")

            payload = _deserialize_backup(get_storage().read(job.storage_key))
            update_restore_job(
                restore,
                status="completed",
                metadata={"restored_snapshot": payload.get("snapshot")},
                completed_at=_now(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Restore failed: job=%s", backup_job_id)
            update_restore_job(
                restore,
                status="failed",
                error_message=str(exc),
                completed_at=_now(),
            )
        return restore

    def apply_retention(self, policy_id: str) -> list[str]:
        """Delete backup jobs older than the policy's retention period."""
        policy = get_backup_policy(policy_id, workspace_id=self.workspace_id)
        if not policy or policy.retention_days <= 0:
            return []
        cutoff = _now() - timedelta(days=policy.retention_days)
        old_jobs = [
            job for job in list_backup_jobs(self.workspace_id, limit=10000)
            if job.completed_at and job.completed_at < cutoff
        ]
        storage = get_storage()
        deleted_keys: list[str] = []
        for job in old_jobs:
            if job.storage_key:
                try:
                    storage.delete(job.storage_key)
                    deleted_keys.append(job.storage_key)
                except Exception:  # noqa: S110
                    pass
            delete_backup_job(job.id, workspace_id=self.workspace_id)
        return deleted_keys


class DRPlanManager:
    """Manage DR plan metadata and drill records for a workspace."""

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id

    def record_drill(self, plan_id: str) -> DRDrill:
        plan = get_dr_plan(plan_id, workspace_id=self.workspace_id)
        if not plan:
            raise ValueError(f"DR plan {plan_id} not found")
        drill = create_dr_drill(
            workspace_id=self.workspace_id,
            plan_id=plan_id,
            status="running",
        )
        update_dr_plan(plan, last_drill_at=_now())
        return drill


class DRDrillSimulator:
    """Simulate a failover drill and score DR readiness."""

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id

    def simulate_failover(self, plan_id: str) -> DRDrill:
        plan = get_dr_plan(plan_id, workspace_id=self.workspace_id)
        if not plan:
            raise ValueError(f"DR plan {plan_id} not found")

        manager = DRPlanManager(self.workspace_id)
        drill = manager.record_drill(plan_id)
        update_dr_drill(drill, started_at=_now())

        findings: list[dict[str, Any]] = []
        score = 100.0

        recent_jobs = [
            j for j in list_backup_jobs(self.workspace_id, limit=10)
            if j.status == "completed"
        ]
        if not recent_jobs:
            findings.append({"check": "recent_backup", "status": "fail", "message": "No completed backups in workspace"})
            score -= 40.0
        else:
            findings.append({"check": "recent_backup", "status": "pass", "message": f"{len(recent_jobs)} completed backups available"})

        if recent_jobs:
            latest = recent_jobs[0]
            verification = self.verify_backup(latest.id)
            if verification["verified"]:
                findings.append({"check": "checksum", "status": "pass", "message": "Latest backup integrity verified"})
            else:
                failed_checks = ", ".join(verification.get("failed_checks", [])) or "backup_integrity"
                findings.append({"check": "checksum", "status": "fail", "message": f"Latest backup verification failed: {failed_checks}"})
                score -= 30.0

        if plan.rto_minutes <= 0 or plan.rpo_minutes <= 0:
            findings.append({"check": "plan_targets", "status": "fail", "message": "RTO/RPO must be positive"})
            score -= 10.0
        else:
            findings.append({"check": "plan_targets", "status": "pass", "message": "RTO/RPO configured"})

        if not plan.failover_regions:
            findings.append({"check": "failover_regions", "status": "warn", "message": "No failover regions defined"})
            score -= 10.0
        else:
            findings.append({"check": "failover_regions", "status": "pass", "message": f"Failover regions: {plan.failover_regions}"})

        if not plan.contact_info:
            findings.append({"check": "contact_info", "status": "warn", "message": "No contact info defined"})
            score -= 10.0
        else:
            findings.append({"check": "contact_info", "status": "pass", "message": "Contact info configured"})

        score = max(0.0, score)
        update_dr_drill(
            drill,
            status="completed",
            findings=findings,
            score=score,
            completed_at=_now(),
        )
        return drill


def run_scheduled_backups() -> list[str]:
    """Enqueue due backup policies. Returns list of enqueued policy IDs."""
    db = get_db()
    now = _now()
    with db.session() as s:
        policies = (
            s.query(BackupPolicy)
            .filter_by(enabled=True)
            .filter((BackupPolicy.next_run_at <= now) | (BackupPolicy.next_run_at.is_(None)))  # type: ignore[operator]
            .all()
        )
    enqueued: list[str] = []
    for policy in policies:
        try:
            from aeon_worker import execute_dr_backup_task
            execute_dr_backup_task.delay(policy.id)
            enqueued.append(policy.id)
        except Exception:  # noqa: BLE001
            BackupManager(policy.workspace_id).run_backup(policy.id)
            enqueued.append(policy.id)
    return enqueued
