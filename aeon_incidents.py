"""
AEON OS Phase 46 — Automated Incident Response
===============================================
Turns detected anomalies into managed incidents and executes runbook actions
such as notifications, webhooks, pausing automation rules, and triggering
other automations.
"""

import logging
import os
from typing import Any

from aeon_db import (
    IncidentRunbook,
    create_incident,
    get_anomaly,
    list_incident_runbooks,
)
from aeon_notify import notify

logger = logging.getLogger("aeon_incidents")


# === Matching =================================================================

def _runbook_matches(runbook: IncidentRunbook, anomaly_type: str, severity: str) -> bool:
    """Return True if a runbook's triggers match the anomaly."""
    if not runbook.enabled:
        return False
    triggers = runbook.triggers or []
    if not triggers:
        return False
    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue
        type_match = trigger.get("anomaly_type") in (anomaly_type, "*", None)
        sev_match = trigger.get("severity") in (severity, "*", None)
        if type_match and sev_match:
            return True
    return False


# === Action execution =======================================================

def _execute_notify_action(action: dict[str, Any], anomaly, incident: Any) -> dict[str, Any]:
    """Send in-app notification(s) for an incident."""
    target = action.get("target", "admins")
    metadata = {
        "anomaly_id": anomaly.id,
        "incident_id": getattr(incident, "id", None),
        "target": target,
    }
    try:
        from aeon_db import get_db

        if target == "admins":
            # Notify the first admin/owner in the workspace as a sensible default.
            db = get_db()
            with db.session() as s:
                from aeon_db import Membership

                admin = (
                    s.query(Membership)
                    .filter(Membership.workspace_id == anomaly.workspace_id)
                    .filter(Membership.role.in_(("OWNER", "ADMIN")))
                    .first()
                )
                user_id = admin.user_id if admin else None
        else:
            user_id = target

        if user_id:
            notify(
                user_id=str(user_id),
                type="system_alert",
                title=action.get("title") or f"Incident: {getattr(incident, 'title', 'anomaly')}",
                body=action.get("body") or getattr(anomaly, "description", "An anomaly has been detected."),
                workspace_id=anomaly.workspace_id,
                metadata=metadata,
            )
        return {"ok": True, "target": target, "user_id": user_id}
    except Exception as exc:
        logger.warning("Notify action failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def _execute_webhook_action(action: dict[str, Any], anomaly, incident: Any) -> dict[str, Any]:
    """POST a JSON payload to a configured webhook URL."""
    url = action.get("url")
    if not url:
        return {"ok": False, "error": "webhook URL missing"}
    payload = {
        "anomaly_id": anomaly.id,
        "incident_id": getattr(incident, "id", None),
        "workspace_id": anomaly.workspace_id,
        "anomaly_type": anomaly.anomaly_type,
        "severity": anomaly.severity,
        "title": anomaly.title,
        "description": anomaly.description,
        "metadata": action.get("payload", {}),
    }
    try:
        import requests

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return {"ok": True, "status_code": response.status_code, "url": url}
    except Exception as exc:
        logger.warning("Webhook action failed for %s: %s", url, exc)
        return {"ok": False, "error": str(exc)}


def _execute_pause_rule_action(action: dict[str, Any], anomaly, incident: Any) -> dict[str, Any]:
    """Attempt to pause an automation rule via the Supabase API."""
    rule_id = action.get("rule_id") or anomaly.source_rule_id
    if not rule_id:
        return {"ok": False, "error": "no rule_id to pause"}

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return {"ok": False, "error": "Supabase not configured"}

    try:
        import requests

        response = requests.patch(
            f"{supabase_url}/rest/v1/automation_rules?id=eq.{rule_id}",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
            },
            json={"enabled": False},
            timeout=10,
        )
        response.raise_for_status()
        return {"ok": True, "rule_id": rule_id, "enabled": False}
    except Exception as exc:
        logger.warning("Pause rule action failed for %s: %s", rule_id, exc)
        return {"ok": False, "error": str(exc)}


def _execute_run_automation_action(action: dict[str, Any], anomaly, incident: Any) -> dict[str, Any]:
    """Trigger another automation rule by ID."""
    rule_id = action.get("rule_id")
    if not rule_id:
        return {"ok": False, "error": "run_automation action requires rule_id"}
    try:
        from aeon_automations import execute_rule_by_id

        event_payload = {
            "type": "incident_response",
            "workspace_id": anomaly.workspace_id,
            "payload": {
                "anomaly_id": anomaly.id,
                "incident_id": getattr(incident, "id", None),
                "rule_id": rule_id,
            },
        }
        return execute_rule_by_id(str(rule_id), event_payload)
    except Exception as exc:
        logger.warning("Run automation action failed for %s: %s", rule_id, exc)
        return {"ok": False, "error": str(exc)}


_ACTION_DISPATCH = {
    "notify": _execute_notify_action,
    "webhook": _execute_webhook_action,
    "pause_rule": _execute_pause_rule_action,
    "run_automation": _execute_run_automation_action,
}


def execute_runbook_actions(runbook: IncidentRunbook, anomaly, incident: Any) -> list[dict[str, Any]]:
    """Execute all actions defined in a runbook."""
    results: list[dict[str, Any]] = []
    for action in runbook.actions or []:
        if not isinstance(action, dict):
            continue
        action_type = action.get("type")
        handler = _ACTION_DISPATCH.get(action_type)
        if not handler:
            results.append({"ok": False, "error": f"unknown action type: {action_type}"})
            continue
        results.append(handler(action, anomaly, incident))
    return results


# === Entrypoint ===============================================================

def handle_anomaly(anomaly) -> dict[str, Any]:
    """Evaluate runbooks for an anomaly and create an incident if matched."""
    anomaly_record = anomaly if hasattr(anomaly, "id") else get_anomaly(str(anomaly))
    if anomaly_record is None:
        return {"ok": False, "error": "anomaly not found"}

    workspace_id = anomaly_record.workspace_id
    runbooks = list_incident_runbooks(workspace_id, enabled_only=True)

    matched_runbooks: list[IncidentRunbook] = []
    for runbook in runbooks:
        if _runbook_matches(runbook, anomaly_record.anomaly_type, anomaly_record.severity):
            matched_runbooks.append(runbook)

    if not matched_runbooks:
        return {"ok": True, "incident_created": False, "matched_runbooks": 0}

    # Create a single incident for the first matching runbook.
    primary_runbook = matched_runbooks[0]
    incident = create_incident(
        workspace_id=workspace_id,
        title=primary_runbook.name,
        severity=anomaly_record.severity,
        status="open",
        root_cause_anomaly_id=anomaly_record.id,
        runbook_id=primary_runbook.id,
        metadata={
            "anomaly_type": anomaly_record.anomaly_type,
            "anomaly_title": anomaly_record.title,
            "matched_runbooks": [rb.id for rb in matched_runbooks],
        },
    )

    # Forward to SIEM integrations (best-effort).
    try:
        from aeon_siem import forward_incident_event
        forward_incident_event(
            workspace_id,
            str(incident.id),
            {
                "title": incident.title,
                "severity": incident.severity,
                "status": incident.status,
                "anomaly_type": anomaly_record.anomaly_type,
                "runbook_id": str(incident.runbook_id),
            },
        )
    except Exception:
        pass

    # Execute actions for each matched runbook.
    all_results: list[dict[str, Any]] = []
    for runbook in matched_runbooks:
        all_results.extend(execute_runbook_actions(runbook, anomaly_record, incident))

    return {
        "ok": True,
        "incident_created": True,
        "incident_id": incident.id,
        "matched_runbooks": len(matched_runbooks),
        "action_results": all_results,
    }


def evaluate_runbooks_for_anomaly(anomaly) -> dict[str, Any]:
    """Backward-compatible alias for ``handle_anomaly``."""
    return handle_anomaly(anomaly)
