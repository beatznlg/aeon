"""
AEON OS Phase 43 — Distributed Task Worker
============================================
Celery-based worker for running AEON automations outside the Flask web process.
Uses Redis as broker/backend when AEON_REDIS_URL is configured; otherwise falls
back to synchronous (eager) execution for local development.

Run a worker:
    celery -A aeon_worker worker --loglevel=info

Run the periodic scheduler (only one replica in production):
    celery -A aeon_worker beat --loglevel=info
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from celery import Celery

# Broker / backend configuration
# When no Redis URL is provided, run tasks eagerly (synchronously) for local dev.
_BROKER_URL = os.environ.get("AEON_REDIS_URL") or os.environ.get("REDIS_URL")
_BACKEND_URL = os.environ.get("AEON_CELERY_RESULT_BACKEND") or _BROKER_URL or "memory://"

# Celery needs a broker URL even in eager mode; point it to memory when no Redis is configured.
if not _BROKER_URL:
    _BROKER_URL = "memory://"

_REDIS_CONFIGURED = _BROKER_URL.startswith("redis://") or _BROKER_URL.startswith("rediss://")

app = Celery("aeon")
app.conf.update(
    broker_url=_BROKER_URL,
    result_backend=_BACKEND_URL,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=not _REDIS_CONFIGURED,
    task_store_eager_results=True,
    beat_schedule={},
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

logger = logging.getLogger("aeon_worker")


@app.task(bind=True, max_retries=3, default_retry_delay=10)
def execute_automation_task(self, rule_id: str, event_payload: dict | None = None) -> dict:
    """Execute a single automation rule in a worker context.

    Args:
        rule_id: UUID of the automation rule.
        event_payload: Optional event that triggered the rule.

    Returns:
        Dict describing the execution outcome.
    """
    event_payload = event_payload or {}
    logger.info("Executing automation rule %s", rule_id)

    try:
        # Import here to keep worker boot light and avoid circular imports
        from aeon_automations import execute_rule_by_id

        result = execute_rule_by_id(rule_id, event_payload)
        return {"ok": True, "rule_id": rule_id, "result": result}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Automation execution failed for rule %s", rule_id)
        # Retry with exponential backoff unless this is the last attempt
        try:
            self.retry(exc=exc)
        except Exception:  # noqa: BLE001
            return {"ok": False, "rule_id": rule_id, "error": str(exc)}


@app.task(bind=True, max_retries=3, default_retry_delay=10)
def run_scheduled_rule_tick(self, rule_id: str) -> dict:
    """Periodic task entrypoint used by Celery Beat to run a scheduled rule."""
    return execute_automation_task.delay(rule_id, {"source": "schedule", "triggered_at": _now_iso()}).get()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_automation(rule_id: str, event_payload: dict | None = None) -> str | None:
    """Enqueue an automation execution task if Redis is available, otherwise run eagerly.

    Returns the Celery task ID, or None in eager mode.
    """
    if app.conf.task_always_eager:
        execute_automation_task(rule_id, event_payload)
        return None
    if _REDIS_CONFIGURED:
        task = execute_automation_task.delay(rule_id, event_payload)
        return str(task.id)
    execute_automation_task.apply_async(args=(rule_id, event_payload))
    return None


def schedule_automation_tick(rule_id: str) -> str | None:
    """Enqueue a scheduled tick for a cron-based rule."""
    if app.conf.task_always_eager:
        run_scheduled_rule_tick(rule_id)
        return None
    if _REDIS_CONFIGURED:
        task = run_scheduled_rule_tick.delay(rule_id)
        return str(task.id)
    run_scheduled_rule_tick.apply_async(args=(rule_id,))
    return None


@app.task(bind=True, max_retries=3, default_retry_delay=10)
def execute_dr_backup_task(self, policy_id: str) -> dict:
    """Run a backup for the given policy."""
    try:
        from aeon_db import get_backup_policy
        from aeon_dr import BackupManager
        policy = get_backup_policy(policy_id)
        if not policy:
            return {"ok": False, "error": "policy not found"}
        job = BackupManager(policy.workspace_id).run_backup(policy_id)
        return {"ok": True, "job_id": job.id, "status": job.status}
    except Exception as exc:  # noqa: BLE001
        logger.exception("DR backup failed for policy %s", policy_id)
        try:
            self.retry(exc=exc)
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}


@app.task(bind=True, max_retries=3, default_retry_delay=10)
def execute_dr_restore_task(self, backup_job_id: str) -> dict:
    """Run a restore for the given backup job."""
    try:
        from aeon_db import get_backup_job
        from aeon_dr import BackupManager
        job = get_backup_job(backup_job_id)
        if not job:
            return {"ok": False, "error": "backup job not found"}
        restore = BackupManager(job.workspace_id).restore_backup(backup_job_id)
        return {"ok": True, "restore_id": restore.id, "status": restore.status}
    except Exception as exc:  # noqa: BLE001
        logger.exception("DR restore failed for job %s", backup_job_id)
        try:
            self.retry(exc=exc)
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
