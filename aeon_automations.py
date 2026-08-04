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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from aeon_budgets import check_automation_budget
from aeon_db import add_automation_execution

logger = logging.getLogger("aeon_automations")

# Maximum depth for nested sub-automation calls (Phase 33)
MAX_CALL_DEPTH = 5

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
                if isinstance(actual, str) and isinstance(expected, str) or isinstance(actual, (list, tuple)):
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


def _fetch_rule_by_id(rule_id: str, workspace_id: str | None) -> dict[str, Any] | None:
    """Fetch a single automation rule by ID, scoped to a workspace if provided."""
    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers or not rule_id:
        return None
    try:
        import requests
        query = f"id=eq.{rule_id}"
        if workspace_id:
            query += f"&workspace_id=eq.{workspace_id}"
        r = requests.get(
            f"{db_url}/rest/v1/automation_rules?{query}",
            headers=headers,
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json() or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning("Failed to fetch rule %s: %s", rule_id, exc)
        return None


def _to_number(value: Any) -> float | None:
    """Convert a value to a float for math operations."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _execute_transform(action_config: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Execute a data transformation / formatting action.

    Supported operations:
      - ``math``: basic arithmetic on two operands.
        ``operator``: one of ``+``, ``-``, ``*``, ``/``.
        ``left``, ``right``: numeric values or templates resolving to numbers.
      - ``date_format``: parse an ISO timestamp and reformat it.
        ``input``: ISO timestamp string (supports ``{{ event.payload.x }}``).
        ``output_format``: strftime format (e.g. ``%Y-%m-%d %H:%M``).
        ``input_format``: optional strptime format when input is not ISO.
      - ``regex_extract``: extract a capture group from a string.
        ``pattern``: regex pattern.
        ``input``: string to search.
        ``group``: group index or name (default 0).
      - ``json_parse``: parse a JSON string into an object.
        ``input``: JSON string.
      - ``json_stringify``: serialize an object to a JSON string.
        ``input``: any JSON-serializable value.

    Returns the transformed value under ``result`` for use in subsequent steps
    via ``{{ steps.N.result }}``.
    """
    operation = action_config.get("operation")
    if not operation:
        return {"ok": False, "error": "transform action requires operation"}

    try:
        if operation == "math":
            operator = action_config.get("operator")
            if operator not in {"+", "-", "*", "/"}:
                return {"ok": False, "error": f"unsupported math operator: {operator}"}
            left = _to_number(action_config.get("left"))
            right = _to_number(action_config.get("right"))
            if left is None or right is None:
                return {"ok": False, "error": "math operation requires numeric left and right operands"}
            if operator == "+":
                result = left + right
            elif operator == "-":
                result = left - right
            elif operator == "*":
                result = left * right
            else:  # operator == "/"
                if right == 0:
                    return {"ok": False, "error": "division by zero"}
                result = left / right
            return {"ok": True, "operation": operation, "result": result}

        if operation == "date_format":
            input_value = action_config.get("input")
            if not input_value:
                return {"ok": False, "error": "date_format requires input"}
            input_format = action_config.get("input_format")
            output_format = action_config.get("output_format") or "%Y-%m-%d %H:%M:%S"
            if input_format:
                dt = datetime.strptime(str(input_value), input_format)
            else:
                # Try parsing ISO; handle trailing Z.
                iso = str(input_value).replace("Z", "+00:00")
                dt = datetime.fromisoformat(iso)
            return {"ok": True, "operation": operation, "result": dt.strftime(output_format)}

        if operation == "regex_extract":
            pattern = action_config.get("pattern")
            input_value = action_config.get("input")
            if not pattern or input_value is None:
                return {"ok": False, "error": "regex_extract requires pattern and input"}
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                return {"ok": False, "error": f"invalid regex: {exc}"}
            match = compiled.search(str(input_value))
            if not match:
                return {"ok": False, "error": "pattern did not match input"}
            group = action_config.get("group", 0)
            try:
                value = match.group(group)
            except IndexError:
                return {"ok": False, "error": f"group {group} not present in match"}
            return {"ok": True, "operation": operation, "result": value}

        if operation == "json_parse":
            input_value = action_config.get("input")
            if input_value is None:
                return {"ok": False, "error": "json_parse requires input"}
            return {"ok": True, "operation": operation, "result": json.loads(str(input_value))}

        if operation == "json_stringify":
            input_value = action_config.get("input")
            if input_value is None:
                return {"ok": False, "error": "json_stringify requires input"}
            return {"ok": True, "operation": operation, "result": json.dumps(input_value)}

        return {"ok": False, "error": f"unsupported transform operation: {operation}"}
    except Exception as exc:
        logger.warning("transform action failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def _execute_parallel(
    action_config: dict[str, Any],
    event: dict[str, Any],
    context: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute multiple action branches concurrently (scatter-gather / fan-out).

    ``action_config`` must contain:
        - ``branches``: a list of branch definitions. Each branch may have:
            - ``name``: optional human-readable branch name.
            - ``actions``: a list of action steps to execute in the branch.
    Optional:
        - ``continue_on_error``: if true, the overall step still succeeds even
          when one or more branches fail. Failed branches are listed in
          ``failed_branches``.

    Each branch is executed in its own thread. The aggregated result contains
    a ``branches`` array with each branch's outcome, and a ``failed_branches``
    list of branch names that did not succeed.
    """
    branches = action_config.get("branches") or []
    if not isinstance(branches, list) or not branches:
        return {"ok": False, "error": "parallel action requires a non-empty branches list"}

    continue_on_error = bool(action_config.get("continue_on_error"))
    workspace_id = (context.get("event") or event).get("workspace_id") or context.get("rule", {}).get("workspace_id")
    call_depth = int(context.get("call_depth", 0) or 0)

    def _run_branch(branch: dict[str, Any]) -> dict[str, Any]:
        name = branch.get("name") or f"branch_{branches.index(branch)}"
        branch_actions = branch.get("actions") or []
        if not branch_actions:
            return {"name": name, "ok": False, "error": "branch has no actions"}
        branch_rule = {
            "actions": branch_actions,
            "workspace_id": workspace_id,
        }
        try:
            result = _execute_action(branch_rule, event, call_depth=call_depth, dry_run=dry_run)
        except Exception as exc:
            logger.warning("Parallel branch %s failed: %s", name, exc)
            return {"name": name, "ok": False, "error": str(exc)}
        return {
            "name": name,
            "ok": result.get("ok", False),
            "status": result.get("status"),
            "steps": result.get("steps"),
        }

    try:
        with ThreadPoolExecutor(max_workers=max(1, len(branches))) as executor:
            branch_results = list(executor.map(_run_branch, branches))
    except Exception as exc:
        logger.warning("Failed to execute parallel branches: %s", exc)
        return {"ok": False, "error": str(exc)}

    failed = [r["name"] for r in branch_results if not r.get("ok")]
    if failed and not continue_on_error:
        return {
            "ok": False,
            "error": f"branches failed: {failed}",
            "branches": branch_results,
            "failed_branches": failed,
        }

    return {
        "ok": True,
        "dry_run": dry_run,
        "branches": branch_results,
        "failed_branches": failed,
    }


def _execute_call_rule(
    action_config: dict[str, Any],
    event: dict[str, Any],
    context: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute a sub-automation (rule chaining / composition).

    ``action_config`` must contain:
        - ``rule_id``: the ID of the target automation rule to invoke.
    Optional:
        - ``payload``: a dict/template passed as the sub-rule's event payload.
        - ``event_type``: event type for the synthetic sub-event (default ``sub_request``).
        - ``wait_for_completion``: if true (default), block and return the
          sub-rule's result; otherwise run synchronously but do not block the
          parent chain on the outcome.

    A ``call_depth`` guard prevents runaway recursion (max ``MAX_CALL_DEPTH``).
    """
    rule_id = action_config.get("rule_id")
    if not rule_id:
        return {"ok": False, "error": "call_rule action requires rule_id"}

    parent_event = context.get("event") or event
    workspace_id = parent_event.get("workspace_id") or context.get("rule", {}).get("workspace_id")
    target_rule = _fetch_rule_by_id(str(rule_id), workspace_id)
    if not target_rule:
        return {"ok": False, "error": f"target rule {rule_id} not found"}

    current_depth = int(context.get("call_depth", 0) or 0)
    if current_depth >= MAX_CALL_DEPTH:
        return {"ok": False, "error": f"max sub-automation depth ({MAX_CALL_DEPTH}) exceeded"}

    payload = action_config.get("payload") or {}
    interpolated_payload = _interpolate(payload, context)
    event_type = action_config.get("event_type") or "sub_request"
    sub_event = {
        "type": event_type,
        "payload": interpolated_payload,
        "user_id": parent_event.get("user_id"),
        "workspace_id": workspace_id,
        "timestamp": None,
    }

    wait_for_completion = action_config.get("wait_for_completion", True)
    if not wait_for_completion:
        # Fire-and-forget: run synchronously for simplicity, but the parent
        # chain does not wait on the result.
        _execute_action(target_rule, sub_event, call_depth=current_depth + 1, dry_run=dry_run)
        return {"ok": True, "rule_id": rule_id, "wait_for_completion": False, "dry_run": dry_run}

    sub_result = _execute_action(target_rule, sub_event, call_depth=current_depth + 1, dry_run=dry_run)
    return {
        "ok": sub_result.get("ok", False),
        "rule_id": rule_id,
        "wait_for_completion": True,
        "dry_run": dry_run,
        "sub_result": sub_result,
    }


def _execute_action(
    rule: dict[str, Any],
    event: dict[str, Any],
    *,
    start_index: int = 0,
    initial_steps: list[dict[str, Any]] | None = None,
    call_depth: int = 0,
    dry_run: bool = False,
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
    state = _fetch_workspace_variables(rule.get("workspace_id"))
    context = {"event": event, "rule": rule, "steps": steps, "state": state, "call_depth": call_depth}

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
            result = execute_action_by_type(action_type, action_config, context, dry_run=dry_run)
            steps.append(result)
            if result.get("status") == "sleeping":
                return {
                    "ok": True,
                    "status": "sleeping",
                    "dry_run": dry_run,
                    "steps": steps,
                    "pending_step_index": idx + 1,
                    "resume_at": result.get("resume_at"),
                }
            continue

        # Phase 31: wait_for_event steps suspend the chain until a matching
        # external event arrives (or a timeout expires).
        if action_type == "wait_for_event":
            result = execute_action_by_type(action_type, action_config, context, dry_run=dry_run)
            steps.append(result)
            if result.get("status") == "sleeping":
                return {
                    "ok": True,
                    "status": "sleeping",
                    "dry_run": dry_run,
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
                fallback = _execute_on_error(action, on_error, idx, result["error"], context, dry_run=dry_run)
                if fallback:
                    result["on_error_result"] = fallback
                if continue_on_error and (fallback or fallback is None):
                    continue
                return {
                    "ok": False,
                    "status": "failed",
                    "dry_run": dry_run,
                    "steps": steps,
                    "failed_step": idx,
                    "error": result.get("error", "loop_over failed"),
                }
            iteration_results: list[dict[str, Any]] = []
            for i, item in enumerate(loop_items):
                iter_context = {**context, "item": item, "loop": {"index": i, "total": len(loop_items)}}
                iter_result = execute_action_by_type(action_type, action_config, iter_context, dry_run=dry_run)
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
                fallback = _execute_on_error(action, on_error, idx, error_message, context, dry_run=dry_run)
                if fallback:
                    step_result["on_error_result"] = fallback
                if continue_on_error and (fallback or fallback is None):
                    continue
                return {
                    "ok": False,
                    "status": "failed",
                    "dry_run": dry_run,
                    "steps": steps,
                    "failed_step": idx,
                    "error": error_message,
                }
            continue

        result = execute_action_by_type(action_type, action_config, context, dry_run=dry_run)
        steps.append(result)

        # In dry-run mode, keep the local state dict in sync with simulated
        # variable mutations so later get_variable steps see the updated value.
        if dry_run and action_type in ("set_variable", "increment_variable", "delete_variable") and result.get("ok"):
            key = result.get("key")
            if key is not None:
                if action_type == "delete_variable":
                    context["state"].pop(key, None)
                else:
                    context["state"][key] = result.get("value")

        if not result.get("ok"):
            error_message = result.get("error") or "step failed"
            fallback = _execute_on_error(action, on_error, idx, error_message, context, dry_run=dry_run)
            if fallback:
                result["on_error_result"] = fallback
            if continue_on_error and (fallback or fallback is None):
                continue
            return {
                "ok": False,
                "status": "failed",
                "dry_run": dry_run,
                "steps": steps,
                "failed_step": idx,
                "error": error_message,
            }

    return {"ok": True, "status": "completed", "dry_run": dry_run, "steps": steps}


def _execute_on_error(
    action: dict[str, Any],
    on_error: Any,
    step_index: int,
    error_message: str,
    context: dict[str, Any],
    dry_run: bool = False,
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
    return execute_action_by_type(fallback_type, fallback_config, error_context, dry_run=dry_run)


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
    path = match.group(1) if match else stripped
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


# Actions whose side effects should be simulated when running in dry-run mode.
_SIMULATED_SIDE_EFFECTS = frozenset({
    "webhook",
    "outbound_webhook",
    "swarm",
    "workflow",
    "set_variable",
    "delete_variable",
    "increment_variable",
    "plugin",
})


def _simulate_action(
    action_type: str,
    action_config: dict[str, Any],
    event: dict[str, Any],
) -> dict[str, Any]:
    """Return a simulated result for a side-effect action without executing it.

    Used by dry-run mode so users can preview what a rule would do without
    actually calling external services or mutating workspace state.
    """
    if action_type in ("webhook", "outbound_webhook"):
        url = action_config.get("url")
        if not url:
            return {"ok": False, "error": "webhook URL missing", "dry_run": True}
        method = str(action_config.get("method", "POST")).upper() if action_type == "outbound_webhook" else "POST"
        return {
            "ok": True,
            "dry_run": True,
            "simulated": True,
            "action_type": action_type,
            "method": method,
            "url": url,
            "status_code": 200,
        }
    if action_type in ("swarm", "workflow"):
        return {
            "ok": True,
            "dry_run": True,
            "simulated": True,
            "action_type": action_type,
            "status_code": 200,
            "data": {"simulated": True},
        }
    if action_type == "plugin":
        plugin_id = action_config.get("plugin_id")
        entry = action_config.get("entry")
        if not plugin_id or not entry:
            return {"ok": False, "error": "plugin action requires plugin_id and entry", "dry_run": True}
        return {
            "ok": True,
            "dry_run": True,
            "simulated": True,
            "action_type": "plugin",
            "plugin_id": plugin_id,
            "entry": entry,
        }

    if action_type == "set_variable":
        key = action_config.get("key")
        if not key:
            return {"ok": False, "error": "set_variable requires key", "dry_run": True}
        return {
            "ok": True,
            "dry_run": True,
            "simulated": True,
            "action_type": "set_variable",
            "key": key,
            "value": action_config.get("value"),
        }
    if action_type == "delete_variable":
        key = action_config.get("key")
        if not key:
            return {"ok": False, "error": "delete_variable requires key", "dry_run": True}
        return {
            "ok": True,
            "dry_run": True,
            "simulated": True,
            "action_type": "delete_variable",
            "key": key,
            "deleted": True,
        }
    if action_type == "increment_variable":
        key = action_config.get("key")
        if not key:
            return {"ok": False, "error": "increment_variable requires key", "dry_run": True}
        return {
            "ok": True,
            "dry_run": True,
            "simulated": True,
            "action_type": "increment_variable",
            "key": key,
            "amount": action_config.get("amount", 1),
            "previous_value": 0,
            "value": action_config.get("amount", 1),
        }
    # Fallback for any other side-effect action.
    return {"ok": True, "dry_run": True, "simulated": True, "action_type": action_type}


def _execute_plugin(
    action_config: dict[str, Any],
    event: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke a marketplace plugin entry point as an automation action.

    ``action_config`` must contain:
        - ``plugin_id``: the marketplace plugin to call.
        - ``entry``: the plugin entry point (e.g. ``analyze``, ``score``).
        - ``params``: optional dict of parameters; values may use the
          ``{{ event.payload.xxx }}`` / ``{{ rule.xxx }}`` template syntax.

    Execution is scoped to the rule's ``workspace_id`` and fails closed if
    the plugin is not installed or not enabled in that workspace.
    """
    plugin_id = action_config.get("plugin_id")
    entry = action_config.get("entry")
    if not plugin_id or not entry:
        return {"ok": False, "error": "plugin action requires plugin_id and entry"}

    params = action_config.get("params") or {}
    rule = (context or {}).get("rule") or {}
    workspace_id = str(rule.get("workspace_id") or event.get("workspace_id") or "default")

    try:
        from aeon_marketplace import get_marketplace_manager

        result = get_marketplace_manager().run_entry(workspace_id, str(plugin_id), str(entry), params)
        return {
            **result,
            "plugin_id": plugin_id,
            "entry": entry,
            "workspace_id": workspace_id,
        }
    except Exception as exc:
        return {"ok": False, "error": f"plugin action failed: {exc}"}


def execute_action_by_type(
    action_type: str | None,
    action_config: dict[str, Any],
    *args,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute an action given its type, config, and automation context.

    Supports two calling conventions for backward compatibility:
        execute_action_by_type(action_type, action_config, context)
        execute_action_by_type(action_type, action_config, event, rule)  # legacy

    When ``dry_run`` is true, side-effect actions are simulated instead of
    executed. Non-side-effect actions (``transform``, ``get_variable``,
    ``delay``, ``wait_for_event``) still run normally so the preview remains
    accurate. Sub-automations and parallel branches are executed recursively
    in dry-run mode.
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

    if dry_run and action_type in _SIMULATED_SIDE_EFFECTS:
        return _simulate_action(str(action_type), interpolated_config, event)

    # In dry-run mode, delay and wait_for_event should not suspend execution,
    # otherwise the preview would stop at the first pause. Return a normal
    # simulated result so the rest of the chain can be previewed.
    if dry_run and action_type in ("delay", "wait_for_event"):
        return {"ok": True, "dry_run": True, "simulated": True, "action_type": action_type}

    if action_type == "get_variable":
        key = interpolated_config.get("key")
        if dry_run and key is not None and key in (context.get("state") or {}):
            return {"ok": True, "key": key, "value": context["state"][key]}
        return _execute_get_variable(interpolated_config, event)

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
    if action_type == "wait_for_event":
        return _execute_wait_for_event(interpolated_config, event)
    if action_type == "set_variable":
        return _execute_set_variable(interpolated_config, event)
    if action_type == "delete_variable":
        return _execute_delete_variable(interpolated_config, event)
    if action_type == "increment_variable":
        return _execute_increment_variable(interpolated_config, event)
    if action_type == "call_rule":
        return _execute_call_rule(interpolated_config, event, context, dry_run=dry_run)
    if action_type == "plugin":
        return _execute_plugin(interpolated_config, event, context)
    if action_type == "transform":
        return _execute_transform(interpolated_config, event)
    if action_type == "parallel":
        return _execute_parallel(interpolated_config, event, context, dry_run=dry_run)
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


def _execute_wait_for_event(action_config: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Return a sleeping result that waits for a matching external event.

    ``action_config`` must contain:
        - ``event_type``: the event type to wait for.
        - ``correlation_key``: dotted path in the incoming event payload to match.
        - ``correlation_value``: value (or template) to match against.
        - ``timeout_minutes``: optional timeout; defaults to 1440 (24 hours).

    The result includes the ``waiting_for_event`` type, the expected
    ``correlation_key`` and ``correlation_value``, and a ``resume_at`` timestamp
    derived from the timeout.
    """
    wait_event_type = action_config.get("event_type")
    if not wait_event_type:
        return {"ok": False, "error": "wait_for_event action requires event_type"}

    correlation_key = action_config.get("correlation_key")
    correlation_value = action_config.get("correlation_value")
    if correlation_key is None or correlation_value is None:
        return {"ok": False, "error": "wait_for_event action requires correlation_key and correlation_value"}

    try:
        timeout = float(action_config.get("timeout_minutes") or 1440)
    except (TypeError, ValueError):
        return {"ok": False, "error": "timeout_minutes must be numeric"}
    if timeout <= 0:
        return {"ok": False, "error": "timeout_minutes must be positive"}

    resume_at = datetime.now(timezone.utc) + timedelta(minutes=timeout)
    return {
        "ok": True,
        "status": "sleeping",
        "waiting_for_event": wait_event_type,
        "correlation_key": correlation_key,
        "correlation_value": correlation_value,
        "timeout_minutes": timeout,
        "resume_at": resume_at.isoformat(),
    }


def _fetch_workspace_variables(workspace_id: str | None) -> dict[str, Any]:
    """Load all non-expired automation variables for a workspace into a flat dict."""
    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers or not workspace_id:
        return {}

    try:
        import requests
        r = requests.get(
            f"{db_url}/rest/v1/automation_variables",
            headers=headers,
            params={
                "workspace_id": f"eq.{workspace_id}",
                "or": "(expires_at.is.null,expires_at.gte.now)",
            },
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json() or []
        return {row["key"]: row["value"] for row in rows}
    except Exception as exc:
        logger.warning("Failed to fetch automation variables for workspace %s: %s", workspace_id, exc)
        return {}


def _execute_set_variable(action_config: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Persist a key-value variable for the workspace.

    ``action_config`` must contain:
        - ``key``: variable name.
        - ``value``: any JSON-serializable value.
    Optional:
        - ``ttl_minutes``: time-to-live in minutes. If omitted, the variable
          never expires.
    """
    workspace_id = event.get("workspace_id")
    if not workspace_id:
        return {"ok": False, "error": "set_variable requires workspace_id in event"}

    key = action_config.get("key")
    if not key:
        return {"ok": False, "error": "set_variable requires key"}
    if "value" not in action_config:
        return {"ok": False, "error": "set_variable requires value"}

    value = action_config["value"]
    expires_at = None
    if action_config.get("ttl_minutes"):
        try:
            ttl = float(action_config["ttl_minutes"])
            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=ttl)).isoformat()
        except (TypeError, ValueError):
            return {"ok": False, "error": "ttl_minutes must be numeric"}

    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return {"ok": False, "error": "Supabase not configured"}

    try:
        import requests
        payload: dict[str, Any] = {
            "workspace_id": workspace_id,
            "key": key,
            "value": value,
        }
        if expires_at:
            payload["expires_at"] = expires_at
        requests.post(
            f"{db_url}/rest/v1/automation_variables",
            headers={**headers, "Prefer": "resolution=merge-duplicates,return=representation"},
            json=payload,
            timeout=10,
        ).raise_for_status()
        return {"ok": True, "key": key, "value": value, "expires_at": expires_at}
    except Exception as exc:
        logger.warning("Failed to set automation variable %s: %s", key, exc)
        return {"ok": False, "error": str(exc)}


def _execute_get_variable(action_config: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Return a variable value without modifying storage."""
    workspace_id = event.get("workspace_id")
    key = action_config.get("key")
    if not workspace_id:
        return {"ok": False, "error": "get_variable requires workspace_id in event"}
    if not key:
        return {"ok": False, "error": "get_variable requires key"}

    variables = _fetch_workspace_variables(workspace_id)
    value = variables.get(key)
    if value is None:
        return {"ok": False, "error": f"variable {key} not found"}
    return {"ok": True, "key": key, "value": value}


def _execute_delete_variable(action_config: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Delete a variable from storage."""
    workspace_id = event.get("workspace_id")
    key = action_config.get("key")
    if not workspace_id:
        return {"ok": False, "error": "delete_variable requires workspace_id in event"}
    if not key:
        return {"ok": False, "error": "delete_variable requires key"}

    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return {"ok": False, "error": "Supabase not configured"}

    try:
        import requests
        requests.delete(
            f"{db_url}/rest/v1/automation_variables",
            headers=headers,
            params={"workspace_id": f"eq.{workspace_id}", "key": f"eq.{key}"},
            timeout=10,
        ).raise_for_status()
        return {"ok": True, "key": key, "deleted": True}
    except Exception as exc:
        logger.warning("Failed to delete automation variable %s: %s", key, exc)
        return {"ok": False, "error": str(exc)}


def _execute_increment_variable(action_config: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Atomically increment a numeric variable by a given amount.

    If the variable does not exist, it is created with the increment value.
    """
    workspace_id = event.get("workspace_id")
    key = action_config.get("key")
    if not workspace_id:
        return {"ok": False, "error": "increment_variable requires workspace_id in event"}
    if not key:
        return {"ok": False, "error": "increment_variable requires key"}

    try:
        amount = float(action_config.get("amount", 1))
    except (TypeError, ValueError):
        return {"ok": False, "error": "amount must be numeric"}

    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return {"ok": False, "error": "Supabase not configured"}

    try:
        import requests

        # Upsert-style: merge into existing value or default to 0 then add amount.
        current = _fetch_workspace_variables(workspace_id).get(key, 0)
        try:
            current = float(current)
        except (TypeError, ValueError):
            current = 0
        new_value = current + amount

        requests.post(
            f"{db_url}/rest/v1/automation_variables",
            headers={**headers, "Prefer": "resolution=merge-duplicates,return=representation"},
            json={
                "workspace_id": workspace_id,
                "key": key,
                "value": new_value,
            },
            timeout=10,
        ).raise_for_status()
        return {"ok": True, "key": key, "previous_value": current, "value": new_value, "amount": amount}
    except Exception as exc:
        logger.warning("Failed to increment automation variable %s: %s", key, exc)
        return {"ok": False, "error": str(exc)}


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

    workspace_id = rule.get("workspace_id")
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
                        "value": json.dumps({
                            "approval_id": approval_id,
                            "decision": "approved",
                            "workspace_id": workspace_id,
                        }),
                        "action_id": "approve_request",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                        "style": "danger",
                        "value": json.dumps({
                            "approval_id": approval_id,
                            "decision": "rejected",
                            "workspace_id": workspace_id,
                        }),
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
    workspace_id: str | None = None,
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

    # The authenticated HTTP route historically called this helper without an
    # explicit workspace argument. Recover that trusted request context when
    # available, but never permit a context-free lookup by ID: approval IDs are
    # not tenant boundaries.
    if not workspace_id:
        try:
            from flask import g, has_request_context
            if has_request_context():
                workspace_id = getattr(g, "workspace_id", None)
                if not workspace_id:
                    user_context = getattr(g, "user", {}) or {}
                    workspace_id = user_context.get("workspace_id")
        except (ImportError, RuntimeError):
            workspace_id = None
    if not workspace_id:
        return {"ok": False, "error": "workspace_id is required to resolve an approval"}

    try:
        import requests

        # Fetch the approval request constrained to the caller's workspace so an
        # approval ID cannot cross tenants.
        query = {
            "id": f"eq.{approval_id}",
            "workspace_id": f"eq.{workspace_id}",
        }
        r = requests.get(
            f"{db_url}/rest/v1/approval_requests",
            headers=headers,
            params=query,
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
                f"{db_url}/rest/v1/approval_requests",
                headers=headers,
                params=query,
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
            f"{db_url}/rest/v1/approval_requests",
            headers=headers,
            params=query,
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


def _try_resume_waiting_executions(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Resume any sleeping executions waiting for this event.

    Queries ``automation_executions`` for rows with ``status = 'sleeping'`` whose
    saved state indicates they are waiting for ``event_type``. For each, checks
    whether the incoming event payload matches the saved correlation value at
    the configured correlation key. Matching executions are resumed with the
    waking event attached to the wait step.
    """
    db_url = _get_db_url()
    headers = _supabase_headers()
    if not db_url or not headers:
        return []

    event_type = event.get("type")
    payload = event.get("payload") or {}

    try:
        import requests
        r = requests.get(
            f"{db_url}/rest/v1/automation_executions",
            headers=headers,
            params={
                "status": "eq.sleeping",
                "order": "created_at.asc",
            },
            timeout=10,
        )
        r.raise_for_status()
        executions = r.json() or []
    except Exception as exc:
        logger.warning("Failed to fetch sleeping executions for event resumption: %s", exc)
        return []

    resumed: list[dict[str, Any]] = []
    for execution in executions:
        try:
            state = execution.get("state") or {}
            if isinstance(state, str):
                try:
                    state = json.loads(state)
                except Exception:
                    continue
            wait_step = (state.get("steps") or [])[-1] if state.get("steps") else None
            if not wait_step or wait_step.get("waiting_for_event") != event_type:
                continue
            correlation_key = wait_step.get("correlation_key")
            expected_value = wait_step.get("correlation_value")
            if correlation_key is None or expected_value is None:
                continue
            actual_value = _get_path(payload, correlation_key)
            if actual_value != expected_value:
                continue
            # Mark as running to prevent duplicate resumptions
            requests.patch(
                f"{db_url}/rest/v1/automation_executions?id=eq.{execution.get('id')}",
                headers=headers,
                json={"status": "triggered"},
                timeout=10,
            ).raise_for_status()
            result = resume_execution(execution, waking_event=event)
            resumed.append(result)
        except Exception as exc:
            logger.warning("Failed to resume waiting execution %s: %s", execution.get("id"), exc)

    return resumed



def _dispatch_to_worker(rule_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Enqueue a rule execution via Celery when Redis is configured.

    Falls back to synchronous execution when the worker module is unavailable
    or when running in eager/local mode.
    """
    try:
        # Lazy import avoids a circular dependency: aeon_worker imports aeon_automations.
        from aeon_worker import app as celery_app  # type: ignore[attr-defined]
        from aeon_worker import enqueue_automation  # type: ignore[attr-defined]

        # In eager/local mode run synchronously to avoid scheduling overhead and
        # double execution. Only queue when a real broker is configured.
        if celery_app.conf.task_always_eager:
            return execute_rule_by_id(rule_id, event)

        task_id = enqueue_automation(rule_id, event)
        if task_id:
            return {"ok": True, "dispatched": True, "task_id": task_id, "status": "dispatched"}
    except Exception as exc:
        logger.warning("Failed to dispatch rule %s to Celery: %s", rule_id, exc)

    # Fallback: execute synchronously
    return execute_rule_by_id(rule_id, event)


def execute_rule_by_id(rule_id: str, event_payload: dict[str, Any]) -> dict[str, Any]:
    """Fetch a single automation rule by ID and execute its actions.

    This function is the synchronous entrypoint used by the Celery worker. It
    performs the same cooldown, approval, and budget checks as
    ``evaluate_automations`` before running ``_execute_action``.
    """
    workspace_id = event_payload.get("workspace_id")
    rule = _fetch_rule_by_id(rule_id, workspace_id)
    if not rule:
        return {"ok": False, "error": "rule not found", "rule_id": rule_id}

    event: dict[str, Any] = {
        "type": event_payload.get("type") or "system",
        "payload": event_payload.get("payload") or {},
        "user_id": event_payload.get("user_id"),
        "workspace_id": workspace_id,
        "timestamp": event_payload.get("timestamp"),
    }

    # Phase 25: cooldown / throttling
    if _is_in_cooldown(rule):
        _log_execution_with_status(rule, event, "throttled", {"reason": "cooldown active"})
        return {"ok": True, "status": "throttled", "reason": "cooldown active", "rule_id": rule_id}

    # Phase 42: budget enforcement
    try:
        budget_result = check_automation_budget(str(workspace_id), rule_id=str(rule_id))
        if not budget_result.allowed:
            _log_execution_with_status(rule, event, "throttled", {"reason": budget_result.blocks})
            return {"ok": True, "status": "throttled", "reason": budget_result.blocks, "rule_id": rule_id}
    except Exception as exc:
        logger.warning("Budget check failed for rule %s: %s", rule_id, exc)

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
            return {
                "ok": True,
                "status": "pending_approval",
                "approval_id": approval_id,
                "rule_id": rule_id,
            }

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
    return {"ok": result.get("ok", False), "status": result.get("status"), "result": result, "rule_id": rule_id}


def evaluate_automations(
    event_type: str,
    payload: dict[str, Any],
    user_id: str | None = None,
    workspace_id: str | None = None,
    *,
    use_worker: bool = True,
) -> list[dict[str, Any]]:
    """Evaluate all enabled automation rules for an event and execute matches.

    When ``use_worker`` is true and a Celery broker (Redis) is configured,
    matching rules are dispatched to the worker queue instead of being executed
    inline. This keeps the web process responsive and lets automation execution
    scale horizontally across worker replicas.
    """
    if event_type not in TRIGGER_EVENT_TYPES:
        return []

    event = {
        "type": event_type,
        "payload": payload,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "timestamp": None,
    }

    # Phase 31: before triggering new rules, resume any sleeping executions
    # that are waiting for this event.
    _try_resume_waiting_executions(event)

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

        # Phase 42: enforce automation budgets before execution
        try:
            budget_result = check_automation_budget(str(workspace_id), rule_id=str(rule.get("id")))
            if not budget_result.allowed:
                _log_execution_with_status(rule, event, "throttled", {"reason": budget_result.blocks})
                results.append({
                    "rule_id": rule.get("id"),
                    "rule_name": rule.get("name"),
                    "result": {
                        "ok": True,
                        "status": "throttled",
                        "reason": budget_result.blocks,
                    },
                })
                continue
        except Exception as exc:
            logger.warning("Budget check failed for rule %s: %s", rule.get("id"), exc)

        # Phase 43: dispatch to Celery when configured, otherwise run inline
        if use_worker:
            result = _dispatch_to_worker(str(rule.get("id")), event)
        else:
            result = execute_rule_by_id(str(rule.get("id")), event)
            _update_last_triggered(rule)
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


def resume_execution(execution: dict[str, Any], waking_event: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resume a single sleeping execution from where it left off.

    If ``waking_event`` is provided (e.g. an external event that matched a
    ``wait_for_event`` correlation), the last step in the saved state is
    annotated with the waking event payload so subsequent steps can reference
    it via ``steps.<idx>.waking_event_payload``.
    """
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
    if waking_event and initial_steps:
        # Annotate the last step (the wait_for_event step) with the waking
        # event payload so the remainder of the chain can use it.
        initial_steps[-1]["waking_event_payload"] = waking_event.get("payload")
        initial_steps[-1]["status"] = "completed"
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

        # Phase 42: enforce automation budgets before scheduled execution.
        workspace_id = rule.get("workspace_id")
        rule_id = rule.get("id")
        try:
            budget_result = check_automation_budget(str(workspace_id), rule_id=str(rule_id))
            if not budget_result.allowed:
                logger.warning("Scheduled rule %s blocked by budget in workspace %s", rule_id, workspace_id)
                add_automation_execution(
                    rule_id=str(rule_id),
                    workspace_id=str(workspace_id),
                    status="throttled",
                    result={"reason": budget_result.blocks},
                )
                return
        except Exception as exc:
            logger.warning("Budget check failed for scheduled rule %s: %s", rule_id, exc)

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
            # Phase 43: run scheduled rules on Celery workers when configured.
            result = _dispatch_to_worker(str(rule.get("id")), event)
            dispatched = result.get("dispatched")
            inner = result.get("result") if not dispatched else result
            if dispatched:
                # Celery task result is logged asynchronously by the worker.
                _log_execution_with_status(rule, event, "dispatched", result)
            elif inner and inner.get("status") == "sleeping":
                _log_execution_with_status(
                    rule,
                    event,
                    "sleeping",
                    inner,
                    resume_at=inner.get("resume_at"),
                    state={
                        "pending_step_index": inner.get("pending_step_index"),
                        "steps": inner.get("steps"),
                    },
                )
            else:
                _log_execution_with_status(rule, event, "triggered" if (inner or {}).get("ok") else "failed", inner or result)

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
