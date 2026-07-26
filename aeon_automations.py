"""
AEON Event-Driven Automations (Phase 18)
==========================================
Lightweight rule engine that listens to activity events and triggers
actions: webhooks, swarms, or workflows.

Rules are stored in Supabase `automation_rules`. Executions are logged in
`automation_executions`. The engine is invoked from `aeon_notify.log_activity`
after an event is persisted/broadcast.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger("aeon_automations")

# Supported event types that can trigger automations
TRIGGER_EVENT_TYPES = frozenset({
    "swarm_status",
    "workflow_status",
    "notification",
    "api_key_created",
    "api_key_revoked",
    "workspace_activity",
    "system",
})


def _supabase_headers() -> dict[str, str] | None:
    """Return headers for Supabase service-role requests, or None if not configured."""
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not service_key:
        return None
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def _get_db_url() -> str | None:
    return os.environ.get("SUPABASE_URL")


def _fetch_rules_for_event(event_type: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
    """Load enabled automation rules matching the event type and workspace."""
    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return []

    try:
        import requests

        query = f"type=eq.{event_type}&enabled=eq.true"
        if workspace_id:
            query += f"&workspace_id=eq.{workspace_id}"
        else:
            query += "&workspace_id=is.null"

        r = requests.get(
            f"{db_url}/rest/v1/automation_rules?{query}",
            headers=headers,
            timeout=10,
        )
        r.raise_for_status()
        return r.json() or []
    except Exception as exc:
        logger.warning("Failed to fetch automation rules for %s: %s", event_type, exc)
        return []


def _condition_matches(condition: dict[str, Any] | None, payload: dict[str, Any]) -> bool:
    """Evaluate a simple condition against an event payload.

    Condition format supports equality checks on top-level keys:
        {"status": "failed", "ok": false}
    Returns True if the payload matches all specified conditions.
    """
    if not condition:
        return True
    for key, expected in condition.items():
        actual = payload.get(key) if isinstance(payload, dict) else None
        if actual != expected:
            return False
    return True


def _execute_action(rule: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Execute the action configured for a rule."""
    action_type = rule.get("action_type")
    action_config = rule.get("action_config") or {}
    event_payload = event.get("payload") or {}

    if action_type == "webhook":
        return _execute_webhook(action_config, event)
    if action_type == "swarm":
        return _execute_swarm(action_config, event_payload)
    if action_type == "workflow":
        return _execute_workflow(action_config, event_payload)
    return {"ok": False, "error": f"unsupported action_type {action_type}"}


def _execute_webhook(action_config: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    url = action_config.get("url")
    if not url:
        return {"ok": False, "error": "webhook URL missing"}

    try:
        import requests

        r = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "type": event.get("type"),
                "payload": event.get("payload"),
                "user_id": event.get("user_id"),
                "workspace_id": event.get("workspace_id"),
                "timestamp": event.get("timestamp"),
            },
            timeout=10,
        )
        r.raise_for_status()
        return {"ok": True, "status_code": r.status_code}
    except Exception as exc:
        logger.warning("Webhook action failed for %s: %s", url, exc)
        return {"ok": False, "error": str(exc)}


def _execute_swarm(action_config: dict[str, Any], event_payload: dict[str, Any]) -> dict[str, Any]:
    backend_url = os.environ.get("AEON_PYTHON_URL") or "http://localhost:5000"
    try:
        import requests

        r = requests.post(
            f"{backend_url}/swarm/run",
            headers={"Content-Type": "application/json"},
            json={
                "app_ids": action_config.get("app_ids", ["researcher", "writer"]),
                "prompt": action_config.get("prompt", "Act on this event"),
                "roles": action_config.get("roles"),
            },
            timeout=60,
        )
        r.raise_for_status()
        return {"ok": True, "status_code": r.status_code, "data": r.json()}
    except Exception as exc:
        logger.warning("Swarm action failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def _execute_workflow(action_config: dict[str, Any], event_payload: dict[str, Any]) -> dict[str, Any]:
    backend_url = os.environ.get("AEON_PYTHON_URL") or "http://localhost:5000"
    workflow_id = action_config.get("workflow_id")
    if not workflow_id:
        return {"ok": False, "error": "workflow_id missing"}
    try:
        import requests

        r = requests.post(
            f"{backend_url}/workflows/{workflow_id}/run",
            headers={"Content-Type": "application/json"},
            json={
                "initial_input": action_config.get("initial_input", ""),
            },
            timeout=60,
        )
        r.raise_for_status()
        return {"ok": True, "status_code": r.status_code, "data": r.json()}
    except Exception as exc:
        logger.warning("Workflow action failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def _log_execution(rule: dict[str, Any], event: dict[str, Any], result: dict[str, Any]) -> None:
    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return

    try:
        import requests

        requests.post(
            f"{db_url}/rest/v1/automation_executions",
            headers=headers,
            json={
                "rule_id": rule.get("id"),
                "event_type": event.get("type"),
                "event_payload": json.dumps(event.get("payload") or {}),
                "status": "triggered" if result.get("ok") else "failed",
                "result": json.dumps(result),
                "workspace_id": rule.get("workspace_id"),
                "user_id": event.get("user_id"),
            },
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Failed to log automation execution: %s", exc)


def evaluate_automations(
    event_type: str,
    payload: dict[str, Any],
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    """Evaluate all enabled automation rules for an event and execute matches."""
    if event_type not in TRIGGER_EVENT_TYPES:
        return []

    event = {
        "type": event_type,
        "payload": payload,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "timestamp": None,
    }

    rules = _fetch_rules_for_event(event_type, workspace_id)
    results: list[dict[str, Any]] = []
    for rule in rules:
        condition = rule.get("condition")
        if not _condition_matches(condition, payload):
            continue

        result = _execute_action(rule, event)
        _log_execution(rule, event, result)
        results.append({
            "rule_id": rule.get("id"),
            "rule_name": rule.get("name"),
            "result": result,
        })

    return results
