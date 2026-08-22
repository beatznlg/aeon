"""
AEON OS Phase 47 — Disaster Recovery API routes.
"""

from typing import Any

from flask import Blueprint, g, jsonify, request

from aeon_auth import require_auth, require_workspace_role
from aeon_db import (
    BackupJob,
    BackupPolicy,
    DRDrill,
    DRPlan,
    RestoreJob,
    create_backup_policy,
    create_dr_plan,
    delete_backup_policy,
    delete_dr_plan,
    get_backup_job,
    get_backup_policy,
    get_dr_plan,
    list_backup_jobs,
    list_backup_policies,
    list_dr_drills,
    list_dr_plans,
    list_restore_jobs,
    update_backup_policy,
    update_dr_plan,
)
from aeon_dr import BackupManager, DRDrillSimulator, run_scheduled_backups

dr_bp = Blueprint("dr", __name__)


# --- Serialization helpers --------------------------------------------------

def _policy_to_dict(p: BackupPolicy) -> dict[str, Any]:
    return {
        "id": p.id,
        "workspace_id": p.workspace_id,
        "name": p.name,
        "schedule": p.schedule,
        "retention_days": p.retention_days,
        "target": p.target,
        "target_config": p.target_config,
        "encryption_enabled": p.encryption_enabled,
        "enabled": p.enabled,
        "last_run_at": p.last_run_at.isoformat() if p.last_run_at else None,
        "next_run_at": p.next_run_at.isoformat() if p.next_run_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _job_to_dict(j: BackupJob) -> dict[str, Any]:
    return {
        "id": j.id,
        "workspace_id": j.workspace_id,
        "policy_id": j.policy_id,
        "status": j.status,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        "size_bytes": j.size_bytes,
        "checksum": j.checksum,
        "storage_key": j.storage_key,
        "metadata": j.metadata_json,
        "error_message": j.error_message,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }


def _restore_to_dict(r: RestoreJob) -> dict[str, Any]:
    return {
        "id": r.id,
        "workspace_id": r.workspace_id,
        "backup_job_id": r.backup_job_id,
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "metadata": r.metadata_json,
        "error_message": r.error_message,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _plan_to_dict(p: DRPlan) -> dict[str, Any]:
    return {
        "id": p.id,
        "workspace_id": p.workspace_id,
        "name": p.name,
        "rto_minutes": p.rto_minutes,
        "rpo_minutes": p.rpo_minutes,
        "target_region": p.target_region,
        "failover_regions": p.failover_regions,
        "contact_info": p.contact_info,
        "enabled": p.enabled,
        "last_drill_at": p.last_drill_at.isoformat() if p.last_drill_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _drill_to_dict(d: DRDrill) -> dict[str, Any]:
    return {
        "id": d.id,
        "workspace_id": d.workspace_id,
        "plan_id": d.plan_id,
        "status": d.status,
        "started_at": d.started_at.isoformat() if d.started_at else None,
        "completed_at": d.completed_at.isoformat() if d.completed_at else None,
        "findings": d.findings,
        "score": d.score,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


# --- Backup policies --------------------------------------------------------

@dr_bp.route("/dr/policies", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def list_backup_policies_endpoint():
    ctx = g.user
    rows = list_backup_policies(ctx.get("workspace_id"))
    return jsonify({"ok": True, "policies": [_policy_to_dict(p) for p in rows]})


@dr_bp.route("/dr/policies", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def create_backup_policy_endpoint():
    ctx = g.user
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    policy = create_backup_policy(
        workspace_id=ctx.get("workspace_id"),
        name=name,
        schedule=data.get("schedule", "0 2 * * *"),
        retention_days=data.get("retention_days", 30),
        target=data.get("target", "local"),
        target_config=data.get("target_config", {}),
        encryption_enabled=data.get("encryption_enabled", True),
        enabled=data.get("enabled", True),
    )
    return jsonify({"ok": True, "policy": _policy_to_dict(policy)}), 201


@dr_bp.route("/dr/policies/<policy_id>", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def get_backup_policy_endpoint(policy_id: str):
    ctx = g.user
    policy = get_backup_policy(policy_id, workspace_id=ctx.get("workspace_id"))
    if not policy:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "policy": _policy_to_dict(policy)})


@dr_bp.route("/dr/policies/<policy_id>", methods=["PATCH"])
@require_auth
@require_workspace_role("ADMIN")
def update_backup_policy_endpoint(policy_id: str):
    ctx = g.user
    policy = get_backup_policy(policy_id, workspace_id=ctx.get("workspace_id"))
    if not policy:
        return jsonify({"ok": False, "error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    policy = update_backup_policy(
        policy,
        name=data.get("name"),
        schedule=data.get("schedule"),
        retention_days=data.get("retention_days"),
        target=data.get("target"),
        target_config=data.get("target_config"),
        encryption_enabled=data.get("encryption_enabled"),
        enabled=data.get("enabled"),
    )
    return jsonify({"ok": True, "policy": _policy_to_dict(policy)})


@dr_bp.route("/dr/policies/<policy_id>", methods=["DELETE"])
@require_auth
@require_workspace_role("ADMIN")
def delete_backup_policy_endpoint(policy_id: str):
    ctx = g.user
    deleted = delete_backup_policy(policy_id, workspace_id=ctx.get("workspace_id"))
    if not deleted:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True})


@dr_bp.route("/dr/policies/<policy_id>/run", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def run_backup_policy_endpoint(policy_id: str):
    ctx = g.user
    policy = get_backup_policy(policy_id, workspace_id=ctx.get("workspace_id"))
    if not policy:
        return jsonify({"ok": False, "error": "not found"}), 404
    manager = BackupManager(ctx.get("workspace_id"))
    job = manager.run_backup(policy_id)
    return jsonify({"ok": True, "job": _job_to_dict(job)}), 202


@dr_bp.route("/dr/policies/<policy_id>/retention", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def apply_retention_endpoint(policy_id: str):
    ctx = g.user
    policy = get_backup_policy(policy_id, workspace_id=ctx.get("workspace_id"))
    if not policy:
        return jsonify({"ok": False, "error": "not found"}), 404
    manager = BackupManager(ctx.get("workspace_id"))
    deleted = manager.apply_retention(policy_id)
    return jsonify({"ok": True, "deleted_keys": deleted})


# --- Backup jobs ------------------------------------------------------------

@dr_bp.route("/dr/backups", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def list_backup_jobs_endpoint():
    ctx = g.user
    limit = min(1000, max(1, request.args.get("limit", 100, type=int)))
    rows = list_backup_jobs(ctx.get("workspace_id"), limit=limit)
    return jsonify({"ok": True, "jobs": [_job_to_dict(j) for j in rows]})


@dr_bp.route("/dr/backups/<job_id>/verify", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def verify_backup_endpoint(job_id: str):
    """Run a read-only integrity check for a workspace backup."""
    ctx = g.user
    job = get_backup_job(job_id, workspace_id=ctx.get("workspace_id"))
    if not job:
        return jsonify({"ok": False, "error": "not found"}), 404
    manager = BackupManager(ctx.get("workspace_id"))
    verification = manager.verify_backup(job_id)
    return jsonify({"ok": True, "verification": verification})


@dr_bp.route("/dr/backups/<job_id>/restore", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def restore_backup_endpoint(job_id: str):
    ctx = g.user
    job = get_backup_job(job_id, workspace_id=ctx.get("workspace_id"))
    if not job:
        return jsonify({"ok": False, "error": "not found"}), 404
    manager = BackupManager(ctx.get("workspace_id"))
    restore = manager.restore_backup(job_id)
    return jsonify({"ok": True, "restore": _restore_to_dict(restore)}), 202


@dr_bp.route("/dr/restores", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def list_restore_jobs_endpoint():
    ctx = g.user
    limit = min(1000, max(1, request.args.get("limit", 100, type=int)))
    rows = list_restore_jobs(ctx.get("workspace_id"), limit=limit)
    return jsonify({"ok": True, "restores": [_restore_to_dict(r) for r in rows]})


# --- DR plans ---------------------------------------------------------------

@dr_bp.route("/dr/plans", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def list_dr_plans_endpoint():
    ctx = g.user
    rows = list_dr_plans(ctx.get("workspace_id"))
    return jsonify({"ok": True, "plans": [_plan_to_dict(p) for p in rows]})


@dr_bp.route("/dr/plans", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def create_dr_plan_endpoint():
    ctx = g.user
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    plan = create_dr_plan(
        workspace_id=ctx.get("workspace_id"),
        name=name,
        rto_minutes=data.get("rto_minutes", 60),
        rpo_minutes=data.get("rpo_minutes", 60),
        target_region=data.get("target_region", "primary"),
        failover_regions=data.get("failover_regions", []),
        contact_info=data.get("contact_info", {}),
        enabled=data.get("enabled", True),
    )
    return jsonify({"ok": True, "plan": _plan_to_dict(plan)}), 201


@dr_bp.route("/dr/plans/<plan_id>", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def get_dr_plan_endpoint(plan_id: str):
    ctx = g.user
    plan = get_dr_plan(plan_id, workspace_id=ctx.get("workspace_id"))
    if not plan:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "plan": _plan_to_dict(plan)})


@dr_bp.route("/dr/plans/<plan_id>", methods=["PATCH"])
@require_auth
@require_workspace_role("ADMIN")
def update_dr_plan_endpoint(plan_id: str):
    ctx = g.user
    plan = get_dr_plan(plan_id, workspace_id=ctx.get("workspace_id"))
    if not plan:
        return jsonify({"ok": False, "error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    plan = update_dr_plan(
        plan,
        name=data.get("name"),
        rto_minutes=data.get("rto_minutes"),
        rpo_minutes=data.get("rpo_minutes"),
        target_region=data.get("target_region"),
        failover_regions=data.get("failover_regions"),
        contact_info=data.get("contact_info"),
        enabled=data.get("enabled"),
    )
    return jsonify({"ok": True, "plan": _plan_to_dict(plan)})


@dr_bp.route("/dr/plans/<plan_id>", methods=["DELETE"])
@require_auth
@require_workspace_role("ADMIN")
def delete_dr_plan_endpoint(plan_id: str):
    ctx = g.user
    deleted = delete_dr_plan(plan_id, workspace_id=ctx.get("workspace_id"))
    if not deleted:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True})


@dr_bp.route("/dr/plans/<plan_id>/drill", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def run_dr_drill_endpoint(plan_id: str):
    ctx = g.user
    plan = get_dr_plan(plan_id, workspace_id=ctx.get("workspace_id"))
    if not plan:
        return jsonify({"ok": False, "error": "not found"}), 404
    simulator = DRDrillSimulator(ctx.get("workspace_id"))
    drill = simulator.simulate_failover(plan_id)
    return jsonify({"ok": True, "drill": _drill_to_dict(drill)}), 202


# --- DR drills --------------------------------------------------------------

@dr_bp.route("/dr/drills", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def list_dr_drills_endpoint():
    ctx = g.user
    limit = min(1000, max(1, request.args.get("limit", 100, type=int)))
    rows = list_dr_drills(ctx.get("workspace_id"), limit=limit)
    return jsonify({"ok": True, "drills": [_drill_to_dict(d) for d in rows]})


# --- Scheduled run ------------------------------------------------------------

@dr_bp.route("/dr/scheduled/run", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def run_scheduled_backups_endpoint():
    enqueued = run_scheduled_backups()
    return jsonify({"ok": True, "enqueued": enqueued})
