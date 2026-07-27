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
import re
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


def _get_path(payload: Any, path: str) -> Any:
    """Return the value at a dotted path in a nested dict/list, or None if absent.

    Supports list indices (e.g. ``steps.0.data``).
    """
    value = payload
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and 0 <= int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def _operator_matches(actual: Any, operator_spec: dict[str, Any]) -> bool:
    """Evaluate a MongoDB-style operator spec against an actual value.

    Supports: $eq, $neq, $gt, $lt, $gte, $lte, $in, $contains, $exists, $regex.
    Multiple operators in the same spec are AND-ed together.
    """
    for op, expected in operator_spec.items():
        match op:
            case "$eq":
                if actual != expected:
                    return False
            case "$neq":
                if actual == expected:
                    return False
            case "$gt":
                try:
                    if actual is None or expected is None or not (actual > expected):
                        return False
                except TypeError:
                    return False
            case "$lt":
                try:
                    if actual is None or expected is None or not (actual < expected):
                        return False
                except TypeError:
                    return False
            case "$gte":
                try:
                    if actual is None or expected is None or not (actual >= expected):
                        return False
                except TypeError:
                    return False
            case "$lte":
                try:
                    if actual is None or expected is None or not (actual <= expected):
                        return False
                except TypeError:
                    return False
            case "$in":
                if not isinstance(expected, (list, tuple, set)):
                    return False
                if actual not in expected:
                    return False
            case "$contains":
                if isinstance(actual, str) and isinstance(expected, str):
                    if expected not in actual:
                        return False
                elif isinstance(actual, (list, tuple)):
                    if expected not in actual:
                        return False
                else:
                    return False
            case "$exists":
                exists = actual is not None
                if bool(expected) != exists:
                    return False
            case "$regex":
                if not isinstance(actual, str):
                    return False
                try:
                    if not re.search(expected, actual):
                        return False
                except re.error:
                    return False
            case _:
                # Unknown operator: treat as no match rather than raising.
                return False
    return True


def evaluate_condition(condition: Any, payload: dict[str, Any]) -> bool:
    """Evaluate an advanced condition against an event payload.

    Supports:
        - Top-level equality (backward compatible):
            {"status": "failed"}
        - MongoDB-style operators on fields:
            {"amount": {"$gt": 1000}}
        - Logical operators at top level:
            {"$or": [{"status": "failed"}, {"severity": {"$gte": 5}}]}
            {"$and": [{"type": "error"}, {"$not": {"ignored": true}}]}
        - Dotted nested field paths:
            {"user.plan": "premium"}

    Returns True if the payload matches the condition.
    """
    if not condition:
        return True
    if not isinstance(condition, dict):
        return bool(condition)

    for key, expected in condition.items():
        if key == "$and":
            if not isinstance(expected, list):
                return False
            return all(evaluate_condition(item, payload) for item in expected)
        if key == "$or":
            if not isinstance(expected, list):
                return False
            return any(evaluate_condition(item, payload) for item in expected)
        if key == "$not":
            return not evaluate_condition(expected, payload)

        actual = _get_path(payload, key)
        if isinstance(expected, dict) and expected and any(k.startswith("$") for k in expected):
            if not _operator_matches(actual, expected):
                return False
        elif actual != expected:
            return False

    return True


def _condition_matches(condition: dict[str, Any] | None, payload: dict[str, Any]) -> bool:
    """Backward-compatible alias for evaluate_condition.

    Condition format supports equality checks and advanced operators:
        {"status": "failed"}
        {"amount": {"$gt": 1000}}
        {"$or": [{"status": "failed"}, {"severity": {"$gte": 5}}]}
    Returns True if the payload matches the condition.
    """
    return evaluate_condition(condition, payload)


def _is_in_cooldown(rule: dict[str, Any]) -> bool:
    """Return True if the rule is still within its configured cooldown window."""
    cooldown = rule.get("cooldown_minutes") or 0
    if not cooldown:
        return False
    last_triggered = rule.get("last_triggered_at")
    if not last_triggered:
        return False
    try:
        if isinstance(last_triggered, str):
            last = datetime.fromisoformat(last_triggered.replace("Z", "+00:00"))
        elif isinstance(last_triggered, datetime):
            last = last_triggered
        else:
            return False
        return datetime.now(timezone.utc) - last < timedelta(minutes=int(cooldown))
    except Exception:
        return False


def _update_last_triggered(rule: dict[str, Any]) -> None:
    """Persist the current time as the rule's last triggered timestamp."""
    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return
    try:
        import requests

        requests.patch(
            f"{db_url}/rest/v1/automation_rules?id=eq.{rule.get('id')}",
            headers=headers,
            json={"last_triggered_at": "now"},
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Failed to update last_triggered_at for rule %s: %s", rule.get("id"), exc)


def _execute_action(
    rule: dict[str, Any],
    event: dict[str, Any],
    *,
    start_index: int = 0,
    initial_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute the action(s) configured for a rule.

    Supports an ordered ``actions`` array of action steps. Each step's output is
    appended to ``steps`` and made available to subsequent steps via templates
    like ``{{ steps.0.data.summary }}``. Falls back to the legacy single-action
    ``action_type``/``action_config`` fields when ``actions`` is absent or empty.

    Phase 29: each step may define ``on_error`` (a fallback action) and
    ``continue_on_error`` (bool). When a step fails, the fallback action runs
    with ``{{ error.message }}`` and ``{{ error.step }}`` available in context.
    If ``continue_on_error`` is true, execution proceeds to the next step.

    Phase 30: supports ``delay`` steps that put the execution to sleep until a
    later time. When a delay is hit, returns ``status == "sleeping"`` with the
    ``pending_step_index`` and ``resume_at`` timestamp so the scheduler can
    resume later.
    """
    actions = rule.get("actions") or []
    if not actions:
        actions = [
            {
                "type": rule.get("action_type"),
                "config": rule.get("action_config") or {},
            }
        ]

    steps: list[dict[str, Any]] = list(initial_steps) if initial_steps else []
    context = {"event": event, "rule": rule, "steps": steps}

    for idx, action in enumerate(actions):
        if idx < start_index:
            continue

        action_type = action.get("type") or action.get("action_type")
        action_config = action.get("config") or action.get("action_config") or {}
        run_if = action.get("run_if")
        if run_if:
            condition_context = {"event": event, "rule": rule, "steps": steps}
            if not evaluate_condition(run_if, condition_context):
                steps.append({"ok": True, "skipped": True, "condition": run_if})
                continue

        on_error = action.get("on_error")
        continue_on_error = bool(action.get("continue_on_error"))

        # Phase 30: delay steps are handled before loops because they don't
        # perform real work; they just schedule a resume time.
        if action_type == "delay":
            result = execute_action_by_type(action_type, action_config, context)
            steps.append(result)
            if result.get("status") == "sleeping":
                return {
                    "ok": True,
                    "status": "sleeping",
                    "steps": steps,
                    "pending_step_index": idx + 1,
                    "resume_at": result.get("resume_at"),
                }
            continue

        loop_over = action.get("loop_over")
        if loop_over:
            loop_items = _resolve_loop_expression(loop_over, context)
            if not isinstance(loop_items, (list, tuple)):
                result = {"ok": False, "error": f"loop_over did not resolve to a list: {loop_over}"}
                steps.append(result)
                fallback = _execute_on_error(action, on_error, idx, result["error"], context)
                if fallback:
                    result["on_error_result"] = fallback
                if continue_on_error and (fallback or fallback is None):
                    continue
                return {
                    "ok": False,
                    "status": "failed",
                    "steps": steps,
                    "failed_step": idx,
                    "error": result.get("error", "loop_over failed"),
                }
            iteration_results: list[dict[str, Any]] = []
            for i, item in enumerate(loop_items):
                iter_context = {**context, "item": item, "loop": {"index": i, "total": len(loop_items)}}
                iter_result = execute_action_by_type(action_type, action_config, iter_context)
                iteration_results.append(iter_result)
                if not iter_result.get("ok"):
                    break
            step_result: dict[str, Any] = {
                "ok": all(r.get("ok") for r in iteration_results),
                "results": iteration_results,
            }
            steps.append(step_result)
            if not step_result["ok"]:
                error_message = "one or more loop iterations failed"
                fallback = _execute_on_error(action, on_error, idx, error_message, context)
                if fallback:
                    step_result["on_error_result"] = fallback
                if continue_on_error and (fallback or fallback is None):
                    continue
                return {
                    "ok": False,
                    "status": "failed",
                    "steps": steps,
                    "failed_step": idx,
                    "error": error_message,
                }
            continue

        result = execute_action_by_type(action_type, action_config, context)
        steps.append(result)
        if not result.get("ok"):
            error_message = result.get("error") or "step failed"
            fallback = _execute_on_error(action, on_error, idx, error_message, context)
            if fallback:
                result["on_error_result"] = fallback
            if continue_on_error and (fallback or fallback is None):
                continue
            return {
                "ok": False,
                "status": "failed",
                "steps": steps,
                "failed_step": idx,
                "error": error_message,
            }

    return {"ok": True, "status": "completed", "steps": steps}


def _execute_on_error(
    action: dict[str, Any],
    on_error: Any,
    step_index: int,
    error_message: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    """Execute a step's on_error fallback action, if provided.

    Returns the fallback result dict, or None if no on_error action is defined.
    The fallback context includes ``error.message`` and ``error.step`` so the
    fallback action can report or route the failure.
    """
    if not on_error or not isinstance(on_error, dict):
        return None
    fallback_type = on_error.get("type") or on_error.get("action_type")
    fallback_config = on_error.get("config") or on_error.get("action_config") or {}
    if not fallback_type:
        return None
    error_context = {
        **context,
        "error": {"message": str(error_message), "step": step_index},
    }
    return execute_action_by_type(fallback_type, fallback_config, error_context)


def _resolve_template_value(path: str, context: dict[str, Any]) -> Any:
    """Resolve a dotted/indexed template path against the automation context.

    Supported paths:
        event.payload.<key>[.<subkey>...]
        event.type, event.user_id, event.workspace_id, event.timestamp
        rule.name, rule.id, rule.workspace_id
        steps.<index>.<key>  (e.g. steps.0.data.summary)
        steps[index].<key>   (e.g. steps[0].data.summary)
    """
    # Normalize bracket syntax: steps[0].data -> steps.0.data
    normalized = path.replace("[", ".").replace("]", "")
    parts = normalized.split(".")
    if not parts or not path:
        return ""

    value = context
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and 0 <= int(part) < len(value):
            value = value[int(part)]
        else:
            return ""
    return value


def _resolve_loop_expression(expression: str, context: dict[str, Any]) -> Any:
    """Resolve a ``loop_over`` expression to its actual value.

    Supports either a dotted path (``event.payload.items``) or a template
    (``{{ event.payload.items }}``). Returns the resolved value, or an empty
    string if the path cannot be resolved.
    """
    stripped = expression.strip()
    match = re.fullmatch(r"{{\s*([\w.\[\]]+)\s*}}", stripped)
    if match:
        path = match.group(1)
    else:
        path = stripped
    return _resolve_template_value(path, context)


def _interpolate(value: Any, *args) -> Any:
    """Recursively interpolate {{ ... }} templates in strings, dicts, and lists.

    Supports two calling conventions for backward compatibility:
        _interpolate(value, context)
        _interpolate(value, event, rule)  # legacy
    """
    if len(args) == 1:
        context = args[0]
    elif len(args) == 2:
        event, rule = args
        context = {"event": event, "rule": rule, "steps": []}
    else:
        raise TypeError("_interpolate() takes 2 or 3 arguments")

    if isinstance(value, str):
        pattern = re.compile(r"{{\s*([\w.\[\]]+)\s*}}")

        def _repl(match: re.Match) -> str:
            path = match.group(1)
            resolved = _resolve_template_value(path, context)
            if resolved is None:
                return ""
            return str(resolved)

        return pattern.sub(_repl, value)
    if isinstance(value, dict):
        return {k: _interpolate(v, *args) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v, *args) for v in value]
    return value


def execute_action_by_type(
    action_type: str | None,
    action_config: dict[str, Any],
    *args,
) -> dict[str, Any]:
    """Execute an action given its type, config, and automation context.

    Supports two calling conventions for backward compatibility:
        execute_action_by_type(action_type, action_config, context)
        execute_action_by_type(action_type, action_config, event, rule)  # legacy
    """
    if len(args) == 1:
        context = args[0]
    elif len(args) == 2:
        event, rule = args
        context = {"event": event, "rule": rule, "steps": []}
    else:
        raise TypeError("execute_action_by_type() takes 3 or 4 arguments")

    event = context.get("event") or {}
    event_payload = event.get("payload") or {}
    interpolated_config = _interpolate(action_config, context)

    if action_type == "webhook":
        return _execute_webhook(interpolated_config, event)
    if action_type == "outbound_webhook":
        return _execute_outbound_webhook(interpolated_config, event)
    if action_type == "swarm":
        return _execute_swarm(interpolated_config, event_payload)
    if action_type == "workflow":
        return _execute_workflow(interpolated_config, event_payload)
    if action_type == "delay":
        return _execute_delay(interpolated_config, event)
    return {"ok": False, "error": f"unsupported action_type {action_type}"}


def _execute_delay(action_config: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Return a sleeping result that tells the scheduler to resume later.

    ``action_config`` must contain a positive ``duration_minutes`` value.
    The result includes an ISO-formatted ``resume_at`` timestamp.
    """
    duration = action_config.get("duration_minutes")
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        return {"ok": False, "error": "delay action requires a numeric duration_minutes"}
    if duration <= 0:
        return {"ok": False, "error": "duration_minutes must be positive"}

    resume_at = datetime.now(timezone.utc) + timedelta(minutes=duration)
    return {
        "ok": True,
        "status": "sleeping",
        "delayed": True,
        "duration_minutes": duration,
        "resume_at": resume_at.isoformat(),
    }


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


def _execute_outbound_webhook(action_config: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Send an outbound HTTP request with a custom method, headers, and body.

    Supports template interpolation in url, headers, and body so automations can
    forward event data to external systems like Zapier, Make, or custom APIs.
    """
    url = action_config.get("url")
    if not url:
        return {"ok": False, "error": "outbound_webhook URL missing"}

    method = str(action_config.get("method", "POST")).upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        return {"ok": False, "error": f"unsupported HTTP method {method}"}

    headers = action_config.get("headers") or {"Content-Type": "application/json"}
    body = action_config.get("body")

    try:
        import requests

        kwargs: dict[str, Any] = {"headers": headers, "timeout": 10}
        if method != "GET" and body is not None:
            if isinstance(body, dict):
                kwargs["json"] = body
            else:
                kwargs["data"] = body

        r = requests.request(method, url, **kwargs)
        r.raise_for_status()
        return {"ok": True, "status_code": r.status_code, "method": method, "url": url}
    except Exception as exc:
        logger.warning("Outbound webhook action failed for %s: %s", url, exc)
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
    *,
    resume_at: str | None = None,
    state: dict[str, Any] | None = None,
) -> None:
    """Log an automation execution with an explicit status string.

    Phase 30: supports persisting ``resume_at`` and ``state`` for sleeping
    executions so the scheduler can resume them later.
    """
    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return

    try:
        import requests

        payload: dict[str, Any] = {
            "rule_id": rule.get("id"),
            "event_type": event.get("type"),
            "event_payload": json.dumps(event.get("payload") or {}),
            "status": status,
            "result": json.dumps(result),
            "workspace_id": rule.get("workspace_id"),
            "user_id": event.get("user_id"),
        }
        if resume_at:
            payload["resume_at"] = resume_at
        if state is not None:
            payload["state"] = json.dumps(state)
        requests.post(
            f"{db_url}/rest/v1/automation_executions",
            headers=headers,
            json=payload,
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
        approval_rule = {
            "id": approval.get("rule_id"),
            "workspace_id": approval.get("workspace_id"),
        }
        approval_context = {"event": event, "rule": approval_rule, "steps": []}
        result = execute_action_by_type(approval.get("action_type"), action_config, approval_context)

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

        # Phase 25: cooldown / throttling
        if _is_in_cooldown(rule):
            _log_execution_with_status(
                rule,
                event,
                "throttled",
                {"reason": "cooldown active"},
            )
            results.append({
                "rule_id": rule.get("id"),
                "rule_name": rule.get("name"),
                "result": {
                    "ok": True,
                    "status": "throttled",
                    "reason": "cooldown active",
                },
            })
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
        _update_last_triggered(rule)
        if result.get("status") == "sleeping":
            _log_execution_with_status(
                rule,
                event,
                "sleeping",
                result,
                resume_at=result.get("resume_at"),
                state={
                    "pending_step_index": result.get("pending_step_index"),
                    "steps": result.get("steps"),
                },
            )
        else:
            _log_execution(rule, event, result)
        results.append({
            "rule_id": rule.get("id"),
            "rule_name": rule.get("name"),
            "result": result,
        })

    return results


def resume_sleeping_executions() -> list[dict[str, Any]]:
    """Find and resume automation executions that are due to wake up.

    Queries ``automation_executions`` for rows with ``status = 'sleeping'`` and
    ``resume_at <= now()``. For each, reconstructs the rule/event context and
    continues execution from the saved step index. Returns a list of resume
    results.
    """
    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return []

    try:
        import requests

        now = datetime.now(timezone.utc).isoformat()
        r = requests.get(
            f"{db_url}/rest/v1/automation_executions",
            headers=headers,
            params={
                "status": "eq.sleeping",
                "resume_at": f"lte.{now}",
                "order": "created_at.asc",
            },
            timeout=10,
        )
        r.raise_for_status()
        executions = r.json() or []
    except Exception as exc:
        logger.warning("Failed to fetch sleeping executions: %s", exc)
        return []

    results: list[dict[str, Any]] = []
    for execution in executions:
        try:
            result = resume_execution(execution)
            results.append(result)
        except Exception as exc:
            logger.warning("Failed to resume execution %s: %s", execution.get("id"), exc)

    return results


def resume_execution(execution: dict[str, Any]) -> dict[str, Any]:
    """Resume a single sleeping execution from where it left off."""
    db_url = _get_db_url()
    headers = _supabase_headers()

    execution_id = execution.get("id")
    state = execution.get("state") or {}
    if isinstance(state, str):
        try:
            state = json.loads(state)
        except Exception:
            state = {}

    pending_step_index = int(state.get("pending_step_index", 0) or 0)
    initial_steps = state.get("steps") or []
    event_payload = execution.get("event_payload")
    if isinstance(event_payload, str):
        try:
            event_payload = json.loads(event_payload)
        except Exception:
            event_payload = {}
    elif event_payload is None:
        event_payload = {}

    event = {
        "type": execution.get("event_type"),
        "payload": event_payload,
        "user_id": execution.get("user_id"),
        "workspace_id": execution.get("workspace_id"),
        "timestamp": None,
    }

    # Fetch the original rule
    rule: dict[str, Any] = {}
    if db_url and headers:
        try:
            import requests
            r = requests.get(
                f"{db_url}/rest/v1/automation_rules?id=eq.{execution.get('rule_id')}",
                headers=headers,
                timeout=10,
            )
            r.raise_for_status()
            rows = r.json() or []
            if rows:
                rule = rows[0]
        except Exception as exc:
            logger.warning("Failed to fetch rule for resumed execution %s: %s", execution_id, exc)

    if not rule:
        return {"ok": False, "error": "rule not found", "execution_id": execution_id}

    # Mark the execution as running to prevent duplicate resumptions
    if db_url and headers:
        try:
            import requests
            requests.patch(
                f"{db_url}/rest/v1/automation_executions?id=eq.{execution_id}",
                headers=headers,
                json={"status": "triggered"},
                timeout=10,
            ).raise_for_status()
        except Exception as exc:
            logger.warning("Failed to mark execution %s as running: %s", execution_id, exc)

    result = _execute_action(rule, event, start_index=pending_step_index, initial_steps=initial_steps)

    # Log the resumed execution result
    status = "completed" if result.get("status") == "completed" else ("sleeping" if result.get("status") == "sleeping" else "failed")
    resume_at = result.get("resume_at")
    new_state = {
        "pending_step_index": result.get("pending_step_index"),
        "steps": result.get("steps"),
    } if result.get("status") == "sleeping" else None
    _log_execution_with_status(rule, event, status, result, resume_at=resume_at, state=new_state)

    return {"ok": True, "execution_id": execution_id, "status": status, "result": result}


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

        # Phase 30: resume any sleeping executions that are due to wake up
        # before triggering new scheduled rules.
        try:
            resume_sleeping_executions()
        except Exception as exc:
            logger.warning("Failed to resume sleeping executions: %s", exc)

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
            if result.get("status") == "sleeping":
                _log_execution_with_status(
                    rule,
                    event,
                    "sleeping",
                    result,
                    resume_at=result.get("resume_at"),
                    state={
                        "pending_step_index": result.get("pending_step_index"),
                        "steps": result.get("steps"),
                    },
                )
            else:
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
