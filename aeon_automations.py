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
import threading
from datetime import datetime, timezone, timedelta
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
    "inbound_webhook",
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
    return execute_action_by_type(action_type, action_config, event)


def execute_action_by_type(
    action_type: str | None,
    action_config: dict[str, Any],
    event: dict[str, Any],
) -> dict[str, Any]:
    """Execute an action given its type, config, and triggering event."""
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


def _log_execution_with_status(
    rule: dict[str, Any],
    event: dict[str, Any],
    status: str,
    result: dict[str, Any],
) -> None:
    """Log an automation execution with an explicit status string."""
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
                "status": status,
                "result": json.dumps(result),
                "workspace_id": rule.get("workspace_id"),
                "user_id": event.get("user_id"),
            },
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Failed to log automation execution: %s", exc)


def _create_approval_request(rule: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Create a pending approval request for a rule that requires HITL approval."""
    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return {"ok": False, "error": "Supabase not configured"}

    try:
        import requests

        payload = {
            "rule_id": rule.get("id"),
            "event_type": event.get("type"),
            "event_payload": json.dumps(event.get("payload") or {}),
            "action_type": rule.get("action_type"),
            "action_config": json.dumps(rule.get("action_config") or {}),
            "status": "pending",
            "workspace_id": rule.get("workspace_id"),
            "user_id": event.get("user_id"),
            "requested_by": event.get("user_id"),
        }
        r = requests.post(
            f"{db_url}/rest/v1/approval_requests",
            headers={**headers, "Prefer": "return=representation"},
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        created = r.json()
        return {"ok": True, "approval": created[0] if created else None}
    except Exception as exc:
        logger.warning("Failed to create approval request: %s", exc)
        return {"ok": False, "error": str(exc)}


def _notify_approval_required(rule: dict[str, Any], approval_id: str, event: dict[str, Any]) -> None:
    """Send a notification that an automation is awaiting human approval."""
    from aeon_notify import notify

    workspace_id = rule.get("workspace_id")
    user_id = event.get("user_id")
    if user_id:
        notify(
            user_id=user_id,
            type="approval_requested",
            title=f"Approval Required: {rule.get('name', 'Automation')}",
            body=f"An automation rule '{rule.get('name')}' fired and requires your approval before proceeding.",
            icon="✋",
            link=f"/os/approvals?id={approval_id}",
            workspace_id=workspace_id,
            metadata={
                "approval_id": approval_id,
                "rule_id": rule.get("id"),
                "event_type": event.get("type"),
            },
        )
    _notify_slack_approval(rule, str(approval_id), event)


def _notify_slack_approval(rule: dict[str, Any], approval_id: str, event: dict[str, Any]) -> None:
    """Send an interactive Slack Block Kit message for an approval request."""
    import urllib.parse

    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    if not bot_token:
        return

    db_url = _get_db_url()
    headers = _supabase_headers()
    channel = os.environ.get("SLACK_APPROVALS_CHANNEL")
    if not channel and db_url and headers:
        try:
            import requests
            ws = requests.get(
                f"{db_url}/rest/v1/workspaces",
                headers=headers,
                params={"id": f"eq.{rule.get('workspace_id')}", "select": "slack_channel"},
                timeout=10,
            )
            ws.raise_for_status()
            rows = ws.json() or []
            if rows:
                channel = rows[0].get("slack_channel") or os.environ.get("SLACK_APPROVALS_CHANNEL")
        except Exception as exc:
            logger.debug("Could not fetch workspace Slack channel: %s", exc)

    if not channel:
        return

    public_url = os.environ.get("AEON_PUBLIC_URL") or ""
    resolve_url = f"{public_url.rstrip('/')}/slack/interactions"
    try:
        import requests

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*AEON Approval Required*\n"
                        f"Rule: {rule.get('name')}\n"
                        f"Event: {event.get('type')}\n"
                        f"Action: {rule.get('action_type')}"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                        "style": "primary",
                        "value": json.dumps({"approval_id": approval_id, "decision": "approved"}),
                        "action_id": "approve_request",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                        "style": "danger",
                        "value": json.dumps({"approval_id": approval_id, "decision": "rejected"}),
                        "action_id": "reject_request",
                    },
                ],
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"<{resolve_url}|Resolve in AEON>"},
                ],
            },
        ]

        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json",
            },
            json={
                "channel": channel,
                "text": f"AEON approval required: {rule.get('name')}",
                "blocks": blocks,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Slack approval notification failed: %s", data.get("error"))
    except Exception as exc:
        logger.warning("Failed to send Slack approval message: %s", exc)


def resolve_approval(
    approval_id: str,
    decision: str,
    resolver_user_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Resolve a pending approval request.

    decision must be 'approved' or 'rejected'. If approved, the deferred action
    is executed and the result stored on the approval request.
    """
    if decision not in {"approved", "rejected"}:
        return {"ok": False, "error": "decision must be approved or rejected"}

    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return {"ok": False, "error": "Supabase not configured"}

    try:
        import requests

        # Fetch the approval request
        r = requests.get(
            f"{db_url}/rest/v1/approval_requests?id=eq.{approval_id}",
            headers=headers,
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json() or []
        if not rows:
            return {"ok": False, "error": "approval request not found"}
        approval = rows[0]

        if approval["status"] != "pending":
            return {"ok": False, "error": f"approval request already {approval['status']}"}

        if decision == "rejected":
            update = {
                "status": "rejected",
                "approved_by": resolver_user_id,
                "reason": reason or "",
                "resolved_at": "now",
            }
            requests.patch(
                f"{db_url}/rest/v1/approval_requests?id=eq.{approval_id}",
                headers=headers,
                json=update,
                timeout=10,
            ).raise_for_status()
            return {"ok": True, "status": "rejected", "approval_id": approval_id}

        # approved: execute the deferred action
        event = {
            "type": approval["event_type"],
            "payload": json.loads(approval.get("event_payload") or "{}"),
            "user_id": approval.get("user_id"),
            "workspace_id": approval.get("workspace_id"),
            "timestamp": None,
        }
        action_config = json.loads(approval.get("action_config") or "{}")
        result = execute_action_by_type(approval.get("action_type"), action_config, event)

        update = {
            "status": "approved",
            "approved_by": resolver_user_id,
            "reason": reason or "",
            "result": json.dumps(result),
            "resolved_at": "now",
        }
        requests.patch(
            f"{db_url}/rest/v1/approval_requests?id=eq.{approval_id}",
            headers=headers,
            json=update,
            timeout=10,
        ).raise_for_status()

        # Log the execution as triggered
        rule = {
            "id": approval.get("rule_id"),
            "workspace_id": approval.get("workspace_id"),
        }
        _log_execution_with_status(rule, event, "triggered", result)

        return {
            "ok": True,
            "status": "approved",
            "approval_id": approval_id,
            "result": result,
        }
    except Exception as exc:
        logger.warning("Failed to resolve approval %s: %s", approval_id, exc)
        return {"ok": False, "error": str(exc)}


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

        # Phase 19: HITL approval checkpoint
        if rule.get("approval_required"):
            approval_result = _create_approval_request(rule, event)
            if approval_result.get("ok"):
                approval = approval_result.get("approval") or {}
                approval_id = approval.get("id")
                if approval_id:
                    _notify_approval_required(rule, str(approval_id), event)
                _log_execution_with_status(
                    rule,
                    event,
                    "pending_approval",
                    {"approval_id": approval_id, "status": "pending"},
                )
                results.append({
                    "rule_id": rule.get("id"),
                    "rule_name": rule.get("name"),
                    "result": {
                        "ok": True,
                        "status": "pending_approval",
                        "approval_id": approval_id,
                    },
                })
                continue

        result = _execute_action(rule, event)
        _log_execution(rule, event, result)
        results.append({
            "rule_id": rule.get("id"),
            "rule_name": rule.get("name"),
            "result": result,
        })

    return results


# ── Scheduled / Cron Automations (Phase 20) ──────────────────────────────────

def _compute_next_run(cron_expression: str, base_time: datetime | None = None) -> datetime | None:
    """Return the next datetime a cron expression should fire.

    Uses ``croniter`` when available; otherwise falls back to a simple
    once-per-minute parser that only supports the special expression ``* * * * *``.
    """
    base = base_time or datetime.now(timezone.utc)
    try:
        from croniter import croniter
        try:
            return croniter(cron_expression, base).get_next(datetime)
        except Exception as exc:
            logger.warning("Invalid cron expression %r: %s", cron_expression, exc)
            return None
    except ImportError:
        logger.debug("croniter not installed; using minimal cron fallback")
        if cron_expression.strip() == "* * * * *":
            return base + timedelta(minutes=1)
        logger.warning("Cannot parse cron expression %r without croniter", cron_expression)
        return None


class ScheduledAutomationScheduler:
    """Background scheduler that runs automation rules on a cron schedule."""

    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="aeon-scheduled-automations",
        )
        self._thread.start()
        logger.info("Scheduled automation scheduler started (tick every %ss)", self.interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.warning("Scheduled automation tick failed: %s", exc)
            self._stop_event.wait(self.interval_seconds)

    def _tick(self) -> None:
        db_url = _get_db_url()
        headers = _supabase_headers()
        if not db_url or not headers:
            return

        import requests

        now = datetime.now(timezone.utc).isoformat()
        try:
            r = requests.get(
                f"{db_url}/rest/v1/automation_rules",
                headers=headers,
                params={
                    "enabled": "eq.true",
                    "schedule_type": "eq.cron",
                    "next_run_at": f"lte.{now}",
                    "order": "next_run_at.asc",
                },
                timeout=10,
            )
            r.raise_for_status()
            rules = r.json() or []
        except Exception as exc:
            logger.warning("Failed to fetch due scheduled rules: %s", exc)
            return

        for rule in rules:
            self._run_rule(rule)

    def _run_rule(self, rule: dict[str, Any]) -> None:
        """Execute a single scheduled rule and update its run tracking."""
        db_url = _get_db_url()
        headers = _supabase_headers()
        now_dt = datetime.now(timezone.utc)
        event = {
            "type": rule.get("event_type") or "system",
            "payload": {"schedule_type": "cron", "rule_id": rule.get("id")},
            "user_id": rule.get("created_by"),
            "workspace_id": rule.get("workspace_id"),
            "timestamp": now_dt.isoformat(),
        }

        # If approval is required, create a pending request instead of executing.
        if rule.get("approval_required"):
            approval_result = _create_approval_request(rule, event)
            _log_execution_with_status(
                rule,
                event,
                "pending_approval",
                {"approval_id": (approval_result.get("approval") or {}).get("id"), "status": "pending"},
            )
        else:
            result = _execute_action(rule, event)
            _log_execution_with_status(rule, event, "triggered" if result.get("ok") else "failed", result)

        # Advance last_run_at and next_run_at
        next_run = _compute_next_run(rule.get("cron_expression", ""), now_dt)
        update = {"last_run_at": "now"}
        if next_run:
            update["next_run_at"] = next_run.isoformat()
        else:
            update["next_run_at"] = None

        if db_url and headers:
            try:
                import requests
                requests.patch(
                    f"{db_url}/rest/v1/automation_rules?id=eq.{rule.get('id')}",
                    headers=headers,
                    json=update,
                    timeout=10,
                ).raise_for_status()
            except Exception as exc:
                logger.warning("Failed to update scheduled rule timing: %s", exc)


# Global scheduler instance
_scheduler = ScheduledAutomationScheduler()


def start_scheduler(interval_seconds: int = 60) -> None:
    """Start the global scheduled automation scheduler."""
    _scheduler.interval_seconds = interval_seconds
    _scheduler.start()


def stop_scheduler() -> None:
    """Stop the global scheduled automation scheduler."""
    _scheduler.stop()
