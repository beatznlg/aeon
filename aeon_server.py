"""
AEON Kernel Flask API Worker
============================
Exposes the ReflectiveAgent from aeon.py over HTTP so the Next.js frontend
can route chat/tick traffic to a real Python agent instead of the TypeScript
mock bridge.

Env:
  AEON_PYTHON_PORT   Port to listen on (default 5000)
  AEON_PYTHON_HOST   Host to bind (default 0.0.0.0)
  AEON_ROOT          Root state directory (default ./aeon_state/server)
  AEON_LLM_PROVIDER  LLM provider to use (stub, openai, anthropic, ...)

Run locally:
  python aeon_server.py

Next.js routes proxy when AEON_PYTHON_URL is set, e.g.:
  AEON_PYTHON_URL=http://127.0.0.1:5000
"""

import json
import logging
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
import re
from typing import Any

import requests
from flask import Flask, Response, g, jsonify, request

from aeon_cache import get_cache
from aeon_db import (
    add_automation_execution,
    get_workspace_security_config,
    get_workspace_theme_config,
    init_db,
    list_anomalies,
    list_automation_executions,
    list_automation_policies,
    list_backup_policies,
    list_dr_plans,
    list_incidents,
    list_siem_integrations,
    update_workspace_theme_config,
    upsert_workspace_security_config,
)
from aeon_db import (
    get_db as _get_local_db,
)

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, os.environ.get("AEON_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("aeon_server")

import aeon_workflows  # patches AeonOS with workflow/swarm helpers
from aeon import ReflectiveAgent
from aeon_api_keys import ApiKeyManager
from aeon_auth import (
    get_current_user_context,
    require_auth,
    require_role,
    require_workspace_access,
    require_workspace_role,
)
from aeon_automations import _compute_next_run, _execute_action, evaluate_condition, resolve_approval, start_scheduler
from aeon_budgets import (
    check_automation_budget,
)
from aeon_db import (
    create_automation_budget,
    create_automation_policy,
    delete_automation_budget,
    delete_automation_policy,
    get_automation_budget,
    get_automation_policy,
    list_automation_budgets,
    list_automation_policies,
    update_automation_budget,
    update_automation_policy,
)
from aeon_governance import GovernanceManager, get_governance
from aeon_integrations import IntegrationManager, WebhookDelivery, get_integration_catalog
from aeon_llm import get_llm_provider, list_providers, set_active_provider
from aeon_llm import test_provider as _test_llm_provider
from aeon_policies import (
    PolicyEffect,
    evaluate_automation_policy,
)
from aeon_residency import residency_manager
from aeon_scim import (
    require_scim_token,
    scim_create_group,
    scim_create_user,
    scim_get_group,
    scim_get_user,
    scim_list_groups,
    scim_list_users,
    scim_patch_group,
    scim_patch_user,
    scim_replace_group,
    scim_replace_user,
)
from aeon_security import SecurityScanner, sanitize_metadata
from aeon_sso import (
    complete_oidc_login,
    complete_saml_login,
    initiate_oidc_login,
    initiate_saml_login,
    list_sso_providers,
    saml_available,
)
from aeon_sso import (
    create_sso_provider as _create_sso_provider,
)
from aeon_sso import (
    delete_sso_provider as _delete_sso_provider,
)
from aeon_sso import (
    get_sso_provider as _get_sso_provider,
)
from aeon_sso import (
    update_sso_provider as _update_sso_provider,
)

# Supported automation action types (kept in sync with aeon_automations.py)
_AUTOMATION_ACTION_TYPES = frozenset({
    "webhook",
    "outbound_webhook",
    "swarm",
    "workflow",
    "delay",
    "wait_for_event",
    "set_variable",
    "get_variable",
    "delete_variable",
    "increment_variable",
    "call_rule",
    "transform",
    "parallel",
})


def _validate_automation_action(step: dict, path: str) -> tuple[bool, str | None]:
    """Validate a single automation action step. Returns (ok, error_message)."""
    if not isinstance(step, dict):
        return False, f"{path} must be an object"
    step_type = step.get("type") or step.get("action_type")
    if not step_type:
        return False, f"{path} missing type"
    if step_type not in _AUTOMATION_ACTION_TYPES:
        return False, f"{path} type '{step_type}' is not supported"
    run_if = step.get("run_if")
    if run_if is not None and not isinstance(run_if, dict):
        return False, f"{path} run_if must be a condition object or omitted"
    loop_over = step.get("loop_over")
    if loop_over is not None and not isinstance(loop_over, str):
        return False, f"{path} loop_over must be a string path/template or omitted"
    on_error = step.get("on_error")
    if on_error is not None:
        if not isinstance(on_error, dict):
            return False, f"{path} on_error must be an action object or omitted"
        ok, err = _validate_automation_action(on_error, f"{path}.on_error")
        if not ok:
            return False, err
    continue_on_error = step.get("continue_on_error")
    if continue_on_error is not None and not isinstance(continue_on_error, bool):
        return False, f"{path} continue_on_error must be a boolean or omitted"
    return True, None


def _validate_automation_payload(data: dict) -> tuple[bool, str | None]:
    """Validate the core payload for creating or importing automation rules."""
    name = (data.get("name") or "").strip()
    event_type = (data.get("event_type") or "").strip()
    if not name or not event_type:
        return False, "name and event_type are required"

    schedule_type = (data.get("schedule_type") or "event").strip()
    if schedule_type not in {"event", "cron"}:
        return False, "schedule_type must be event or cron"
    cron_expression = (data.get("cron_expression") or "").strip()
    if schedule_type == "cron" and not cron_expression:
        return False, "cron_expression is required for scheduled rules"

    actions = data.get("actions") or []
    action_type = (data.get("action_type") or "").strip()
    if actions:
        for idx, step in enumerate(actions):
            ok, err = _validate_automation_action(step, f"actions[{idx}]")
            if not ok:
                return False, err
    elif action_type:
        ok, err = _validate_automation_action({"type": action_type, "config": data.get("action_config") or {}}, "action")
        if not ok:
            return False, err
    else:
        return False, "Must provide actions array or legacy action_type"

    cooldown_minutes = data.get("cooldown_minutes", 0)
    try:
        cooldown_minutes = int(cooldown_minutes)
        if cooldown_minutes < 0:
            raise ValueError
    except (ValueError, TypeError):
        return False, "cooldown_minutes must be a non-negative integer"

    return True, None


from aeon_notify import log_activity
from aeon_notify import notify as _notify
from aeon_os import AeonOS
from aeon_stripe import get_stripe_client, init_stripe
from aeon_usage import BillingCalculator, HealthCollector, UsageMeter

app = Flask(__name__)

from aeon_anomalies_routes import anomalies_bp
from aeon_dr_routes import dr_bp
from aeon_sectors import sectors_bp
from aeon_siem_routes import siem_bp

app.register_blueprint(anomalies_bp)
app.register_blueprint(dr_bp)
app.register_blueprint(sectors_bp, url_prefix="/sectors")
app.register_blueprint(siem_bp)

# ── Automation metrics (Phase 39) ───────────────────────────────────────────

_SUCCESS_STATUSES = {"triggered", "completed"}


def _metrics_local_fallback_enabled() -> bool:
    """Return True if metrics should fall back to the local DB."""
    return os.environ.get("AEON_METRICS_LOCAL_FALLBACK", "").lower() in ("1", "true", "yes")


def _seed_sample_automation_executions(workspace_id: str) -> None:
    """Seed a few sample automation executions for a preview workspace."""
    sample_rows = [
        {
            "rule_id": "preview-rule-onboarding",
            "workspace_id": str(workspace_id),
            "status": "completed",
            "result": {"runtime_ms": 120},
        },
        {
            "rule_id": "preview-rule-onboarding",
            "workspace_id": str(workspace_id),
            "status": "completed",
            "result": {"runtime_ms": 95},
        },
        {
            "rule_id": "preview-rule-onboarding",
            "workspace_id": str(workspace_id),
            "status": "failed",
            "result": {"runtime_ms": 80},
        },
        {
            "rule_id": "preview-rule-daily-digest",
            "workspace_id": str(workspace_id),
            "status": "completed",
            "result": {"runtime_ms": 200},
        },
        {
            "rule_id": "preview-rule-daily-digest",
            "workspace_id": str(workspace_id),
            "status": "throttled",
            "result": None,
        },
        {
            "rule_id": "preview-rule-approval",
            "workspace_id": str(workspace_id),
            "status": "pending_approval",
            "result": None,
        },
    ]
    for row in sample_rows:
        try:
            add_automation_execution(**row)
        except Exception as exc:
            logger.warning("Failed to seed sample execution: %s", exc)


def _aggregate_automation_metrics(executions: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate raw execution rows into totals, rates, and daily trends."""
    total_runs = len(executions)
    completed_count = 0
    failed_count = 0
    throttled_count = 0
    pending_count = 0
    runtime_sum = 0.0
    runtime_samples = 0
    daily: dict[str, dict[str, int]] = {}

    for execution in executions:
        status = execution.get("status") or "triggered"
        if status == "completed":
            completed_count += 1
        elif status == "failed":
            failed_count += 1
        elif status == "throttled":
            throttled_count += 1
        elif status == "pending_approval":
            pending_count += 1

        result = execution.get("result") or {}
        runtime = result.get("runtime_ms") if isinstance(result, dict) else None
        if runtime is not None:
            try:
                runtime_sum += float(runtime)
                runtime_samples += 1
            except (TypeError, ValueError):
                pass

        created = execution.get("created_at", "") or ""
        day = created[:10] if len(created) >= 10 else "unknown"
        bucket = daily.setdefault(day, {"runs": 0, "completed": 0, "failed": 0})
        bucket["runs"] += 1
        if status in _SUCCESS_STATUSES:
            bucket["completed"] += 1
        elif status == "failed":
            bucket["failed"] += 1

    successful = sum(1 for e in executions if e.get("status") in _SUCCESS_STATUSES)
    success_rate = round((successful / total_runs) * 100, 2) if total_runs else 0.0
    failure_rate = round((failed_count / total_runs) * 100, 2) if total_runs else 0.0

    return {
        "total_runs": total_runs,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "throttled_count": throttled_count,
        "pending_count": pending_count,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "average_runtime_ms": round(runtime_sum / runtime_samples, 2) if runtime_samples else 0.0,
        "daily_counts": [
            {"date": day, **bucket} for day, bucket in sorted(daily.items())
        ],
    }


@app.route("/automations/metrics", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def automation_metrics_workspace():
    """Return aggregated execution metrics for the current workspace."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    days = min(90, max(1, request.args.get("days", 30, type=int)))
    since = (datetime.now(timezone.utc) - timedelta(days=days))

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        if not _metrics_local_fallback_enabled():
            return jsonify({"ok": False, "error": "Supabase not configured"}), 503
        # Use local SQLite fallback for preview/dev environments.
        executions = list_automation_executions(str(workspace_id), since=since)
        source = "local"
    else:
        since_iso = since.isoformat()
        try:
            r = requests.get(
                f"{supabase_url}/rest/v1/automation_executions",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
                params={
                    "workspace_id": f"eq.{workspace_id}",
                    "created_at": f"gte.{since_iso}",
                    "order": "created_at.desc",
                    "limit": 1000,
                },
                timeout=10,
            )
            r.raise_for_status()
            executions = r.json() or []
            source = "supabase"
        except Exception as e:
            logger.warning("Failed to fetch automation metrics from Supabase: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500

    metrics = _aggregate_automation_metrics(executions)

    # Per-rule breakdown
    rule_counts: dict[str, int] = {}
    for execution in executions:
        rid = execution.get("rule_id")
        if rid:
            rule_counts[rid] = rule_counts.get(rid, 0) + 1
    top_rules = sorted(rule_counts.items(), key=lambda item: item[1], reverse=True)[:10]

    return jsonify({
        "ok": True,
        "workspace_id": workspace_id,
        "days": days,
        "source": source,
        **metrics,
        "top_rules": [{"rule_id": rid, "runs": count} for rid, count in top_rules],
    })


@app.route("/automations/<rule_id>/metrics", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def automation_metrics_rule(rule_id: str):
    """Return aggregated execution metrics for a single automation rule."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    days = min(90, max(1, request.args.get("days", 30, type=int)))
    since = (datetime.now(timezone.utc) - timedelta(days=days))

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        if not _metrics_local_fallback_enabled():
            return jsonify({"ok": False, "error": "Supabase not configured"}), 503
        # Use local SQLite fallback for preview/dev environments.
        all_executions = list_automation_executions(str(workspace_id), since=since)
        executions = [e for e in all_executions if e.get("rule_id") == rule_id]
        source = "local"
    else:
        since_iso = since.isoformat()
        try:
            r = requests.get(
                f"{supabase_url}/rest/v1/automation_executions",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
                params={
                    "rule_id": f"eq.{rule_id}",
                    "workspace_id": f"eq.{workspace_id}",
                    "created_at": f"gte.{since_iso}",
                    "order": "created_at.desc",
                    "limit": 1000,
                },
                timeout=10,
            )
            r.raise_for_status()
            executions = r.json() or []
            source = "supabase"
        except Exception as e:
            logger.warning("Failed to fetch automation metrics from Supabase: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500

    metrics = _aggregate_automation_metrics(executions)

    return jsonify({
        "ok": True,
        "rule_id": rule_id,
        "workspace_id": workspace_id,
        "days": days,
        "source": source,
        **metrics,
    })

# Start background scheduler for cron-based automations unless disabled.
if os.environ.get("AEON_DISABLE_SCHEDULER") != "1":
    try:
        start_scheduler(interval_seconds=int(os.environ.get("AEON_SCHEDULER_INTERVAL_SECONDS", "60")))
    except Exception as _sched_exc:
        logger.warning("Could not start scheduled automations: %s", _sched_exc)


# ── Security headers & CORS ─────────────────────────────────────────────────
# Default CSP allows inline scripts/styles only for the Swagger UI served from
# /openapi.json and /docs. Tighten these for production behind a reverse proxy.
_DEFAULT_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://unpkg.com",
    "style-src 'self' 'unsafe-inline' https://unpkg.com",
    "img-src 'self' data: https:",
    "font-src 'self'",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])


def _origin_allowed(origin: str) -> bool:
    """Return True if the origin is allowed to make CORS requests."""
    allowed = os.environ.get("AEON_CORS_ALLOWED_ORIGINS", "*")
    if allowed == "*":
        return True
    return origin.lower() in {o.strip().lower() for o in allowed.split(",")}


@app.after_request
def _security_headers(response):
    """Apply baseline security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    response.headers["Content-Security-Policy"] = _DEFAULT_CSP
    # HSTS only when explicitly enabled; ingress/load-balancer usually terminates TLS
    if os.environ.get("AEON_HSTS", "").lower() in ("1", "true", "yes"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.before_request
def _cors_preflight():
    """Handle CORS preflight and attach CORS headers to all responses."""
    if request.method == "OPTIONS":
        origin = request.headers.get("Origin", "*")
        if _origin_allowed(origin):
            headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, PATCH, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, X-User-Id, X-Workspace-Id, X-User-Email, X-API-Key, X-API-Token",
                "Access-Control-Max-Age": "86400",
            }
            if os.environ.get("AEON_CORS_ALLOW_CREDENTIALS", "").lower() in ("1", "true", "yes"):
                headers["Access-Control-Allow-Credentials"] = "true"
            return ("", 204, headers)
        return ("", 403, {})


@app.after_request
def _cors_headers(response):
    origin = request.headers.get("Origin")
    if origin and _origin_allowed(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        if os.environ.get("AEON_CORS_ALLOW_CREDENTIALS", "").lower() in ("1", "true", "yes"):
            response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# ── Configuration ────────────────────────────────────────────────────────────
HOST = os.environ.get("AEON_PYTHON_HOST", "0.0.0.0")  #nosec B104
PORT = int(os.environ.get("AEON_PYTHON_PORT", "5000"))
AEON_ROOT = Path(os.environ.get("AEON_ROOT", "./aeon_state/server"))
AEON_ROOT.mkdir(parents=True, exist_ok=True)

# Initialize local database tables (SQLite fallback for preview/dev)
init_db()
_get_local_db().ensure_default_workspace()

# Initialize Stripe client at startup
init_stripe(AEON_ROOT)

# Initialize shared cache at startup
get_cache()


# ── Environment validation ───────────────────────────────────────────────────
def validate_environment() -> dict[str, Any]:
    """Check environment variables and return a readiness report."""
    checks = {
        "SUPABASE_URL": "optional",
        "SUPABASE_ANON_KEY": "optional",
        "SUPABASE_SERVICE_ROLE_KEY": "optional",
        "HUGGINGFACE_TOKEN": "optional",  #nosec B105
        "OPENAI_API_KEY": "optional",
        "ANTHROPIC_API_KEY": "optional",
    }
    report: dict[str, Any] = {"ok": True, "missing": [], "warnings": []}
    for name, kind in checks.items():
        if not os.environ.get(name):
            if kind == "required":
                report["ok"] = False
                report["missing"].append(name)
            else:
                report["warnings"].append(f"{name} not set")
    return report


# ── Rate limiter (Redis-backed with in-memory fallback) ─────────────────────
class RateLimiter:
    """Sliding-window rate limiter keyed by client IP or user header.

    Uses Redis when available; otherwise falls back to an in-memory bucket.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._buckets: dict[str, list] = {}

    def is_allowed(self, key: str) -> bool:
        # Degenerate case: a zero-second window means no rate limiting.
        if self.window_seconds <= 0:
            return True
        cache = get_cache()
        # Use a deterministic Redis key per client/window.
        window = int(time.time() // self.window_seconds)
        redis_key = f"aeon:rate:{key}:{window}"
        try:
            if cache._redis is not None:
                current = cache._redis.incr(redis_key)
                if current == 1:
                    cache._redis.expire(redis_key, self.window_seconds)
                return int(current) <= self.max_requests
        except Exception as exc:  # pragma: no cover
            logger.warning("Redis rate-limit failed, falling back to memory: %s", exc)

        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key, [])
            bucket = [t for t in bucket if now - t < self.window_seconds]
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            self._buckets[key] = bucket
            return True

    def key_for_request(self) -> str:
        # Trust X-Forwarded-For only if running behind a known proxy;
        # in Freebuff/Cloud run we accept the first hop.
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "unknown"


_rate_limit_max = int(os.environ.get("AEON_RATE_LIMIT", "60"))
_rate_limit_window = int(os.environ.get("AEON_RATE_LIMIT_WINDOW_SECONDS", "60"))
rate_limiter = RateLimiter(max_requests=_rate_limit_max, window_seconds=_rate_limit_window)


# ── Prometheus/OpenMetrics metrics ──────────────────────────────────────────
class MetricsCollector:
    """Lightweight in-memory metrics collector with Prometheus exposition format."""

    # Standard Prometheus histogram buckets in seconds
    BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, dict[tuple, int]] = {}
        self._histograms: dict[str, dict[tuple, dict[str, Any]]] = {}
        self._gauges: dict[str, float] = {}

    def inc(self, name: str, amount: int = 1, labels: dict[str, str] | None = None):
        label_key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._counters.setdefault(name, {})[label_key] = self._counters.get(name, {}).get(label_key, 0) + amount

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None):
        label_key = tuple(sorted((labels or {}).items()))
        with self._lock:
            hist = self._histograms.setdefault(name, {})
            if label_key not in hist:
                hist[label_key] = {
                    "buckets": dict.fromkeys(self.BUCKETS, 0),
                    "sum": 0.0,
                    "count": 0,
                }
            entry = hist[label_key]
            for bucket in self.BUCKETS:
                if value <= bucket:
                    entry["buckets"][bucket] += 1
            entry["sum"] += value
            entry["count"] += 1

    def set_gauge(self, name: str, value: float):
        with self._lock:
            self._gauges[name] = value

    def _escape_label(self, value: str) -> str:
        return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _format_labels(self, labels: dict[str, str]) -> str:
        return ",".join(f'{k}="{self._escape_label(v)}"' for k, v in sorted(labels.items()))

    def render(self) -> str:
        lines: list = []
        with self._lock:
            # Counters
            for name, labels_values in self._counters.items():
                lines.append(f"# HELP {name} AEON counter")
                lines.append(f"# TYPE {name} counter")
                for label_tuple, value in labels_values.items():
                    labels = dict(label_tuple)
                    lines.append(f"{name}{{{self._format_labels(labels)}}} {value}")

            # Histograms
            for name, label_entries in self._histograms.items():
                lines.append(f"# HELP {name} AEON histogram")
                lines.append(f"# TYPE {name} histogram")
                for label_key, entry in label_entries.items():
                    labels = dict(label_key)
                    for bucket in self.BUCKETS:
                        labels_with_bucket = dict(labels)
                        labels_with_bucket["le"] = str(bucket)
                        lines.append(f"{name}_bucket{{{self._format_labels(labels_with_bucket)}}} {entry['buckets'][bucket]}")
                    lines.append(f"{name}_sum{{{self._format_labels(labels)}}} {entry['sum']}")
                    lines.append(f"{name}_count{{{self._format_labels(labels)}}} {entry['count']}")

            # Gauges
            for name, value in self._gauges.items():
                lines.append(f"# HELP {name} AEON gauge")
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {value}")

        return "\n".join(lines) + "\n"

    def snapshot_summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": {name: {str(k): v for k, v in labels_values.items()} for name, labels_values in self._counters.items()},
                "gauges": dict(self._gauges),
                "histograms": {name: {str(k): v for k, v in entries.items()} for name, entries in self._histograms.items()},
            }


metrics_collector = MetricsCollector()


# ── Request lifecycle hooks ──────────────────────────────────────────────────
@app.before_request
def _before_request():
    g.start_time = time.time()
    # Health/readiness/metrics endpoints are excluded from rate limiting.
    if request.path in ("/health", "/ready", "/metrics"):
        return None
    if not rate_limiter.is_allowed(rate_limiter.key_for_request()):
        logger.warning("Rate limit exceeded for %s", rate_limiter.key_for_request())
        return jsonify({"ok": False, "error": "rate limit exceeded"}), 429
    logger.info("%s %s", request.method, request.path)
    return None


@app.after_request
def _after_request(response):
    start = getattr(g, "start_time", None)
    duration_sec = (time.time() - start) if start else 0
    duration_ms = duration_sec * 1000
    logger.info("%s %s -> %s (%d ms)", request.method, request.path, response.status_code, int(duration_ms))
    response.headers["X-Request-ID"] = f"{time.time():.6f}-{id(request)}"
    # Record Prometheus metrics for every request (except the metrics endpoint itself to avoid loops)
    if request.path != "/metrics":
        metrics_collector.inc("aeon_http_requests_total", labels={
            "method": request.method,
            "path": request.path,
            "status": str(response.status_code),
        })
        metrics_collector.observe("aeon_http_request_duration_seconds", duration_sec, labels={
            "method": request.method,
            "path": request.path,
        })
    return response


@app.errorhandler(Exception)
def _handle_exception(e):
    logger.exception("Unhandled exception: %s", e)
    return jsonify({"ok": False, "error": "internal server error"}), 500

# ── Agent cache (one per app_id) ─────────────────────────────────────────────
_agent_lock = threading.Lock()
_agents: dict[str, ReflectiveAgent] = {}


def get_agent(app_id: str) -> ReflectiveAgent:
    """Return (and lazily create) a ReflectiveAgent for the given app_id."""
    with _agent_lock:
        if app_id not in _agents:
            root = AEON_ROOT / app_id
            root.mkdir(parents=True, exist_ok=True)
            (root / "substrates").mkdir(parents=True, exist_ok=True)
            (root / "skills").mkdir(parents=True, exist_ok=True)
            (root / "goals").mkdir(parents=True, exist_ok=True)
            _agents[app_id] = ReflectiveAgent(root=root)
        return _agents[app_id]


# ── Async job queue (ThreadPoolExecutor-based) ───────────────────────────────
class JobQueue:
    """Background task queue backed by a ThreadPoolExecutor.

    Uses a managed thread pool for concurrent async jobs and keeps an LRU of
    completed results to prevent unbounded memory growth.
    """

    def __init__(self, workers: int | None = None):
        self.workers = workers or int(os.environ.get("AEON_WORKER_THREADS", "5"))
        self._executor = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="aeon_worker")
        self._results: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._pending = 0

    def _run_job(self, job_id: str, app_id: str, action: str, payload: dict[str, Any]) -> None:
        try:
            agent = get_agent(app_id)
            if action == "act":
                result = agent.act(payload.get("query", ""))
            elif action == "reflect":
                result = agent.reflect()
            elif action == "evolve":
                result = agent.evolve(
                    prompt=payload.get("prompt"),
                    source=payload.get("source"),
                    test_cases=payload.get("test_cases"),
                )
            else:
                result = {"error": f"unknown action {action}"}
            with self._lock:
                self._results[job_id] = {
                    "status": "done",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "result": result,
                }
        except Exception as e:
            with self._lock:
                self._results[job_id] = {
                    "status": "error",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(e),
                }

    def submit(self, app_id: str, action: str, payload: dict[str, Any]) -> str:
        job_id = f"{app_id}-{action}-{int(time.time() * 1000)}-{id(payload)}"
        with self._lock:
            self._results[job_id] = {
                "status": "queued",
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
            self._pending += 1
        future = self._executor.submit(self._run_job, job_id, app_id, action, payload)
        future.add_done_callback(lambda _f: self._dec_pending())
        return job_id

    def _dec_pending(self) -> None:
        with self._lock:
            self._pending = max(0, self._pending - 1)

    def status(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._results.get(job_id)

    def shutdown(self):
        self._executor.shutdown(wait=True)


job_queue = JobQueue(workers=2)


# ── Flask routes ───────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "backend": "aeon_python_kernel"})


@app.route("/live", methods=["GET"])
def live():
    """Liveness probe: returns 200 as long as the server process is responsive."""
    return jsonify({"ok": True, "status": "alive"}), 200


@app.route("/dashboard/stats", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def dashboard_stats():
    """Return aggregate counts for the current workspace dashboard."""
    workspace_id = g.user.get("workspace_id")
    if not workspace_id:
        return jsonify({"ok": False, "error": "workspace not selected"}), 400

    anomalies = list_anomalies(str(workspace_id))
    incidents = list_incidents(str(workspace_id))
    open_incidents = list_incidents(str(workspace_id), status="open")
    automations = list_automation_policies(str(workspace_id))
    backup_policies = list_backup_policies(str(workspace_id))
    dr_plans = list_dr_plans(str(workspace_id))
    siem = list_siem_integrations(str(workspace_id))

    since = datetime.now(timezone.utc) - timedelta(days=30)
    executions = list_automation_executions(str(workspace_id), since=since)

    return jsonify({
        "ok": True,
        "workspace_id": str(workspace_id),
        "counts": {
            "anomalies": len(anomalies),
            "incidents": len(incidents),
            "open_incidents": len(open_incidents),
            "automations": len(automations),
            "backup_policies": len(backup_policies),
            "dr_plans": len(dr_plans),
            "siem_integrations": len(siem),
            "automation_executions_30d": len(executions),
        },
    })


def _operations_agent_snapshot(agent: Any, app_id: str) -> dict[str, Any]:
    """Return non-sensitive runtime counts for one agent instance."""
    try:
        vitals = agent.self_model.vitals()
        if not isinstance(vitals, dict):
            vitals = {}
    except Exception:
        vitals = {}

    memory = getattr(agent, "memory", None)
    episodic = getattr(memory, "episodic", None)
    semantic = getattr(memory, "semantic", None)
    procedural = getattr(memory, "procedural", None)
    skill_meta = getattr(memory, "skill_meta", None)

    try:
        open_goals = agent.goals.open_goals()
        if not isinstance(open_goals, list):
            open_goals = list(open_goals or [])
    except Exception:
        open_goals = []
    goals = getattr(agent, "goals", None)
    all_goals = getattr(goals, "goals", None)

    return {
        "app_id": app_id,
        "ticks": int(getattr(agent, "tick_count", 0) or 0),
        "vitals": vitals,
        "memory": {
            "episodic_events": len(episodic) if episodic is not None else 0,
            "semantic_nodes": len(getattr(semantic, "nodes", {}) or {}) if semantic else 0,
            "semantic_edges": len(getattr(semantic, "edges", []) or []) if semantic else 0,
            "procedural_skills": len(skill_meta or {}) if skill_meta is not None else len(getattr(procedural, "names", {}) or {}) if procedural else 0,
        },
        "goals": {
            "open": len(open_goals),
            "total": len(all_goals) if all_goals is not None else len(open_goals),
        },
    }


def _operations_worker_snapshot() -> dict[str, Any]:
    """Return queue capacity and status counts without exposing job payloads."""
    with job_queue._lock:
        statuses: dict[str, int] = {}
        for result in job_queue._results.values():
            status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
            statuses[status] = statuses.get(status, 0) + 1
        return {
            "pending": int(job_queue._pending),
            "workers": int(job_queue.workers),
            "tracked_jobs": len(job_queue._results),
            "status_counts": statuses,
        }


@app.route("/operations/snapshot", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def operations_snapshot():
    """Return a tenant-scoped, count-only operations snapshot for the dashboard."""
    workspace_id = str(getattr(g, "workspace_id", None) or g.user.get("workspace_id") or "")
    if not workspace_id:
        return jsonify({"ok": False, "error": "workspace not selected"}), 400

    app_id = request.args.get("app_id") or f"ws-{workspace_id}"
    expected_app_id = f"ws-{workspace_id}"
    if app_id != expected_app_id:
        return jsonify({"ok": False, "error": "app_id must match the workspace agent"}), 403

    agent = get_agent(app_id)
    agent_snapshot = _operations_agent_snapshot(agent, app_id)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    policies = list_automation_policies(workspace_id, enabled_only=False)
    budgets = list_automation_budgets(workspace_id, enabled_only=False)
    executions = list_automation_executions(workspace_id, since=since)
    execution_statuses: dict[str, int] = {}
    for execution in executions:
        status = execution.get("status") or "unknown"
        execution_statuses[status] = execution_statuses.get(status, 0) + 1

    readiness = validate_environment()
    return jsonify({
        "ok": True,
        "workspace_id": workspace_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "backend": "aeon_python_kernel",
            "ready": bool(readiness.get("ok")),
            "environment": readiness,
        },
        "agent": {
            "app_id": agent_snapshot["app_id"],
            "ticks": agent_snapshot["ticks"],
            "vitals": agent_snapshot["vitals"],
        },
        "memory": agent_snapshot["memory"],
        "goals": agent_snapshot["goals"],
        "worker": _operations_worker_snapshot(),
        "automations": {
            "policies": {
                "total": len(policies),
                "enabled": sum(1 for policy in policies if bool(getattr(policy, "enabled", False))),
            },
            "budgets": {
                "total": len(budgets),
                "enabled": sum(1 for budget in budgets if bool(getattr(budget, "enabled", False))),
            },
            "executions_last_24h": len(executions),
            "execution_statuses": execution_statuses,
        },
    })


# Initialize Stripe at startup
init_stripe(AEON_ROOT)


# ── Auth routes ────────────────────────────────────────────────────────────
@app.route("/auth/login", methods=["POST"])
def auth_login():
    """Issue a short-lived JWT access token for a valid user."""
    from werkzeug.security import check_password_hash

    from aeon_auth import _FallbackAdmin, create_access_token
    from aeon_db import get_db

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"ok": False, "error": "email and password required"}), 400

    # Fallback admin (dev/bootstrap)
    if _FallbackAdmin.matches(email, password):
        token = create_access_token(_FallbackAdmin.id, _FallbackAdmin.email, _FallbackAdmin.role, _FallbackAdmin.workspace_id)
        return jsonify({"ok": True, "token": token, "user": {"id": _FallbackAdmin.id, "email": _FallbackAdmin.email, "role": _FallbackAdmin.role}})

    db = get_db()
    user = db.get_user_by_email(email)
    if not user or not check_password_hash(user.password, password):
        return jsonify({"ok": False, "error": "invalid credentials"}), 401

    # Pick the first workspace membership as the default workspace context.
    workspace_id = None
    try:
        memberships = db.list_user_memberships(user.id)
        if memberships:
            workspace_id = memberships[0].workspace_id
    except Exception:  #nosec B110
        pass
    token = create_access_token(user.id, user.email, user.role, workspace_id)
    return jsonify({
        "ok": True,
        "token": token,
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role, "workspace_id": workspace_id},
    })


@app.route("/auth/me", methods=["GET"])
@require_auth
def auth_me():
    """Return the current authenticated user's profile and default workspace."""
    from aeon_db import get_db

    ctx = g.user
    user_id = ctx.get("user_id")
    db = get_db()
    user = db.get_user_by_id(user_id)
    if not user:
        return jsonify({"ok": False, "error": "user not found"}), 404

    workspace = None
    try:
        memberships = db.list_user_memberships(str(user.id))
        if memberships:
            ws = db.get_workspace(str(memberships[0].workspace_id))
            if ws:
                workspace = {
                    "id": str(ws.id),
                    "slug": ws.slug,
                    "name": ws.name,
                    "plan": ws.plan,
                }
    except Exception:  #nosec B110
        pass

    return jsonify({
        "ok": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "workspace": workspace,
        },
    })


@app.route("/auth/register", methods=["POST"])
def auth_register():
    """Register a new user account (self-service).
    Creates the user, a default workspace, and a membership.
    Returns a JWT so the user can immediately start chatting.
    """
    from werkzeug.security import generate_password_hash

    from aeon_auth import create_access_token
    from aeon_db import Membership, User, Workspace, get_db

    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")
    name = (data.get("name") or "").strip() or email.split("@")[0]

    if not email or not password:
        return jsonify({"ok": False, "error": "email and password required"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "error": "password must be at least 6 characters"}), 400

    db = get_db()
    existing = db.get_user_by_email(email)
    if existing:
        return jsonify({"ok": False, "error": "email already registered"}), 409

    try:
        user = User(
            email=email,
            name=name,
            password=generate_password_hash(password),
            role="VIEWER",
        )
        with db.session() as s:
            s.add(user)
            s.flush()

            # Create a personal workspace for the new user
            slug = f"ws-{user.id[:8]}"
            workspace = Workspace(
                slug=slug,
                name=f"{name}'s Workspace",
                plan="free",
            )
            s.add(workspace)
            s.flush()

            # Add user as ADMIN of their workspace
            membership = Membership(
                workspace_id=workspace.id,
                user_id=user.id,
                role="ADMIN",
            )
            s.add(membership)
            s.commit()

            workspace_id = str(workspace.id)

        # Seed sample automation metrics for preview/dev environments so the
        # dashboard has real data to display without a live Supabase instance.
        if _metrics_local_fallback_enabled():
            try:
                _seed_sample_automation_executions(workspace_id)
            except Exception as exc:
                logger.warning("Failed to seed preview metrics: %s", exc)

        token = create_access_token(user.id, user.email, user.role, workspace_id)
        logger.info("New user registered: %s (workspace: %s)", email, slug        )
        # Welcome notification
        _notify(
            user_id=str(user.id),
            type="welcome",
            title=f"Welcome to AEON, {name}!",
            body="Your workspace has been created. Start chatting or explore the OS Launcher to get started.",
            icon="👋",
            link="/os",
            workspace_id=workspace_id,
        )
        return jsonify({
            "ok": True,
            "token": token,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "workspace_id": workspace_id,
            },
        }), 201
    except Exception as e:
        logger.exception("Registration failed: %s", e)
        return jsonify({"ok": False, "error": f"registration failed: {e}"}), 500


@app.route("/auth/jwt/status", methods=["GET"])
@require_auth
@require_role("ADMIN")
def auth_jwt_status():
    """Return non-sensitive JWT signing configuration status."""
    from aeon_auth import jwt_status
    return jsonify({"ok": True, **jwt_status()})


@app.route("/auth/jwt/rotate", methods=["POST"])
@require_auth
@require_role("ADMIN")
def auth_jwt_rotate():
    """Rotate the primary JWT signing secret. Accepts an optional explicit secret."""
    from aeon_auth import rotate_jwt_secret
    data = request.json or {}
    new_secret = data.get("secret")
    result = rotate_jwt_secret(new_secret)
    return jsonify({"ok": True, "rotation": result})


# ── Enterprise SSO (Phase 44) ───────────────────────────────────────────────
@app.route("/sso/providers", methods=["GET", "POST"])
@require_auth
@require_workspace_role("ADMIN")
def sso_providers_index():
    """List or create SSO providers for the current workspace."""
    ctx = g.user
    workspace_id = ctx.get("workspace_id")

    if request.method == "GET":
        providers = list_sso_providers(workspace_id)
        return jsonify({
            "ok": True,
            "providers": [
                {
                    "id": str(p.id),
                    "workspace_id": str(p.workspace_id),
                    "protocol": p.protocol,
                    "name": p.name,
                    "active": p.active,
                    "config": p.config,
                    "attribute_mapping": p.attribute_mapping,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in providers
            ],
        })

    data = request.json or {}
    protocol = (data.get("protocol") or "").lower()
    name = (data.get("name") or "").strip()
    config = data.get("config") or {}
    attribute_mapping = data.get("attribute_mapping") or {}
    if protocol not in ("saml", "oidc"):
        return jsonify({"ok": False, "error": "protocol must be saml or oidc"}), 400
    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400

    provider = _create_sso_provider(
        workspace_id=workspace_id,
        protocol=protocol,
        name=name,
        config=config,
        attribute_mapping=attribute_mapping,
    )
    return jsonify({
        "ok": True,
        "provider": {
            "id": str(provider.id),
            "workspace_id": str(provider.workspace_id),
            "protocol": provider.protocol,
            "name": provider.name,
            "active": provider.active,
        },
    }), 201


@app.route("/sso/providers/<provider_id>", methods=["GET", "PATCH", "DELETE"])
@require_auth
@require_workspace_role("ADMIN")
def sso_provider_detail(provider_id: str):
    """Get, update, or delete an SSO provider."""
    provider = _get_sso_provider(provider_id)
    if not provider:
        return jsonify({"ok": False, "error": "provider not found"}), 404

    if request.method == "GET":
        return jsonify({
            "ok": True,
            "provider": {
                "id": str(provider.id),
                "workspace_id": str(provider.workspace_id),
                "protocol": provider.protocol,
                "name": provider.name,
                "active": provider.active,
                "config": provider.config,
                "attribute_mapping": provider.attribute_mapping,
            },
        })

    if request.method == "DELETE":
        _delete_sso_provider(provider_id)
        return jsonify({"ok": True})

    data = request.json or {}
    provider = _update_sso_provider(
        provider,
        name=data.get("name"),
        config=data.get("config"),
        attribute_mapping=data.get("attribute_mapping"),
        active=data.get("active"),
    )
    return jsonify({
        "ok": True,
        "provider": {
            "id": str(provider.id),
            "name": provider.name,
            "active": provider.active,
        },
    })


@app.route("/sso/oidc/login/<provider_id>", methods=["GET"])
def sso_oidc_login(provider_id: str):
    """Initiate an OIDC login by redirecting to the identity provider."""
    provider = _get_sso_provider(provider_id)
    if not provider or provider.protocol != "oidc":
        return jsonify({"ok": False, "error": "OIDC provider not found"}), 404

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    cache = get_cache()
    cache.set(f"oidc:state:{state}", {"provider_id": str(provider.id), "nonce": nonce}, ttl=600)
    redirect_url = initiate_oidc_login(provider, state, nonce)
    return jsonify({"ok": True, "redirect_url": redirect_url})


@app.route("/sso/oidc/callback/<provider_id>", methods=["GET"])
def sso_oidc_callback(provider_id: str):
    """Handle the OIDC callback, provision the user, and issue an AEON token."""
    state = request.args.get("state")
    code = request.args.get("code")
    if not state or not code:
        return jsonify({"ok": False, "error": "missing state or code"}), 400

    cache = get_cache()
    stored = cache.get(f"oidc:state:{state}")
    if not stored or stored.get("provider_id") != provider_id:
        return jsonify({"ok": False, "error": "invalid or expired state"}), 400
    cache.delete(f"oidc:state:{state}")

    provider = _get_sso_provider(provider_id)
    if not provider or provider.protocol != "oidc":
        return jsonify({"ok": False, "error": "OIDC provider not found"}), 404

    try:
        result = complete_oidc_login(provider, code, state, stored.get("nonce"))
    except Exception as e:  # noqa: BLE001
        logger.warning("OIDC callback failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify(result)


@app.route("/sso/saml/login/<provider_id>", methods=["GET"])
def sso_saml_login(provider_id: str):
    """Initiate a SAML 2.0 login by redirecting to the identity provider."""
    if not saml_available():
        return jsonify({"ok": False, "error": "SAML support is not installed"}), 501
    provider = _get_sso_provider(provider_id)
    if not provider or provider.protocol != "saml":
        return jsonify({"ok": False, "error": "SAML provider not found"}), 404
    try:
        redirect_url = initiate_saml_login(provider)
    except Exception as e:  # noqa: BLE001
        logger.warning("SAML login initiation failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "redirect_url": redirect_url})


@app.route("/sso/saml/acs/<provider_id>", methods=["POST"])
def sso_saml_acs(provider_id: str):
    """SAML Assertion Consumer Service endpoint."""
    if not saml_available():
        return jsonify({"ok": False, "error": "SAML support is not installed"}), 501
    provider = _get_sso_provider(provider_id)
    if not provider or provider.protocol != "saml":
        return jsonify({"ok": False, "error": "SAML provider not found"}), 404
    try:
        result = complete_saml_login(provider, request.form.to_dict(flat=True))
    except Exception as e:  # noqa: BLE001
        logger.warning("SAML ACS failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify(result)


# ── SCIM 2.0 Provisioning (Phase 44) ─────────────────────────────────────────
@app.route("/scim/v2/Users", methods=["GET", "POST"])
@require_scim_token
def scim_users_index():
    workspace_id = g.scim_workspace_id
    if request.method == "GET":
        filter_expr = request.args.get("filter")
        return scim_list_users(workspace_id, filter_expr)
    return scim_create_user(workspace_id, request.json or {})


@app.route("/scim/v2/Users/<user_id>", methods=["GET", "PUT", "PATCH"])
@require_scim_token
def scim_user_detail(user_id: str):
    workspace_id = g.scim_workspace_id
    if request.method == "GET":
        return scim_get_user(workspace_id, user_id)
    if request.method == "PUT":
        return scim_replace_user(workspace_id, user_id, request.json or {})
    return scim_patch_user(workspace_id, user_id, request.json or {})


@app.route("/scim/v2/Groups", methods=["GET", "POST"])
@require_scim_token
def scim_groups_index():
    workspace_id = g.scim_workspace_id
    if request.method == "GET":
        return scim_list_groups(workspace_id)
    return scim_create_group(workspace_id, request.json or {})


@app.route("/scim/v2/Groups/<group_id>", methods=["GET", "PUT", "PATCH"])
@require_scim_token
def scim_group_detail(group_id: str):
    workspace_id = g.scim_workspace_id
    if request.method == "GET":
        return scim_get_group(workspace_id, group_id)
    if request.method == "PUT":
        return scim_replace_group(workspace_id, group_id, request.json or {})
    return scim_patch_group(workspace_id, group_id, request.json or {})


# ── Security, Compliance & Data Residency (Phase 45) ─────────────────────────
@app.route("/workspaces/<workspace_id>/security/config", methods=["GET", "PUT"])
@require_auth
@require_workspace_role("ADMIN")
def workspace_security_config(workspace_id: str):
    """Get or update the security/residency configuration for a workspace."""
    if request.method == "GET":
        cfg = get_workspace_security_config(workspace_id)
        if cfg is None:
            return jsonify({
                "ok": True,
                "workspace_id": workspace_id,
                "pii_redaction_enabled": True,
                "phi_redaction_enabled": False,
                "data_region": "global",
                "kms_key_id": None,
            })
        return jsonify({
            "ok": True,
            "workspace_id": workspace_id,
            "pii_redaction_enabled": cfg.pii_redaction_enabled,
            "phi_redaction_enabled": cfg.phi_redaction_enabled,
            "data_region": cfg.data_region,
            "kms_key_id": cfg.kms_key_id,
        })

    data = request.json or {}
    try:
        cfg = upsert_workspace_security_config(
            workspace_id,
            pii_redaction_enabled=data.get("pii_redaction_enabled"),
            phi_redaction_enabled=data.get("phi_redaction_enabled"),
            data_region=data.get("data_region"),
            kms_key_id=data.get("kms_key_id"),
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({
        "ok": True,
        "workspace_id": workspace_id,
        "pii_redaction_enabled": cfg.pii_redaction_enabled,
        "phi_redaction_enabled": cfg.phi_redaction_enabled,
        "data_region": cfg.data_region,
        "kms_key_id": cfg.kms_key_id,
    })


@app.route("/workspaces/<workspace_id>/security/scan", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def workspace_security_scan(workspace_id: str):
    """Scan arbitrary text for PII/PHI based on the workspace security config."""
    data = request.json or {}
    text = data.get("text", "")
    cfg = get_workspace_security_config(workspace_id)
    scanner = SecurityScanner(
        pii_enabled=cfg.pii_redaction_enabled if cfg else True,
        phi_enabled=cfg.phi_redaction_enabled if cfg else False,
    )
    redacted, findings = scanner.scan_and_redact(text)

    if findings:
        try:
            from aeon_siem import forward_dlp_event
            forward_dlp_event(
                workspace_id,
                None,
                {
                    "findings_count": len(findings),
                    "categories": list({f.get("category") for f in findings}),
                    "types": list({f.get("type") for f in findings}),
                    "scan_trigger": "security_scan",
                },
            )
        except Exception:
            pass

    return jsonify({
        "ok": True,
        "workspace_id": workspace_id,
        "redacted_text": redacted,
        "findings": findings,
    })


@app.route("/workspaces/<workspace_id>/residency/check", methods=["GET"])
@require_auth
@require_workspace_role("ADMIN")
def workspace_residency_check(workspace_id: str):
    """Check whether the current runtime region satisfies the workspace policy."""
    cfg = get_workspace_security_config(workspace_id)
    required_region = cfg.data_region if cfg else "global"
    try:
        residency_manager.enforce_region(required_region)
    except PermissionError as exc:
        return jsonify({
            "ok": False,
            "workspace_id": workspace_id,
            "current_region": residency_manager.current_region,
            "required_region": required_region,
            "error": str(exc),
        }), 403
    return jsonify({
        "ok": True,
        "workspace_id": workspace_id,
        "current_region": residency_manager.current_region,
        "required_region": required_region,
    })


@app.route("/workspaces/<workspace_id>/security/encrypt", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def workspace_security_encrypt(workspace_id: str):
    """Encrypt a payload using the workspace's configured KMS key (BYOK)."""
    data = request.json or {}
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "payload must be an object"}), 400
    cfg = get_workspace_security_config(workspace_id)
    try:
        encrypted, envelope = residency_manager.encrypt_envelope(payload, kms_key_id=cfg.kms_key_id if cfg else None)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({
        "ok": True,
        "workspace_id": workspace_id,
        "encrypted_data": encrypted,
        "envelope": envelope,
    })


@app.route("/workspaces/<workspace_id>/security/decrypt", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def workspace_security_decrypt(workspace_id: str):
    """Decrypt a payload previously encrypted via /security/encrypt."""
    data = request.json or {}
    encrypted_data = data.get("encrypted_data")
    envelope = data.get("envelope")
    if not isinstance(encrypted_data, str) or not isinstance(envelope, dict):
        return jsonify({"ok": False, "error": "encrypted_data and envelope are required"}), 400
    try:
        decrypted = residency_manager.decrypt_envelope(encrypted_data, envelope)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({
        "ok": True,
        "workspace_id": workspace_id,
        "payload": decrypted,
    })


@app.route("/workspaces", methods=["GET"])
@require_auth
def workspaces_list():
    """List workspaces the authenticated user belongs to."""
    from aeon_db import get_db
    ctx = g.user
    user_id = ctx.get("user_id")
    db = get_db()
    memberships = db.list_user_memberships(user_id)
    workspaces = []
    for m in memberships:
        ws = db.get_workspace(str(m.workspace_id))
        if ws:
            workspaces.append({
                "id": str(ws.id),
                "slug": ws.slug,
                "name": ws.name,
                "plan": ws.plan,
                "role": m.role,
            })
    return jsonify({"ok": True, "workspaces": workspaces})


@app.route("/workspaces/<workspace_id>/chat", methods=["POST"])
@require_auth
def workspace_chat(workspace_id: str):
    """Workspace-scoped chat with isolated agent state per workspace."""
    from aeon_db import get_db
    data = request.json or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "missing query"}), 400
    ctx = _governance_context()

    # Verify workspace access
    user_id = ctx.get("user_id")
    db = get_db()
    membership = db.get_membership(workspace_id, user_id)
    if not membership:
        return jsonify({"ok": False, "error": "workspace access denied"}), 403

    try:
        # Per-request provider override
        provider_override = data.get("provider")
        if provider_override:
            import aeon as _aeon
            _aeon.QW = get_llm_provider(str(provider_override))
            os.environ["AEON_LLM_PROVIDER"] = str(provider_override)

        # Use workspace_id as the agent key for isolated state
        agent = get_agent(f"ws-{workspace_id}")
        result = agent.act(query)
        metrics_collector.inc("aeon_chat_requests_total")
        metrics_collector.inc("aeon_agent_ticks_total", labels={"app_id": f"ws-{workspace_id}"})

        get_governance_manager().log_audit(
            action="WORKSPACE_CHAT",
            module="workspace",
            user_id=user_id,
            workspace_id=workspace_id,
            email=ctx.get("email"),
            metadata=_secure_metadata({"backend": result.get("backend", "unknown"), "provider_override": provider_override}, ctx.get("workspace_id")),
        )
        return jsonify({"ok": True, "data": result, "backend": result.get("backend", "unknown")})
    except Exception as e:
        get_governance_manager().log_audit(
            action="WORKSPACE_CHAT_ERROR",
            module="workspace",
            user_id=user_id,
            workspace_id=workspace_id,
            email=ctx.get("email"),
            metadata=_secure_metadata({"error": str(e)}, ctx.get("workspace_id")),
        )
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/workspaces/<workspace_id>/history", methods=["GET"])
@require_auth
def workspace_history(workspace_id: str):
    """Return conversation history for a workspace.
    Tries Supabase `episodes` table first, falls back to local agent memory.
    """
    from aeon_db import get_db
    ctx = g.user
    user_id = ctx.get("user_id")
    db = get_db()
    membership = db.get_membership(workspace_id, user_id)
    if not membership:
        return jsonify({"ok": False, "error": "workspace access denied"}), 403

    limit = min(100, max(1, request.args.get("limit", 50, type=int)))

    # Try Supabase episodes table first
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if supabase_url and supabase_key:
            import requests
            r = requests.get(
                f"{supabase_url}/rest/v1/episodes",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                },
                params={
                    "ref": f"eq.ws-{workspace_id}",
                    "order": "id.desc",
                    "limit": limit,
                },
                timeout=10,
            )
            if r.ok:
                episodes = r.json()
                episodes.reverse()
                return jsonify({"ok": True, "history": episodes, "source": "supabase"})
    except Exception:  #nosec B110
        pass

    # Fall back to local agent memory
    try:
        agent = get_agent(f"ws-{workspace_id}")
        context = agent.memory.recent_context(limit)
        return jsonify({"ok": True, "history": context, "source": "local"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Per-tenant Branding & Theme (Phase 48+) ─────────────────────────────────


def _validate_branding_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and sanitize a workspace branding payload.

    Returns a dict containing only the allowed keys, with safe defaults where
    applicable. Raises ValueError on invalid input.
    """
    allowed: dict[str, Any] = {}

    if "companyName" in data:
        allowed["companyName"] = str(data["companyName"])[:120]
    if "productName" in data:
        allowed["productName"] = str(data["productName"])[:120]
    if "tagline" in data:
        allowed["tagline"] = str(data["tagline"])[:240]

    if "primaryColor" in data:
        color = str(data["primaryColor"]).strip()
        if not re.fullmatch(r"^#[0-9A-Fa-f]{6}$", color):
            raise ValueError("primaryColor must be a 6-digit hex color (e.g. #6366f1)")
        allowed["primaryColor"] = color.lower()

    if "logoUrl" in data:
        logo = str(data["logoUrl"]).strip()
        if logo and not re.match(r"^https?://", logo):
            raise ValueError("logoUrl must be an http or https URL")
        allowed["logoUrl"] = logo

    if "defaultMode" in data:
        mode = str(data["defaultMode"]).lower()
        if mode not in {"light", "dark"}:
            raise ValueError("defaultMode must be 'light' or 'dark'")
        allowed["defaultMode"] = mode

    if "modules" in data:
        raw_modules = data["modules"]
        if not isinstance(raw_modules, list):
            raise ValueError("modules must be an array")
        sanitized: list[dict[str, Any]] = []
        for mod in raw_modules:
            if not isinstance(mod, dict):
                continue
            sanitized.append({
                "id": str(mod.get("id", ""))[:64],
                "label": str(mod.get("label", ""))[:120],
                "icon": str(mod.get("icon", ""))[:32],
                "enabled": bool(mod.get("enabled", True)),
            })
        allowed["modules"] = sanitized

    return allowed


@app.route("/workspaces/<workspace_id>/branding", methods=["GET"])
def workspace_branding_get(workspace_id: str):
    """Return the stored branding/theme config for a workspace.

    This endpoint is intentionally public so that public/unsigned pages such as
    login and landing pages can load per-tenant branding.
    """
    config = get_workspace_theme_config(workspace_id)
    return jsonify({
        "ok": True,
        "workspace_id": workspace_id,
        "branding": config or {},
    })


@app.route("/workspaces/<workspace_id>/branding", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def workspace_branding_update(workspace_id: str):
    """Update the branding/theme config for a workspace. Admin only."""
    data = request.json or {}
    try:
        validated = _validate_branding_payload(data)
        updated = update_workspace_theme_config(workspace_id, validated)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({
        "ok": True,
        "workspace_id": workspace_id,
        "branding": updated,
    })


@app.route("/workspaces/<workspace_id>/seed", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def workspace_seed_demo(workspace_id: str):
    """Seed a workspace with realistic demo data. Admin only."""
    try:
        from aeon_seed import seed_demo_workspace
        result = seed_demo_workspace(workspace_id)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404
    except Exception as exc:
        logger.exception("Demo seed failed for workspace %s", workspace_id)
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/ready", methods=["GET"])
def ready():
    """Readiness probe: environment, loaded agents, and job queue."""
    env_report = validate_environment()
    readiness = {
        "ok": env_report["ok"],
        "backend": "aeon_python_kernel",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": env_report,
        "agents_loaded": len(_agents),
        "queue_size": job_queue._pending,
        "queue_workers": job_queue.workers,
    }
    status = 200 if env_report["ok"] else 503
    return jsonify(readiness), status


def _governance_context() -> dict[str, Any]:
    """Extract authenticated user context for audit and governance."""
    ctx = get_current_user_context() or {}
    if ctx:
        return {
            "user_id": ctx.get("user_id"),
            "workspace_id": ctx.get("workspace_id"),
            "email": ctx.get("email"),
        }
    # Legacy header fallback for existing integrations
    data = request.json or {}
    return {
        "user_id": data.get("user_id") or request.headers.get("X-User-Id"),
        "workspace_id": data.get("workspace_id") or request.headers.get("X-Workspace-Id"),
        "email": data.get("email") or request.headers.get("X-User-Email"),
    }


def _log_automation_event(
    action: str,
    ctx: dict[str, Any],
    rule_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit an automation governance audit event.

    The event is queued through the GovernanceManager and flushed to the
    audit_logs table asynchronously.
    """
    workspace_id = ctx.get("workspace_id")
    try:
        get_governance().log_audit(
            action=action,
            module="automations",
            user_id=ctx.get("user_id"),
            workspace_id=workspace_id,
            email=ctx.get("email"),
            metadata=_secure_metadata({"rule_id": rule_id, **(metadata or {})}, workspace_id),
        )
    except Exception as exc:
        logger.warning("Failed to log automation audit event: %s", exc)


def _secure_metadata(metadata: dict[str, Any], workspace_id: str | None = None) -> dict[str, Any]:
    """Sanitize metadata for audit logging based on workspace security config.

    If no workspace_id is provided, only basic PII redaction is applied.
    """
    pii_enabled = True
    phi_enabled = False
    if workspace_id:
        try:
            cfg = get_workspace_security_config(str(workspace_id))
            if cfg:
                pii_enabled = cfg.pii_redaction_enabled
                phi_enabled = cfg.phi_redaction_enabled
        except Exception:  #nosec B110
            pass
    return sanitize_metadata(metadata or {}, pii_enabled=pii_enabled, phi_enabled=phi_enabled)


def _has_workspace_role(ctx: dict[str, Any], workspace_id: str, required_role: str) -> bool:
    """Return True if the user has at least `required_role` in `workspace_id`."""
    from aeon_auth import has_role
    if has_role(ctx.get("role"), "SUPER_ADMIN"):
        return True
    try:
        from aeon_db import get_db
        db = get_db()
        membership = db.get_membership(workspace_id, ctx.get("user_id"))
        if membership and has_role(membership.role, required_role):
            return True
    except Exception:  #nosec B110
        pass
    return False


@app.route("/chat", methods=["POST"])
@require_auth
def chat():
    """Global chat endpoint. Uses the 'default' agent context.
    Supports per-request provider override via the 'provider' field.
    """
    data = request.json or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "missing query"}), 400
    ctx = _governance_context()
    try:
        # Per-request provider override; fall back to the active global QW
        provider_override = data.get("provider")
        if provider_override:
            import aeon as _aeon
            _aeon.QW = get_llm_provider(str(provider_override))
            os.environ["AEON_LLM_PROVIDER"] = str(provider_override)
        agent = get_agent("default")
        result = agent.act(query)
        metrics_collector.inc("aeon_chat_requests_total")
        metrics_collector.inc("aeon_agent_ticks_total", labels={"app_id": "default"})
        get_governance_manager().log_audit(
            action="CHAT",
            module="global",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata=_secure_metadata({"backend": result.get("backend", "unknown"), "provider_override": provider_override}, ctx.get("workspace_id")),
        )
        return jsonify({"ok": True, "data": result, "backend": result.get("backend", "unknown")})
    except Exception as e:
        get_governance_manager().log_audit(
            action="CHAT_ERROR",
            module="global",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata=_secure_metadata({"error": str(e)}, ctx.get("workspace_id")),
        )
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/apps/<app_id>/chat", methods=["POST"])
@require_auth
def app_chat(app_id: str):
    """Module-aware chat endpoint."""
    data = request.json or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "missing query"}), 400
    ctx = _governance_context()
    try:
        agent = get_agent(app_id)
        # Inject module context into the query so the agent is aware of the vertical
        system_hint = data.get("system")
        if system_hint:
            query = f"[{app_id} module context] {system_hint}\n\n{query}"
        result = agent.act(query)
        metrics_collector.inc("aeon_app_chat_requests_total", labels={"app_id": app_id})
        metrics_collector.inc("aeon_agent_ticks_total", labels={"app_id": app_id})
        get_governance_manager().log_audit(
            action="APP_CHAT",
            module=app_id,
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata=_secure_metadata({"backend": result.get("backend", "unknown")}, ctx.get("workspace_id")),
        )
        return jsonify({"ok": True, "data": result, "backend": result.get("backend", "unknown")})
    except Exception as e:
        get_governance_manager().log_audit(
            action="APP_CHAT_ERROR",
            module=app_id,
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata=_secure_metadata({"error": str(e)}, ctx.get("workspace_id")),
        )
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/apps/<app_id>/tick", methods=["POST"])
@require_auth
def app_tick(app_id: str):
    """Run one agent tick for the given app."""
    data = request.json or {}
    query = (data.get("query") or "tick").strip()
    async_mode = bool(data.get("async"))
    ctx = _governance_context()

    if async_mode:
        job_id = job_queue.submit(app_id, "act", {"query": query})
        metrics_collector.inc("aeon_agent_ticks_total", labels={"app_id": app_id})
        get_governance_manager().log_audit(
            action="APP_TICK_QUEUED",
            module=app_id,
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"job_id": job_id, "async": True},
        )
        return jsonify({"ok": True, "status": "queued", "job_id": job_id})

    try:
        agent = get_agent(app_id)
        result = agent.act(query)
        metrics_collector.inc("aeon_agent_ticks_total", labels={"app_id": app_id})
        get_governance_manager().log_audit(
            action="APP_TICK",
            module=app_id,
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"backend": result.get("backend", "unknown")},
        )
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        get_governance_manager().log_audit(
            action="APP_TICK_ERROR",
            module=app_id,
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"error": str(e)},
        )
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/apps/<app_id>/reflect", methods=["POST"])
@require_auth
def app_reflect(app_id: str):
    """Return the agent's current reflection."""
    try:
        agent = get_agent(app_id)
        result = agent.reflect()
        metrics_collector.inc("aeon_agent_reflections_total", labels={"app_id": app_id})
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/jobs/<job_id>", methods=["GET"])
def job_status(job_id: str):
    """Poll the status of an async job."""
    status = job_queue.status(job_id)
    if status is None:
        return jsonify({"ok": False, "error": "job not found"}), 404
    return jsonify({"ok": True, "data": status})


@app.route("/agents", methods=["GET"])
def list_agents():
    """List loaded agent contexts and their vitals."""
    with _agent_lock:
        return jsonify({
            "ok": True,
            "agents": [
                {
                    "app_id": app_id,
                    "ticks": agent.tick_count,
                    "vitals": agent.self_model.vitals(),
                    "open_goals": [g["title"] for g in agent.goals.open_goals()],
                }
                for app_id, agent in _agents.items()
            ],
        })


# ── OS orchestrator singleton (for workflows / swarm) ─────────────────────
_aeon_os_lock = threading.Lock()
_aeon_os_instance: AeonOS | None = None


def get_os() -> AeonOS:
    """Return a singleton AeonOS orchestrator (loads workflow/swarm helpers)."""
    global _aeon_os_instance
    with _aeon_os_lock:
        if _aeon_os_instance is None:
            _aeon_os_instance = AeonOS(root=AEON_ROOT)
            _aeon_os_instance.integration_manager = get_integration_manager()
        return _aeon_os_instance


# ── Workflow endpoints ─────────────────────────────────────────────────────
@app.route("/workflows", methods=["GET", "POST"])
@require_auth
@require_workspace_role("VIEWER")
def workflows_index():
    """List all workflows or create a new one."""
    ctx = _governance_context()
    workspace_id = g.workspace_id
    os_inst = get_os()
    if request.method == "GET":
        return jsonify({"ok": True, "workflows": os_inst.list_workflows()})

    if not _has_workspace_role(ctx, workspace_id, "OPERATOR"):
        return jsonify({"ok": False, "error": "workspace operator required"}), 403

    data = request.json or {}
    workflow = aeon_workflows.WorkflowDefinition(
        id=data.get("id") or f"wf-{int(time.time() * 1000)}",
        name=data.get("name", "Untitled Workflow"),
        description=data.get("description", ""),
        nodes=[aeon_workflows.WorkflowNode(**n) for n in data.get("nodes", [])],
        edges=[aeon_workflows.WorkflowEdge(**e) for e in data.get("edges", [])],
    )
    os_inst.save_workflow(workflow)
    return jsonify({"ok": True, "workflow": workflow.to_dict()})


@app.route("/workflows/<workflow_id>", methods=["GET", "DELETE"])
@require_auth
@require_workspace_role("VIEWER")
def workflow_detail(workflow_id: str):
    ctx = _governance_context()
    workspace_id = g.workspace_id
    os_inst = get_os()
    if request.method == "GET":
        wf = os_inst.get_workflow(workflow_id)
        if wf is None:
            return jsonify({"ok": False, "error": "workflow not found"}), 404
        return jsonify({"ok": True, "workflow": wf.to_dict()})

    if not _has_workspace_role(ctx, workspace_id, "OPERATOR"):
        return jsonify({"ok": False, "error": "workspace operator required"}), 403
    # DELETE
    if os_inst.delete_workflow(workflow_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "workflow not found"}), 404


@app.route("/workflows/<workflow_id>/run", methods=["POST"])
@require_auth
@require_workspace_role("OPERATOR")
def workflow_run(workflow_id: str):
    data = request.json or {}
    initial_input = (data.get("initial_input") or "").strip()
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id") or data.get("workspace_id")
    try:
        # Pass workspace_id so workflow runner uses workspace-scoped agents
        result = get_os().run_workflow(workflow_id, initial_input, workspace_id=workspace_id)
        metrics_collector.inc("aeon_workflow_runs_total", labels={"workflow_id": workflow_id, "ok": str(result.get("ok", True))})
        get_governance_manager().log_audit(
            action="WORKFLOW_RUN",
            module="workflow",
            user_id=ctx.get("user_id"),
            workspace_id=workspace_id,
            email=ctx.get("email"),
            metadata={"workflow_id": workflow_id, "ok": result.get("ok", True)},
        )
        # Workflow completed/failed notification
        wf_ok = result.get("ok", True)
        wf_name = data.get("name", workflow_id)
        if wf_ok:
            _notify(
                user_id=ctx.get("user_id", ""),
                type="workflow_completed",
                title=f"Workflow '{wf_name}' Completed",
                body=f"Workflow {workflow_id} finished successfully in workspace {workspace_id[:8]}...",
                icon="⚡",
                link="/os/workflows",
                workspace_id=workspace_id,
                metadata={"workflow_id": workflow_id},
            )
        else:
            _notify(
                user_id=ctx.get("user_id", ""),
                type="workflow_failed",
                title=f"Workflow '{wf_name}' Failed",
                body=result.get("error", f"Workflow {workflow_id} encountered an error."),
                icon="❌",
                link="/os/workflows",
                workspace_id=workspace_id,
                metadata={"workflow_id": workflow_id},
            )
        # Persist to activity feed and broadcast real-time status update
        log_activity(
            "workflow_status",
            {
                "workflow_id": workflow_id,
                "status": "completed" if wf_ok else "failed",
                "ok": wf_ok,
                "error": result.get("error") if not wf_ok else None,
            },
            user_id=ctx.get("user_id"),
            workspace_id=workspace_id,
        )
        return jsonify(result)
    except Exception as e:
        get_governance_manager().log_audit(
            action="WORKFLOW_RUN_ERROR",
            module="workflow",
            user_id=ctx.get("user_id"),
            workspace_id=workspace_id,
            email=ctx.get("email"),
            metadata={"workflow_id": workflow_id, "error": str(e)},
        )
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Swarm endpoints ────────────────────────────────────────────────────────
@app.route("/swarm/run", methods=["POST"])
@require_auth
@require_workspace_role("OPERATOR")
def swarm_run():
    data = request.json or {}
    app_ids = data.get("app_ids") or []
    prompt = (data.get("prompt") or "").strip()
    roles = data.get("roles") or {}
    ctx = _governance_context()
    if not app_ids or not prompt:
        return jsonify({"ok": False, "error": "app_ids and prompt required"}), 400
    try:
        result = get_os().run_swarm(app_ids, prompt, roles=roles)
        metrics_collector.inc("aeon_swarm_runs_total", labels={"ok": str(result.get("ok", True))})
        get_governance_manager().log_audit(
            action="SWARM_RUN",
            module="swarm",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"app_ids": app_ids, "roles": roles, "ok": result.get("ok", True)},
        )
        # Swarm completed/failed notification
        swarm_ok = result.get("ok", True)
        swarm_id = result.get("swarm_id", "")
        if swarm_ok:
            _notify(
                user_id=ctx.get("user_id", ""),
                type="swarm_completed",
                title="Swarm Completed",
                body=f"Swarm {swarm_id[:8]}... completed with prompt: {prompt[:80]}",
                icon="🐝",
                link=f"/swarms/{swarm_id}" if swarm_id else None,
                workspace_id=ctx.get("workspace_id"),
                metadata={"swarm_id": swarm_id, "app_ids": app_ids},
            )
        else:
            _notify(
                user_id=ctx.get("user_id", ""),
                type="swarm_failed",
                title="Swarm Failed",
                body=result.get("error", f"Swarm with prompt '{prompt[:60]}' encountered an error."),
                icon="⚠️",
                workspace_id=ctx.get("workspace_id"),
                metadata={"swarm_id": swarm_id, "app_ids": app_ids},
            )
        # Persist to activity feed and broadcast real-time status update
        log_activity(
            "swarm_status",
            {
                "swarm_id": swarm_id,
                "status": "completed" if swarm_ok else "failed",
                "ok": swarm_ok,
                "prompt": prompt,
                "app_ids": app_ids,
                "error": result.get("error") if not swarm_ok else None,
            },
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
        )
        return jsonify(result)
    except Exception as e:
        get_governance_manager().log_audit(
            action="SWARM_RUN_ERROR",
            module="swarm",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"app_ids": app_ids, "error": str(e)},
        )
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/swarm/<swarm_id>", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def swarm_status(swarm_id: str):
    """Get the status of a running or completed swarm."""
    try:
        status = get_os().swarm_manager.status(swarm_id)
        return jsonify(status)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/swarm/<swarm_id>/messages", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def swarm_messages(swarm_id: str):
    """Get the message bus log for a swarm."""
    try:
        messages = get_os().swarm_manager.messages(swarm_id)
        return jsonify({"ok": True, "swarm_id": swarm_id, "messages": messages})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── API Key Management endpoints ───────────────────────────────────────
_api_key_manager: ApiKeyManager | None = None


def get_api_key_manager() -> ApiKeyManager:
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = ApiKeyManager(AEON_ROOT)
    return _api_key_manager


def _extract_api_key() -> str | None:
    """Extract an API key from the request headers."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    key = request.headers.get("X-API-Key")
    if key:
        return key.strip()
    return None


def require_api_key(f):
    """Decorator to validate an API key on a route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        plaintext = _extract_api_key()
        if not plaintext:
            return jsonify({"ok": False, "error": "missing API key"}), 401
        mgr = get_api_key_manager()
        key = mgr.validate_key(plaintext)
        if not key:
            return jsonify({"ok": False, "error": "invalid API key"}), 401
        # Check rate limit
        if not mgr.check_rate_limit(key.key_hash):
            return jsonify({"ok": False, "error": "API key rate limit exceeded"}), 429
        g.api_key = key
        return f(*args, **kwargs)
    return decorated


@app.route("/api-keys", methods=["GET", "POST"])
@require_auth
@require_workspace_role("VIEWER")
def api_keys_index():
    """List API keys for a workspace or create a new one (ADMIN only)."""
    ctx = _governance_context()
    workspace_id = g.workspace_id
    mgr = get_api_key_manager()

    if request.method == "GET":
        keys = mgr.list_keys(workspace_id=workspace_id)
        return jsonify({"ok": True, "keys": [k.to_dict() for k in keys], "workspace_id": workspace_id})

    # POST - create a new key (ADMIN only)
    if not _has_workspace_role(ctx, workspace_id, "ADMIN"):
        return jsonify({"ok": False, "error": "workspace admin required"}), 403

    data = request.json or {}
    name = data.get("name", "Unnamed Key")
    rate_limit = min(10000, max(1, int(data.get("rate_limit_per_min", 100))))
    key, plaintext = mgr.create_key(
        name=name,
        workspace_id=workspace_id,
        user_id=ctx.get("user_id"),
        rate_limit_per_min=rate_limit,
    )
    get_governance_manager().log_audit(
        action="API_KEY_CREATED",
        module="api_keys",
        user_id=ctx.get("user_id"),
        workspace_id=workspace_id,
        email=ctx.get("email"),
        metadata={"key_id": key.id, "name": name},
    )
    # API key created notification
    _notify(
        user_id=ctx.get("user_id", ""),
        type="api_key_created",
        title=f"API Key Created: {name}",
        body=f"A new API key '{name}' was created for workspace {workspace_id[:8]}...",
        icon="🔑",
        link="/os/api-keys",
        workspace_id=workspace_id,
    )
    # Return the plaintext key exactly once - it cannot be retrieved again!
    return jsonify({"ok": True, "key": key.to_dict(), "plaintext_key": plaintext})


@app.route("/api-keys/<key_id>", methods=["GET", "DELETE", "PATCH"])
@require_auth
@require_workspace_role("VIEWER")
def api_key_detail(key_id: str):
    """Get, revoke, or update an API key."""
    mgr = get_api_key_manager()
    ctx = _governance_context()
    workspace_id = g.workspace_id

    if request.method == "GET":
        key = mgr.get_key_by_id(key_id)
        if not key or key.workspace_id != workspace_id:
            return jsonify({"ok": False, "error": "key not found"}), 404
        return jsonify({"ok": True, "key": key.to_dict()})

    if request.method == "DELETE":
        if not _has_workspace_role(ctx, workspace_id, "ADMIN"):
            return jsonify({"ok": False, "error": "workspace admin required"}), 403
        key = mgr.get_key_by_id(key_id)
        if not key or key.workspace_id != workspace_id:
            return jsonify({"ok": False, "error": "key not found"}), 404
            if mgr.revoke_key(key_id):
                get_governance_manager().log_audit(
                    action="API_KEY_REVOKED",
                    module="api_keys",
                    user_id=ctx.get("user_id"),
                    workspace_id=workspace_id,
                    email=ctx.get("email"),
                    metadata={"key_id": key_id, "name": key.name},
                )
                # API key revoked notification
                _notify(
                    user_id=ctx.get("user_id", ""),
                    type="api_key_revoked",
                    title=f"API Key Revoked: {key.name}",
                    body=f"The API key '{key.name}' has been revoked.",
                    icon="🗑️",
                    link="/os/api-keys",
                    workspace_id=workspace_id,
                )
                return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "key not found"}), 404

    # PATCH - update key metadata (ADMIN only)
    if not _has_workspace_role(ctx, workspace_id, "ADMIN"):
        return jsonify({"ok": False, "error": "workspace admin required"}), 403
    data = request.json or {}
    key = mgr.get_key_by_id(key_id)
    if not key or key.workspace_id != workspace_id:
        return jsonify({"ok": False, "error": "key not found"}), 404
    updated = mgr.update_key(
        key_id,
        name=data.get("name"),
        enabled=data.get("enabled"),
        rate_limit_per_min=data.get("rate_limit_per_min"),
    )
    if updated:
        get_governance_manager().log_audit(
            action="API_KEY_UPDATED",
            module="api_keys",
            user_id=ctx.get("user_id"),
            workspace_id=workspace_id,
            email=ctx.get("email"),
            metadata={"key_id": key_id, "changes": list(data.keys())},
        )
        return jsonify({"ok": True, "key": updated.to_dict()})
    return jsonify({"ok": False, "error": "update failed"}), 500


@app.route("/api-keys/<key_id>/rotate", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def api_key_rotate(key_id: str):
    """Rotate an API key, returning a new plaintext key and revoking the old one."""
    mgr = get_api_key_manager()
    ctx = _governance_context()
    workspace_id = g.workspace_id

    old_key = mgr.get_key_by_id(key_id)
    if not old_key or old_key.workspace_id != workspace_id:
        return jsonify({"ok": False, "error": "key not found"}), 404

    new_key, plaintext = mgr.rotate_key(key_id, user_id=ctx.get("user_id"))
    if not new_key:
        return jsonify({"ok": False, "error": "rotation failed"}), 500

    get_governance_manager().log_audit(
        action="API_KEY_ROTATED",
        module="api_keys",
        user_id=ctx.get("user_id"),
        workspace_id=workspace_id,
        email=ctx.get("email"),
        metadata={"old_key_id": key_id, "new_key_id": new_key.id},
    )
    # API key rotated notification
    _notify(
        user_id=ctx.get("user_id", ""),
        type="api_key_rotated",
        title=f"API Key Rotated: {old_key.name}",
        body=f"The API key '{old_key.name}' was rotated. Update any services using the old key.",
        icon="🔄",
        link="/os/api-keys",
        workspace_id=workspace_id,
    )
    return jsonify({"ok": True, "key": new_key.to_dict(), "plaintext_key": plaintext})


@app.route("/api-keys/<key_id>/usage", methods=["GET"])
@require_auth
def api_key_usage(key_id: str):
    """Get usage statistics for a specific API key."""
    mgr = get_api_key_manager()
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id", "default")
    days = min(365, max(1, request.args.get("days", 30, type=int)))

    key = mgr.get_key_by_id(key_id)
    if not key or key.workspace_id != workspace_id:
        return jsonify({"ok": False, "error": "key not found"}), 404

    stats = mgr.get_usage_stats(key_id=key_id, days=days)
    return jsonify({"ok": True, "usage": stats})


@app.route("/api-keys/usage/summary", methods=["GET"])
@require_auth
def api_keys_usage_summary():
    """Get aggregate usage statistics for all keys in a workspace."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id") or request.args.get("workspace_id", "default")
    days = min(365, max(1, request.args.get("days", 30, type=int)))
    mgr = get_api_key_manager()
    stats = mgr.get_usage_stats(workspace_id=workspace_id, days=days)
    keys = mgr.list_keys(workspace_id=workspace_id)
    stats["total_keys"] = len(keys)
    stats["active_keys"] = len([k for k in keys if k.enabled])
    return jsonify({"ok": True, "usage": stats})


# ── Usage / Billing / Observability endpoints ────────────────────────────
_usage_meter: UsageMeter | None = None
_billing_calculator: BillingCalculator | None = None
_health_collector: HealthCollector | None = None


def get_usage_meter() -> UsageMeter:
    global _usage_meter
    if _usage_meter is None:
        _usage_meter = UsageMeter(AEON_ROOT)
    return _usage_meter


def get_billing_calculator() -> BillingCalculator:
    global _billing_calculator
    if _billing_calculator is None:
        _billing_calculator = BillingCalculator(AEON_ROOT, meter=get_usage_meter())
    return _billing_calculator


def get_health_collector() -> HealthCollector:
    global _health_collector
    if _health_collector is None:
        _health_collector = HealthCollector(AEON_ROOT)
    return _health_collector


def get_governance_manager() -> GovernanceManager:
    return get_governance()


# ── Governance endpoints ────────────────────────────────────────────────────
@app.route("/governance/audit", methods=["GET"])
@require_auth
def governance_audit():
    # Audit logs are workspace-admin or super-admin only
    workspace_id = request.args.get("workspace_id")
    if workspace_id and not _has_workspace_role(_governance_context(), workspace_id, "ADMIN"):
        return jsonify({"ok": False, "error": "workspace admin required"}), 403
    action = request.args.get("action")
    module = request.args.get("module")
    limit = min(1000, max(1, request.args.get("limit", 100, type=int)))
    offset = max(0, request.args.get("offset", 0, type=int))
    result = get_governance_manager().query_audit(
        workspace_id=workspace_id,
        action=action,
        module=module,
        limit=limit,
        offset=offset,
    )
    return jsonify(result)


@app.route("/governance/compliance", methods=["GET", "POST"])
@require_auth
def governance_compliance():
    workspace_id = (request.json or {}).get("workspace_id") or request.args.get("workspace_id")
    if workspace_id and not _has_workspace_role(_governance_context(), workspace_id, "ADMIN"):
        return jsonify({"ok": False, "error": "workspace admin required"}), 403
    if request.method == "GET":
        check_type = request.args.get("check_type", "pii_scan")
        workspace_id = request.args.get("workspace_id")
        result = get_governance_manager().run_compliance_check(check_type, workspace_id)
        return jsonify(result)

    data = request.json or {}
    check_type = data.get("check_type", "pii_scan")
    workspace_id = data.get("workspace_id")
    result = get_governance_manager().run_compliance_check(check_type, workspace_id)
    return jsonify(result)


@app.route("/governance/retention", methods=["GET", "POST"])
@require_auth
def governance_retention():
    workspace_id = (request.json or {}).get("workspace_id") or request.args.get("workspace_id")
    if workspace_id and not _has_workspace_role(_governance_context(), workspace_id, "ADMIN"):
        return jsonify({"ok": False, "error": "workspace admin required"}), 403
    if request.method == "GET":
        workspace_id = request.args.get("workspace_id")
        # RBAC already checked above if workspace_id was present
        return jsonify({"ok": True, "policy": get_governance_manager().get_retention_policy(workspace_id)})

    data = request.json or {}
    workspace_id = data.get("workspace_id")
    retention_days = int(data.get("retention_days", 365))
    action = data.get("action", "archive")
    if not workspace_id:
        return jsonify({"ok": False, "error": "workspace_id required"}), 400
    result = get_governance_manager().set_retention_policy(workspace_id, retention_days, action)
    return jsonify(result)


# ── Integration / API Gateway endpoints ────────────────────────────────────
_integration_manager: IntegrationManager | None = None


def get_integration_manager() -> IntegrationManager:
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = IntegrationManager(AEON_ROOT)
    return _integration_manager


@app.route("/integrations", methods=["GET", "POST"])
@require_auth
@require_workspace_role("VIEWER")
def integrations_index():
    ctx = _governance_context()
    workspace_id = g.workspace_id
    mgr = get_integration_manager()
    if request.method == "GET":
        return jsonify({"ok": True, "integrations": mgr.list_integrations(mask=True)})

    if not _has_workspace_role(ctx, workspace_id, "OPERATOR"):
        return jsonify({"ok": False, "error": "workspace operator required"}), 403

    data = request.json or {}
    integration_id = data.get("id")
    cfg = mgr.save(data, integration_id=integration_id)
    return jsonify({"ok": True, "integration": cfg.to_dict(mask=True)})


@app.route("/integrations/<integration_id>", methods=["GET", "DELETE"])
@require_auth
@require_workspace_role("VIEWER")
def integration_detail(integration_id: str):
    mgr = get_integration_manager()
    ctx = _governance_context()
    workspace_id = g.workspace_id
    if request.method == "GET":
        cfg = mgr.get(integration_id)
        if cfg is None:
            return jsonify({"ok": False, "error": "integration not found"}), 404
        return jsonify({"ok": True, "integration": cfg.to_dict(mask=True)})

    # DELETE - requires OPERATOR or above in the workspace
    if not _has_workspace_role(ctx, workspace_id, "OPERATOR"):
        return jsonify({"ok": False, "error": "workspace operator required"}), 403
    if mgr.delete(integration_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "integration not found"}), 404


@app.route("/integrations/<integration_id>/run", methods=["POST"])
@require_auth
@require_workspace_role("OPERATOR")
def integration_run(integration_id: str):
    data = request.json or {}
    endpoint = data.get("endpoint", "")
    method = data.get("method", "GET")
    payload = data.get("payload")
    ctx = _governance_context()
    try:
        result = get_integration_manager().run(integration_id, endpoint=endpoint, method=method, payload=payload)
        metrics_collector.inc("aeon_integration_runs_total", labels={"integration_id": integration_id, "ok": str(result.get("ok", True))})
        get_governance_manager().log_audit(
            action="INTEGRATION_RUN",
            module="integrations",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"integration_id": integration_id, "endpoint": endpoint, "method": method, "ok": result.get("ok", True)},
        )
        return jsonify(result)
    except Exception as e:
        get_governance_manager().log_audit(
            action="INTEGRATION_RUN_ERROR",
            module="integrations",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"integration_id": integration_id, "error": str(e)},
        )
        # Integration error notification
        _notify(
            user_id=ctx.get("user_id", ""),
            type="integration_error",
            title=f"Integration Run Failed: {integration_id[:8]}...",
            body=str(e)[:200],
            icon="🔌",
            workspace_id=ctx.get("workspace_id"),
            metadata={"integration_id": integration_id},
        )
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/proxy", methods=["POST"])
@require_auth
def proxy_request():
    data = request.json or {}
    integration_id = data.get("integration_id")
    ctx = _governance_context()
    if not integration_id:
        return jsonify({"ok": False, "error": "integration_id required"}), 400
    endpoint = data.get("endpoint", "")
    method = data.get("method", "GET")
    payload = data.get("payload")
    try:
        result = get_integration_manager().proxy(integration_id, endpoint=endpoint, method=method, payload=payload)
        metrics_collector.inc("aeon_proxy_requests_total", labels={"integration_id": integration_id, "ok": str(result.get("ok", True))})
        get_governance_manager().log_audit(
            action="PROXY_REQUEST",
            module="integrations",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"integration_id": integration_id, "endpoint": endpoint, "method": method, "ok": result.get("ok", True)},
        )
        return jsonify(result)
    except Exception as e:
        get_governance_manager().log_audit(
            action="PROXY_REQUEST_ERROR",
            module="integrations",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"integration_id": integration_id, "error": str(e)},
        )
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/webhooks/receive/<integration_id>", methods=["POST"])
@require_auth
def webhook_receive(integration_id: str):
    mgr = get_integration_manager()
    raw = request.get_data()
    signature = request.headers.get("X-Hub-Signature-256") or request.headers.get("X-Webhook-Signature")
    verified = mgr.verify_webhook(integration_id, signature, raw)
    delivery = WebhookDelivery(
        id=f"wh-{int(time.time() * 1000)}-{id(request)}",
        integration_id=integration_id,
        timestamp=time.time(),
        payload=request.json or {},
        response_status=200 if verified else 401,
        error_message=None if verified else "webhook signature verification failed",
    )
    mgr.record_delivery(delivery)
    metrics_collector.inc("aeon_webhook_deliveries_total", labels={"verified": str(verified)})
    get_governance_manager().log_audit(
        action="WEBHOOK_RECEIVED",
        module="integrations",
        metadata={"integration_id": integration_id, "verified": verified, "delivery_id": delivery.id},
    )
    if not verified:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    return jsonify({"ok": True, "delivery_id": delivery.id})


@app.route("/integrations/catalog", methods=["GET"])
def integrations_catalog():
    """Return the catalog of available integration types (marketplace)."""
    return jsonify({"ok": True, "catalog": get_integration_catalog()})


@app.route("/webhooks/deliveries", methods=["GET"])
@require_auth
def webhook_deliveries():
    limit = min(100, max(1, request.args.get("limit", 100, type=int)))
    return jsonify({"ok": True, "deliveries": get_integration_manager().list_deliveries(limit=limit)})


# ── Usage, Billing & Observability endpoints ───────────────────────────────
@app.route("/billing/<workspace_id>/plan", methods=["POST"])
@require_workspace_access
def billing_set_plan(workspace_id: str):
    """Upgrade/downgrade a workspace plan."""
    if not _has_workspace_role(_governance_context(), workspace_id, "ADMIN"):
        return jsonify({"ok": False, "error": "workspace admin required"}), 403
    data = request.json or {}
    plan_id = data.get("plan_id", "free")
    credits = float(data.get("credits", 0))

    valid_plans = list(get_billing_calculator().plans.keys())
    if plan_id not in valid_plans:
        return jsonify({"ok": False, "error": f"invalid plan '{plan_id}'. Valid: {valid_plans}"}), 400

    ctx = _governance_context()
    try:
        get_billing_calculator().set_plan(workspace_id, plan_id, credits)
        status = get_billing_calculator().workspace_status(workspace_id)
        get_governance_manager().log_audit(
            action="BILLING_PLAN_CHANGE",
            module="billing",
            workspace_id=workspace_id,
            metadata={"plan_id": plan_id, "credits": credits},
        )
        # Plan change notification
        _notify(
            user_id=ctx.get("user_id", ""),
            type="plan_changed",
            title=f"Plan Updated to {plan_id.title()}",
            body=f"Workspace {workspace_id[:8]}... has been updated to the {plan_id} plan.",
            icon="⭐",
            workspace_id=workspace_id,
            metadata={"plan_id": plan_id, "credits": credits},
        )
        return jsonify({"ok": True, "billing": status})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/billing/<workspace_id>/credits", methods=["POST"])
@require_workspace_access
def billing_add_credits(workspace_id: str):
    """Add credits to a workspace (simulated payment)."""
    if not _has_workspace_role(_governance_context(), workspace_id, "ADMIN"):
        return jsonify({"ok": False, "error": "workspace admin required"}), 403
    data = request.json or {}
    amount = float(data.get("amount", 0))
    if amount <= 0:
        return jsonify({"ok": False, "error": "amount must be positive"}), 400

    ctx = _governance_context()
    try:
        get_billing_calculator().add_credits(workspace_id, amount)
        status = get_billing_calculator().workspace_status(workspace_id)
        get_governance_manager().log_audit(
            action="BILLING_CREDITS_ADDED",
            module="billing",
            workspace_id=workspace_id,
            metadata={"amount": amount, "new_credits": status["credits"]},
        )
        # Credits added notification
        _notify(
            user_id=ctx.get("user_id", ""),
            type="credits_added",
            title=f"{amount} Credits Added",
            body=f"{amount} credits added to workspace {workspace_id[:8]}...",
            icon="💰",
            workspace_id=workspace_id,
            metadata={"amount": amount, "new_credits": status.get("credits")},
        )
        return jsonify({"ok": True, "billing": status})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/usage", methods=["POST"])
@require_auth
def usage_record():
    """Record one or more usage events."""
    data = request.json or {}
    events = data if isinstance(data, list) else [data]
    recorded = []
    ctx = _governance_context()
    for item in events:
        event = get_usage_meter().record_event(
            action=item.get("action", "unknown"),
            module=item.get("module", "global"),
            quantity=float(item.get("quantity", 1)),
            cost=float(item.get("cost", 0)),
            user_id=item.get("user_id"),
            workspace_id=item.get("workspace_id"),
            metadata=item.get("metadata", {}),
        )
        recorded.append(event.to_dict())
    get_governance_manager().log_audit(
        action="USAGE_RECORDED",
        module="usage",
        user_id=ctx.get("user_id"),
        workspace_id=ctx.get("workspace_id"),
        email=ctx.get("email"),
        metadata={"count": len(recorded)},
    )
    return jsonify({"ok": True, "recorded": recorded})


@app.route("/usage/summary", methods=["GET"])
@require_auth
def usage_summary():
    workspace_id = request.args.get("workspace_id")
    days = min(365, max(1, request.args.get("days", 30, type=int)))
    summary = get_usage_meter().get_summary(workspace_id=workspace_id, days=days)
    return jsonify({"ok": True, "summary": summary})


@app.route("/billing/<workspace_id>", methods=["GET"])
@require_workspace_access
def billing_status(workspace_id: str):
    days = min(365, max(1, request.args.get("days", 30, type=int)))
    return jsonify({"ok": True, "billing": get_billing_calculator().workspace_status(workspace_id, days=days)})


# ── Stripe Payment Integration endpoints ──────────────────────────────────
@app.route("/stripe/checkout", methods=["POST"])
@require_auth
def stripe_checkout():
    """Create a Stripe Checkout Session for workspace subscription upgrade.
    Falls back to simulated upgrade when Stripe is not configured.
    """
    data = request.json or {}
    workspace_id = data.get("workspace_id", "")
    plan_id = data.get("plan_id", "team")
    success_url = data.get("success_url", "")
    cancel_url = data.get("cancel_url", "")
    ctx = _governance_context()

    if not workspace_id:
        workspace_id = ctx.get("workspace_id", "")
    if not workspace_id:
        return jsonify({"ok": False, "error": "workspace_id required"}), 400

    try:
        client = get_stripe_client()
        result = client.create_checkout_session(
            workspace_id=workspace_id,
            plan_id=plan_id,
            success_url=success_url or "https://app.aeon.ai/os/billing",
            cancel_url=cancel_url or "https://app.aeon.ai/os/billing",
            customer_email=ctx.get("email", ""),
        )
        get_governance_manager().log_audit(
            action="STRIPE_CHECKOUT_CREATED",
            module="billing",
            user_id=ctx.get("user_id"),
            workspace_id=workspace_id,
            email=ctx.get("email"),
            metadata={"plan_id": plan_id, "simulated": result.get("simulated", False)},
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/stripe/portal", methods=["POST"])
@require_auth
def stripe_portal():
    """Create a Stripe Billing Portal session for managing subscriptions."""
    data = request.json or {}
    workspace_id = data.get("workspace_id", "")
    return_url = data.get("return_url", "")
    ctx = _governance_context()

    if not workspace_id:
        workspace_id = ctx.get("workspace_id", "")
    if not workspace_id:
        return jsonify({"ok": False, "error": "workspace_id required"}), 400

    try:
        client = get_stripe_client()
        result = client.create_portal_session(
            workspace_id=workspace_id,
            return_url=return_url or "https://app.aeon.ai/os/billing",
        )
        get_governance_manager().log_audit(
            action="STRIPE_PORTAL_CREATED",
            module="billing",
            user_id=ctx.get("user_id"),
            workspace_id=workspace_id,
            email=ctx.get("email"),
            metadata={"simulated": result.get("simulated", False)},
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook_receive():
    """Receive Stripe webhook events. Does NOT require auth - Stripe signs the payload."""
    raw_body = request.get_data()
    signature = request.headers.get("Stripe-Signature", "")
    client = get_stripe_client()

    if not client.available:
        logger.warning("Stripe webhook received but Stripe is not configured")
        return jsonify({"ok": False, "error": "Stripe not configured"}), 503

    result = client.handle_webhook(raw_body, signature)
    if not result.get("ok"):
        return jsonify(result), 400

    get_governance_manager().log_audit(
        action="STRIPE_WEBHOOK",
        module="billing",
        metadata={"type": result.get("type"), "handled": result.get("handled")},
    )
    return jsonify(result)


@app.route("/stripe/subscription/<workspace_id>", methods=["GET"])
@require_auth
def stripe_subscription_status(workspace_id: str):
    """Get the Stripe subscription status for a workspace."""
    try:
        status = get_stripe_client().get_subscription_status(workspace_id)
        return jsonify({"ok": True, **status})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/stripe/config", methods=["GET"])
@require_auth
def stripe_config():
    """Return Stripe configuration status."""
    client = get_stripe_client()
    return jsonify({
        "ok": True,
        "available": client.available,
        "mode": "test" if "sk_test_" in os.environ.get("STRIPE_API_KEY", "") else "live" if client.available else None,
        "prices_configured": all(
            os.environ.get(k, "").strip()
            for k in ["STRIPE_PRICE_TEAM"]
        ) if client.available else False,
    })


@app.route("/health/detailed", methods=["GET"])
@require_auth
def health_detailed():
    with _agent_lock:
        vitals = [
            {"app_id": app_id, "ticks": agent.tick_count, "vitals": agent.self_model.vitals()}
            for app_id, agent in _agents.items()
        ]
    integrations = [
        {"id": cfg.id, "name": cfg.name, "type": cfg.type, "enabled": cfg.enabled}
        for cfg in get_integration_manager().list_integrations(mask=False)
    ]
    return jsonify(
        get_health_collector().snapshot(
            agent_vitals=vitals,
            queue_size=job_queue._pending,
            integrations=integrations,
        )
    )


@app.route("/metrics", methods=["GET"])
def metrics_index():
    """Return Prometheus/OpenMetrics metrics, or JSON summary if ?format=json."""
    if request.args.get("format") == "json":
        days = min(365, max(1, request.args.get("days", 30, type=int)))
        summary = get_usage_meter().get_summary(workspace_id=None, days=days)
        return jsonify({"ok": True, "metrics": summary})

    # Update dynamic gauges before rendering
    metrics_collector.set_gauge("aeon_agents_loaded", len(_agents))
    metrics_collector.set_gauge("aeon_job_queue_size", job_queue._pending)

    body = metrics_collector.render()
    return Response(body, mimetype="text/plain; version=0.0.4; charset=utf-8")


# ── OpenAPI / Swagger documentation (Phase 10) ───────────────────────────────
_OPENAPI_SPEC_PATH = Path(__file__).parent / "docs" / "openapi.json"
_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>AEON OS API Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <style>html{box-sizing:border-box}body{margin:0}</style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function () {
      window.ui = SwaggerUIBundle({
        url: "/openapi.json",
        dom_id: "#swagger-ui",
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.presets.standaloneLayout],
        layout: "BaseLayout",
      });
    };
  </script>
</body>
</html>
"""


@app.route("/openapi.json", methods=["GET"])
def openapi_json():
    """Return the AEON OpenAPI specification as JSON."""
    if _OPENAPI_SPEC_PATH.exists():
        spec = json.loads(_OPENAPI_SPEC_PATH.read_text(encoding="utf-8"))
        # Inject the current server URL based on the request
        spec["servers"] = [
            {"url": request.url_root.rstrip("/"), "description": "Current server"},
            {"url": "http://localhost:5000", "description": "Local development server"},
        ]
        return jsonify(spec)
    return jsonify({"ok": False, "error": "OpenAPI spec not found"}), 404


@app.route("/docs", methods=["GET"])
def swagger_docs():
    """Serve interactive Swagger UI documentation."""
    return Response(_SWAGGER_UI_HTML, mimetype="text/html")


# ── LLM Provider Management endpoints (Phase 1) ─────────────────────────
@app.route("/llm/providers", methods=["GET"])
@require_auth
def llm_providers():
    """Return all available LLM providers with their configuration status."""
    return jsonify({"ok": True, "providers": list_providers()})


@app.route("/llm/switch", methods=["POST"])
@require_auth
def llm_switch():
    """Switch the active LLM provider at runtime."""
    data = request.json or {}
    provider_id = data.get("provider", "").strip().lower()
    if not provider_id:
        return jsonify({"ok": False, "error": "provider required"}), 400
    result = set_active_provider(provider_id)
    if not result.get("ok"):
        return jsonify(result), 400
    ctx = _governance_context()
    get_governance_manager().log_audit(
        action="LLM_PROVIDER_SWITCH",
        module="llm",
        user_id=ctx.get("user_id"),
        workspace_id=ctx.get("workspace_id"),
        email=ctx.get("email"),
        metadata={"provider": provider_id},
    )
    logger.info("LLM provider switched to: %s", provider_id)
    return jsonify(result)


@app.route("/llm/test", methods=["POST"])
@require_auth
def llm_test():
    """Test a provider (or the current active one) with a simple prompt."""
    data = request.json or {}
    provider_id = data.get("provider") or None
    prompt = data.get("prompt") or None
    result = _test_llm_provider(provider_id, prompt)
    return jsonify(result)


# ── Prompt Registry & RAG endpoints ──────────────────────────────────────────
_prompt_registry: Any | None = None
_kb_manager: Any | None = None
_rag_orchestrator: Any | None = None


def get_prompt_registry():
    global _prompt_registry
    if _prompt_registry is None:
        from aeon_rag import PromptRegistry
        _prompt_registry = PromptRegistry(AEON_ROOT)
    return _prompt_registry


def get_kb_manager():
    global _kb_manager
    if _kb_manager is None:
        from aeon_rag import KnowledgeBaseManager
        _kb_manager = KnowledgeBaseManager(AEON_ROOT)
    return _kb_manager


def get_rag_orchestrator():
    global _rag_orchestrator
    if _rag_orchestrator is None:
        from aeon_rag import RAGOrchestrator
        _rag_orchestrator = RAGOrchestrator(AEON_ROOT)
    return _rag_orchestrator


@app.route("/prompts", methods=["GET", "POST"])
@require_auth
def prompts_index():
    reg = get_prompt_registry()
    ctx = _governance_context()
    if request.method == "GET":
        return jsonify({"ok": True, "prompts": reg.list_prompts()})

    data = request.json or {}
    if not data.get("name"):
        return jsonify({"ok": False, "error": "name is required"}), 400
    prompt = reg.save_prompt(data)
    get_governance_manager().log_audit(
        action="PROMPT_CREATED",
        module="ai_studio",
        user_id=ctx.get("user_id"),
        workspace_id=ctx.get("workspace_id"),
        email=ctx.get("email"),
        metadata={"prompt_id": prompt.id, "name": prompt.name},
    )
    return jsonify({"ok": True, "prompt": prompt.to_dict()})


@app.route("/prompts/<prompt_id>", methods=["GET", "DELETE"])
@require_auth
def prompt_detail(prompt_id: str):
    reg = get_prompt_registry()
    ctx = _governance_context()
    if request.method == "GET":
        prompt = reg.get_prompt(prompt_id)
        if not prompt:
            return jsonify({"ok": False, "error": "prompt not found"}), 404
        return jsonify({"ok": True, "prompt": prompt.to_dict()})

    if reg.delete_prompt(prompt_id):
        get_governance_manager().log_audit(
            action="PROMPT_DELETED",
            module="ai_studio",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"prompt_id": prompt_id},
        )
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "prompt not found"}), 404


@app.route("/knowledge-bases", methods=["GET", "POST"])
@require_auth
def knowledge_bases_index():
    mgr = get_kb_manager()
    ctx = _governance_context()
    if request.method == "GET":
        return jsonify({"ok": True, "knowledge_bases": mgr.list_kbs()})

    data = request.json or {}
    if not data.get("name"):
        return jsonify({"ok": False, "error": "name is required"}), 400
    kb = mgr.create_kb(data)
    get_governance_manager().log_audit(
        action="KB_CREATED",
        module="knowledge",
        user_id=ctx.get("user_id"),
        workspace_id=ctx.get("workspace_id"),
        email=ctx.get("email"),
        metadata={"kb_id": kb.id, "name": kb.name},
    )
    return jsonify({"ok": True, "knowledge_base": kb.to_dict()})


@app.route("/knowledge-bases/<kb_id>", methods=["GET", "DELETE"])
@require_auth
def knowledge_base_detail(kb_id: str):
    mgr = get_kb_manager()
    ctx = _governance_context()
    if request.method == "GET":
        kb = mgr.get_kb(kb_id)
        if not kb:
            return jsonify({"ok": False, "error": "knowledge base not found"}), 404
        return jsonify({"ok": True, "knowledge_base": kb.to_dict()})

    if mgr.delete_kb(kb_id):
        get_governance_manager().log_audit(
            action="KB_DELETED",
            module="knowledge",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"kb_id": kb_id},
        )
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "knowledge base not found"}), 404


@app.route("/knowledge-bases/<kb_id>/documents", methods=["POST"])
@require_auth
def knowledge_base_upload(kb_id: str):
    data = request.json or {}
    text = (data.get("text") or "").strip()
    doc_id = data.get("doc_id") or f"doc-{int(time.time() * 1000)}"
    ctx = _governance_context()
    if not text:
        return jsonify({"ok": False, "error": "text is required"}), 400
    try:
        result = get_kb_manager().add_document(kb_id, doc_id, text, metadata=data.get("metadata", {}))
        get_governance_manager().log_audit(
            action="KB_DOCUMENT_UPLOADED",
            module="knowledge",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"kb_id": kb_id, "doc_id": doc_id, "chunks": result.get("chunks", 0)},
        )
        return jsonify({"ok": True, **result})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/knowledge-bases/<kb_id>/query", methods=["POST"])
@require_auth
def knowledge_base_query(kb_id: str):
    data = request.json or {}
    query = (data.get("query") or "").strip()
    top_k = min(20, max(1, int(data.get("top_k", 5))))
    mode = data.get("mode", "hybrid")
    ctx = _governance_context()
    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400
    try:
        chunks = get_kb_manager().query(kb_id, query, top_k=top_k, mode=mode)
        get_governance_manager().log_audit(
            action="KB_QUERY",
            module="knowledge",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"kb_id": kb_id, "mode": mode, "top_k": top_k},
        )
        return jsonify({"ok": True, "chunks": chunks, "mode": mode})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/knowledge-bases/<kb_id>/stats", methods=["GET"])
@require_auth
def knowledge_base_stats(kb_id: str):
    try:
        stats = get_kb_manager().stats(kb_id)
        return jsonify({"ok": True, "stats": stats})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/rag/chat", methods=["POST"])
@require_auth
def rag_chat():
    data = request.json or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    kb_id = data.get("kb_id")
    prompt_id = data.get("prompt_id")
    variables = data.get("variables", {})
    top_k = min(20, max(1, int(data.get("top_k", 5))))
    ctx = _governance_context()

    try:
        result = get_rag_orchestrator().chat(
            kb_id=kb_id,
            prompt_id=prompt_id,
            variables=variables,
            query=query,
            top_k=top_k,
        )
        get_governance_manager().log_audit(
            action="RAG_CHAT",
            module="knowledge",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"kb_id": kb_id, "prompt_id": prompt_id, "ok": result.get("ok", True)},
        )
        return jsonify(result)
    except Exception as e:
        get_governance_manager().log_audit(
            action="RAG_CHAT_ERROR",
            module="knowledge",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"kb_id": kb_id, "prompt_id": prompt_id, "error": str(e)},
        )
        return jsonify({"ok": False, "error": str(e)}), 500


def _create_rule_snapshot(supabase_url: str, service_key: str, rule: dict, ctx: dict) -> dict | None:
    """Persist a snapshot of an automation rule. Returns the snapshot row or None."""
    try:
        payload = {
            "rule_id": rule.get("id"),
            "workspace_id": rule.get("workspace_id") or ctx.get("workspace_id"),
            "name": rule.get("name"),
            "event_type": rule.get("event_type"),
            "condition": rule.get("condition") or {},
            "action_type": rule.get("action_type"),
            "action_config": rule.get("action_config") or {},
            "actions": rule.get("actions") or [],
            "enabled": rule.get("enabled", True),
            "approval_required": rule.get("approval_required", False),
            "approver_message": rule.get("approver_message", ""),
            "schedule_type": rule.get("schedule_type", "event"),
            "cron_expression": rule.get("cron_expression"),
            "cooldown_minutes": rule.get("cooldown_minutes", 0),
            "created_by": ctx.get("user_id"),
        }
        r = requests.post(
            f"{supabase_url}/rest/v1/automation_rule_snapshots",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None
    except Exception as e:
        logger.warning("Failed to create rule snapshot: %s", e)
        return None


# ── Automation rule endpoints ───────────────────────────────────────────────
@app.route("/automations", methods=["GET", "POST"])
@require_auth
@require_workspace_role("OPERATOR")
def automations_index():
    """List or create automation rules for the current workspace."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    if request.method == "GET":
        try:
            r = requests.get(
                f"{supabase_url}/rest/v1/automation_rules",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
                params={
                    "workspace_id": f"eq.{workspace_id}",
                    "order": "created_at.desc",
                },
                timeout=10,
            )
            r.raise_for_status()
            return jsonify({"ok": True, "rules": r.json()})
        except Exception as e:
            logger.warning("Failed to list automation rules: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500

    # POST
    data = request.json or {}
    name = (data.get("name") or "").strip()
    event_type = (data.get("event_type") or "").strip()
    actions = data.get("actions") or []
    action_type = (data.get("action_type") or "").strip()
    schedule_type = (data.get("schedule_type") or "event").strip()
    cron_expression = (data.get("cron_expression") or "").strip()
    if not name or not event_type:
        return jsonify({"ok": False, "error": "name and event_type are required"}), 400

    # Phase 26: support multi-step action chains via `actions` array.
    # Legacy single-action rules use `action_type`/`action_config`.
    if actions:
        for idx, step in enumerate(actions):
            step_type = step.get("type") or step.get("action_type")
            if not step_type:
                return jsonify({"ok": False, "error": f"actions[{idx}] missing type"}), 400
            if step_type not in {"webhook", "outbound_webhook", "swarm", "workflow", "delay", "wait_for_event", "set_variable", "get_variable", "delete_variable", "increment_variable", "call_rule", "transform", "parallel"}:
                return jsonify({"ok": False, "error": f"actions[{idx}] type must be webhook, outbound_webhook, swarm, or workflow"}), 400
            run_if = step.get("run_if")
            if run_if is not None and not isinstance(run_if, dict):
                return jsonify({"ok": False, "error": f"actions[{idx}] run_if must be a condition object or omitted"}), 400
            loop_over = step.get("loop_over")
            if loop_over is not None and not isinstance(loop_over, str):
                return jsonify({"ok": False, "error": f"actions[{idx}] loop_over must be a string path/template or omitted"}), 400
            on_error = step.get("on_error")
            if on_error is not None:
                if not isinstance(on_error, dict):
                    return jsonify({"ok": False, "error": f"actions[{idx}] on_error must be an action object or omitted"}), 400
                if not (on_error.get("type") or on_error.get("action_type")):
                    return jsonify({"ok": False, "error": f"actions[{idx}] on_error must have a type"}), 400
                if (on_error.get("type") or on_error.get("action_type")) not in {"webhook", "outbound_webhook", "swarm", "workflow", "delay", "wait_for_event", "set_variable", "get_variable", "delete_variable", "increment_variable", "call_rule", "transform", "parallel"}:
                    return jsonify({"ok": False, "error": f"actions[{idx}] on_error type must be webhook, outbound_webhook, swarm, or workflow"}), 400
            continue_on_error = step.get("continue_on_error")
            if continue_on_error is not None and not isinstance(continue_on_error, bool):
                return jsonify({"ok": False, "error": f"actions[{idx}] continue_on_error must be a boolean or omitted"}), 400
        # Derive legacy action_type/action_config from the first step for compatibility.
        first_step = actions[0]
        action_type = first_step.get("type") or first_step.get("action_type")
        action_config = first_step.get("config") or first_step.get("action_config") or {}
    elif action_type:
        action_config = data.get("action_config") or {}
        if action_type not in {"webhook", "outbound_webhook", "swarm", "workflow", "delay", "wait_for_event", "set_variable", "get_variable", "delete_variable", "increment_variable", "call_rule", "transform", "parallel"}:
            return jsonify({"ok": False, "error": "action_type must be webhook, outbound_webhook, swarm, or workflow"}), 400
        # Build an actions array from the legacy single action.
        actions = [{"type": action_type, "config": action_config}]
    else:
        return jsonify({"ok": False, "error": "Must provide actions array or legacy action_type"}), 400

    if schedule_type not in {"event", "cron"}:
        return jsonify({"ok": False, "error": "schedule_type must be event or cron"}), 400
    if schedule_type == "cron" and not cron_expression:
        return jsonify({"ok": False, "error": "cron_expression is required for scheduled rules"}), 400

    cooldown_minutes = data.get("cooldown_minutes", 0)
    try:
        cooldown_minutes = int(cooldown_minutes)
        if cooldown_minutes < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "cooldown_minutes must be a non-negative integer"}), 400

    next_run_at = None
    if schedule_type == "cron":
        next_run_at = _compute_next_run(cron_expression)
        if next_run_at is None:
            return jsonify({"ok": False, "error": "invalid cron_expression"}), 400

    rule_payload = {
        "name": name,
        "event_type": event_type,
        "condition": data.get("condition", {}),
        "action_type": action_type,
        "action_config": action_config,
        "actions": actions,
    }
    policy_result = _check_automation_policy(workspace_id, rule_payload)
    if not policy_result["allowed"]:
        if policy_result["effect"] == "require_approval":
            data["approval_required"] = True
            data["approver_message"] = "Policy requires approval: " + "; ".join(
                (v.get("message", "") if isinstance(v, dict) else getattr(v, "message", "")) for v in policy_result["violations"]
            )
        else:
            _log_automation_event(
                "automation_policy_blocked",
                ctx,
                metadata={"name": name, "effect": policy_result["effect"], "violations": policy_result["violations"]},
            )
            return jsonify({
                "ok": False,
                "error": "policy violation",
                "policy_effect": policy_result["effect"],
                "violations": policy_result["violations"],
            }), 403

    try:
        payload = {
            "name": name,
            "event_type": event_type,
            "condition": data.get("condition", {}),
            "action_type": action_type,
            "action_config": action_config,
            "actions": actions,
            "enabled": data.get("enabled", True),
            "approval_required": data.get("approval_required", False),
            "approver_message": data.get("approver_message", ""),
            "schedule_type": schedule_type,
            "cron_expression": cron_expression if schedule_type == "cron" else None,
            "next_run_at": next_run_at.isoformat() if next_run_at else None,
            "cooldown_minutes": cooldown_minutes,
            "workspace_id": workspace_id,
        }
        r = requests.post(
            f"{supabase_url}/rest/v1/automation_rules",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        created = r.json()
        created_id = created[0].get("id") if created else None
        _log_automation_event(
            "automation_created",
            ctx,
            rule_id=created_id,
            metadata={"name": name, "event_type": event_type, "rule_id": created_id},
        )
        return jsonify({"ok": True, "rule": created[0] if created else None}), 201
    except Exception as e:
        logger.warning("Failed to create automation rule: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/automations/<rule_id>", methods=["GET", "PATCH", "DELETE"])
@require_auth
@require_workspace_role("OPERATOR")
def automation_detail(rule_id: str):
    """Get, update, or delete a single automation rule."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    if request.method == "GET":
        r = requests.get(
            f"{supabase_url}/rest/v1/automation_rules",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={"id": f"eq.{rule_id}", "workspace_id": f"eq.{workspace_id}"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return jsonify({"ok": False, "error": "rule not found"}), 404
        return jsonify({"ok": True, "rule": rows[0]})

    if request.method == "DELETE":
        r = requests.delete(
            f"{supabase_url}/rest/v1/automation_rules",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={"id": f"eq.{rule_id}", "workspace_id": f"eq.{workspace_id}"},
            timeout=10,
        )
        r.raise_for_status()
        _log_automation_event("automation_deleted", ctx, rule_id=rule_id, metadata={"rule_id": rule_id})
        return jsonify({"ok": True})

    # PATCH
    data = request.json or {}
    updates: dict[str, Any] = {}
    for field in (
        "name",
        "event_type",
        "condition",
        "action_type",
        "action_config",
        "actions",
        "enabled",
        "approval_required",
        "approver_message",
        "schedule_type",
        "cron_expression",
        "cooldown_minutes",
    ):
        if field in data:
            updates[field] = data[field]

    # Validate cooldown_minutes when present
    if "cooldown_minutes" in updates:
        try:
            updates["cooldown_minutes"] = int(updates["cooldown_minutes"])
            if updates["cooldown_minutes"] < 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"ok": False, "error": "cooldown_minutes must be a non-negative integer"}), 400

    # Validate actions array when present (Phase 26 action chains)
    if "actions" in updates:
        actions = updates["actions"] or []
        if not isinstance(actions, list):
            return jsonify({"ok": False, "error": "actions must be an array"}), 400
        for idx, step in enumerate(actions):
            if not isinstance(step, dict):
                return jsonify({"ok": False, "error": f"actions[{idx}] must be an object"}), 400
            step_type = step.get("type") or step.get("action_type")
            if not step_type:
                return jsonify({"ok": False, "error": f"actions[{idx}] missing type"}), 400
            if step_type not in {"webhook", "outbound_webhook", "swarm", "workflow", "delay", "wait_for_event", "set_variable", "get_variable", "delete_variable", "increment_variable", "call_rule", "transform", "parallel"}:
                return jsonify({"ok": False, "error": f"actions[{idx}] type must be webhook, outbound_webhook, swarm, or workflow"}), 400
            run_if = step.get("run_if")
            if run_if is not None and not isinstance(run_if, dict):
                return jsonify({"ok": False, "error": f"actions[{idx}] run_if must be a condition object or omitted"}), 400
            loop_over = step.get("loop_over")
            if loop_over is not None and not isinstance(loop_over, str):
                return jsonify({"ok": False, "error": f"actions[{idx}] loop_over must be a string path/template or omitted"}), 400
            on_error = step.get("on_error")
            if on_error is not None:
                if not isinstance(on_error, dict):
                    return jsonify({"ok": False, "error": f"actions[{idx}] on_error must be an action object or omitted"}), 400
                if not (on_error.get("type") or on_error.get("action_type")):
                    return jsonify({"ok": False, "error": f"actions[{idx}] on_error must have a type"}), 400
                if (on_error.get("type") or on_error.get("action_type")) not in {"webhook", "outbound_webhook", "swarm", "workflow", "delay", "wait_for_event", "set_variable", "get_variable", "delete_variable", "increment_variable", "call_rule", "transform", "parallel"}:
                    return jsonify({"ok": False, "error": f"actions[{idx}] on_error type must be webhook, outbound_webhook, swarm, or workflow"}), 400
            continue_on_error = step.get("continue_on_error")
            if continue_on_error is not None and not isinstance(continue_on_error, bool):
                return jsonify({"ok": False, "error": f"actions[{idx}] continue_on_error must be a boolean or omitted"}), 400

    # Recompute next_run_at when switching to cron or changing the expression
    if ("schedule_type" in data or "cron_expression" in data) and updates.get("schedule_type") == "cron":
        cron_expr = data.get("cron_expression") or updates.get("cron_expression")
        if not cron_expr:
            return jsonify({"ok": False, "error": "cron_expression is required for scheduled rules"}), 400
        next_run_at = _compute_next_run(cron_expr)
        if next_run_at is None:
            return jsonify({"ok": False, "error": "invalid cron_expression"}), 400
        updates["next_run_at"] = next_run_at.isoformat()
    elif "schedule_type" in data and updates.get("schedule_type") != "cron":
        updates["cron_expression"] = None
        updates["next_run_at"] = None
    if not updates:
        return jsonify({"ok": False, "error": "no fields to update"}), 400

    # Phase 41: enforce automation policies on the proposed rule.
    rule_payload = {
        "name": updates.get("name", rows[0].get("name", "")),
        "event_type": updates.get("event_type", rows[0].get("event_type", "")),
        "condition": updates.get("condition", rows[0].get("condition", {})),
        "action_type": updates.get("action_type", rows[0].get("action_type", "")),
        "action_config": updates.get("action_config", rows[0].get("action_config", {})),
        "actions": updates.get("actions", rows[0].get("actions", [])),
    }
    policy_result = _check_automation_policy(workspace_id, rule_payload)
    if not policy_result["allowed"]:
        if policy_result["effect"] == "require_approval":
            updates["approval_required"] = True
            updates["approver_message"] = "Policy requires approval: " + "; ".join(
                (v.get("message", "") if isinstance(v, dict) else getattr(v, "message", "")) for v in policy_result["violations"]
            )
        else:
            _log_automation_event(
                "automation_policy_blocked",
                ctx,
                rule_id=rule_id,
                metadata={"rule_id": rule_id, "effect": policy_result["effect"], "violations": policy_result["violations"]},
            )
            return jsonify({
                "ok": False,
                "error": "policy violation",
                "policy_effect": policy_result["effect"],
                "violations": policy_result["violations"],
            }), 403

    # Phase 38: snapshot the current rule before mutating it.
    _create_rule_snapshot(supabase_url, service_key, rows[0], ctx)

    r = requests.patch(
        f"{supabase_url}/rest/v1/automation_rules",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json=updates,
        params={"id": f"eq.{rule_id}", "workspace_id": f"eq.{workspace_id}"},
        timeout=10,
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return jsonify({"ok": False, "error": "rule not found"}), 404
    _log_automation_event("automation_updated", ctx, rule_id=rule_id, metadata={"rule_id": rule_id, "fields": list(updates.keys())})
    return jsonify({"ok": True, "rule": rows[0]})




@app.route("/automations/<rule_id>/run", methods=["POST"])
@require_auth
@require_workspace_role("OPERATOR")
def automation_run_now(rule_id: str):
    """Manually execute a scheduled or event-driven automation rule."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    try:
        r = requests.get(
            f"{supabase_url}/rest/v1/automation_rules",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={"id": f"eq.{rule_id}", "workspace_id": f"eq.{workspace_id}"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json() or []
        if not rows:
            return jsonify({"ok": False, "error": "rule not found"}), 404
        rule = rows[0]

        # Phase 41: enforce runtime automation policies.
        rule_payload = {
            "name": rule.get("name", ""),
            "event_type": rule.get("event_type", ""),
            "condition": rule.get("condition", {}),
            "action_type": rule.get("action_type", ""),
            "action_config": rule.get("action_config", {}),
            "actions": rule.get("actions", []),
        }
        policy_result = _check_automation_policy(workspace_id, rule_payload)
        if not policy_result["allowed"]:
            _log_automation_event(
                "automation_policy_blocked",
                ctx,
                rule_id=rule_id,
                metadata={"rule_id": rule_id, "effect": policy_result["effect"], "violations": policy_result["violations"]},
            )
            return jsonify({
                "ok": False,
                "error": "policy violation",
                "policy_effect": policy_result["effect"],
                "violations": policy_result["violations"],
            }), 403

        # Phase 42: enforce automation budgets before execution.
        budget_result = check_automation_budget(str(workspace_id), rule_id=rule_id)
        if not budget_result.allowed:
            add_automation_execution(
                rule_id=rule_id,
                workspace_id=str(workspace_id),
                status="throttled",
                result={"reason": budget_result.blocks},
            )
            _log_automation_event(
                "automation_budget_blocked",
                ctx,
                rule_id=rule_id,
                metadata={"rule_id": rule_id, "blocks": budget_result.blocks},
            )
            return jsonify({
                "ok": False,
                "error": "budget exceeded",
                "blocks": budget_result.blocks,
            }), 429

        body = request.get_json(silent=True) or {}
        dry_run = bool(body.get("dry_run"))

        event = {
            "type": rule.get("event_type") or "system",
            "payload": {"manual": True, "rule_id": rule_id},
            "user_id": ctx.get("user_id"),
            "workspace_id": workspace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _log_automation_event("automation_run", ctx, rule_id=rule_id, metadata={"rule_id": rule_id, "dry_run": dry_run})
        result = _execute_action(rule, event, dry_run=dry_run)
        return jsonify({"ok": result.get("ok"), "dry_run": dry_run, "result": result})
    except Exception as e:
        logger.warning("Failed to run automation rule manually: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/automations/executions", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def automation_executions_list():
    """List execution logs across all automation rules in the workspace."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    try:
        limit = min(100, max(1, request.args.get("limit", 50, type=int)))
        offset = max(0, request.args.get("offset", 0, type=int))
        status = request.args.get("status")
        event_type = request.args.get("event_type")
        rule_id = request.args.get("rule_id")

        params: dict[str, Any] = {
            "workspace_id": f"eq.{workspace_id}",
            "order": "created_at.desc",
            "limit": limit,
            "offset": offset,
        }
        if status and status in ("triggered", "failed"):
            params["status"] = f"eq.{status}"
        if event_type:
            params["event_type"] = f"eq.{event_type}"
        if rule_id:
            params["rule_id"] = f"eq.{rule_id}"

        r = requests.get(
            f"{supabase_url}/rest/v1/automation_executions",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params=params,
            timeout=10,
        )
        r.raise_for_status()
        executions = r.json()

        # Enrich with rule names
        rule_names: dict[str, str] = {}
        if executions:
            rule_ids = {e.get("rule_id") for e in executions if e.get("rule_id")}
            if rule_ids:
                r2 = requests.get(
                    f"{supabase_url}/rest/v1/automation_rules",
                    headers={
                        "apikey": service_key,
                        "Authorization": f"Bearer {service_key}",
                    },
                    params={
                        "id": f"in.{','.join(rule_ids)}",
                        "select": "id,name",
                    },
                    timeout=10,
                )
                if r2.ok:
                    rule_names = {row["id"]: row["name"] for row in r2.json()}

        for e in executions:
            e["rule_name"] = rule_names.get(e.get("rule_id"))

        return jsonify({"ok": True, "executions": executions})
    except Exception as e:
        logger.warning("Failed to list automation executions: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/automations/executions/<execution_id>", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def automation_execution_detail(execution_id: str):
    """Get a single automation execution log with rule name."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    try:
        r = requests.get(
            f"{supabase_url}/rest/v1/automation_executions",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={
                "id": f"eq.{execution_id}",
                "workspace_id": f"eq.{workspace_id}",
                "limit": 1,
            },
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return jsonify({"ok": False, "error": "execution not found"}), 404

        execution = rows[0]

        # Enrich with rule name
        rule_id = execution.get("rule_id")
        if rule_id:
            r2 = requests.get(
                f"{supabase_url}/rest/v1/automation_rules",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
                params={
                    "id": f"eq.{rule_id}",
                    "select": "id,name",
                },
                timeout=10,
            )
            if r2.ok and r2.json():
                execution["rule_name"] = r2.json()[0].get("name")

        return jsonify({"ok": True, "execution": execution})
    except Exception as e:
        logger.warning("Failed to get automation execution: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/automations/<rule_id>/executions", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def automation_executions(rule_id: str):
    """List execution logs for an automation rule."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    try:
        r = requests.get(
            f"{supabase_url}/rest/v1/automation_executions",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={
                "rule_id": f"eq.{rule_id}",
                "workspace_id": f"eq.{workspace_id}",
                "order": "created_at.desc",
                "limit": 50,
            },
            timeout=10,
        )
        r.raise_for_status()
        return jsonify({"ok": True, "executions": r.json()})
    except Exception as e:
        logger.warning("Failed to list automation executions: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500








# ── Automation policy enforcement (Phase 41) ────────────────────────────────

@app.route("/automations/policies", methods=["GET", "POST"])
@require_auth
@require_workspace_role("ADMIN")
def automation_policies_index():
    """List or create automation policies for the current workspace."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    if request.method == "GET":
        policies = list_automation_policies(workspace_id, enabled_only=request.args.get("enabled", "true").lower() != "false")
        return jsonify({
            "ok": True,
            "policies": [
                {
                    "id": p.id,
                    "workspace_id": p.workspace_id,
                    "name": p.name,
                    "description": p.description,
                    "effect": p.effect,
                    "rules": p.rules,
                    "enabled": p.enabled,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in policies
            ],
        })

    data = request.json or {}
    name = (data.get("name") or "").strip()
    effect = (data.get("effect") or "").strip()
    rules = data.get("rules") or {}
    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    if effect not in {PolicyEffect.BLOCK, PolicyEffect.REQUIRE_APPROVAL}:
        return jsonify({"ok": False, "error": "effect must be 'block' or 'require_approval'"}), 400
    if not isinstance(rules, dict):
        return jsonify({"ok": False, "error": "rules must be an object"}), 400

    policy = create_automation_policy(
        workspace_id=workspace_id,
        name=name,
        effect=effect,
        rules=rules,
        description=data.get("description"),
        enabled=bool(data.get("enabled", True)),
    )
    _log_automation_event("automation_policy_created", ctx, metadata={"policy_id": policy.id, "name": policy.name})
    return jsonify({
        "ok": True,
        "policy": {
            "id": policy.id,
            "workspace_id": policy.workspace_id,
            "name": policy.name,
            "description": policy.description,
            "effect": policy.effect,
            "rules": policy.rules,
            "enabled": policy.enabled,
            "created_at": policy.created_at.isoformat() if policy.created_at else None,
            "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
        },
    }), 201


@app.route("/automations/policies/<policy_id>", methods=["GET", "PATCH", "DELETE"])
@require_auth
@require_workspace_role("ADMIN")
def automation_policy_detail(policy_id: str):
    """Get, update, or delete a single automation policy."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    policy = get_automation_policy(policy_id, workspace_id=workspace_id)
    if not policy:
        return jsonify({"ok": False, "error": "policy not found"}), 404

    if request.method == "GET":
        return jsonify({
            "ok": True,
            "policy": {
                "id": policy.id,
                "workspace_id": policy.workspace_id,
                "name": policy.name,
                "description": policy.description,
                "effect": policy.effect,
                "rules": policy.rules,
                "enabled": policy.enabled,
                "created_at": policy.created_at.isoformat() if policy.created_at else None,
                "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
            },
        })

    if request.method == "DELETE":
        delete_automation_policy(policy_id, workspace_id=workspace_id)
        _log_automation_event("automation_policy_deleted", ctx, metadata={"policy_id": policy_id})
        return jsonify({"ok": True})

    data = request.json or {}
    name = data.get("name")
    effect = data.get("effect")
    rules = data.get("rules")
    description = data.get("description")
    enabled = data.get("enabled")
    if effect is not None and effect not in {PolicyEffect.BLOCK, PolicyEffect.REQUIRE_APPROVAL}:
        return jsonify({"ok": False, "error": "effect must be 'block' or 'require_approval'"}), 400
    if rules is not None and not isinstance(rules, dict):
        return jsonify({"ok": False, "error": "rules must be an object"}), 400

    updated = update_automation_policy(
        policy,
        name=name.strip() if isinstance(name, str) else None,
        effect=effect,
        rules=rules,
        description=description,
        enabled=enabled if isinstance(enabled, bool) else None,
    )
    _log_automation_event("automation_policy_updated", ctx, metadata={"policy_id": policy_id})
    return jsonify({
        "ok": True,
        "policy": {
            "id": updated.id,
            "workspace_id": updated.workspace_id,
            "name": updated.name,
            "description": updated.description,
            "effect": updated.effect,
            "rules": updated.rules,
            "enabled": updated.enabled,
            "created_at": updated.created_at.isoformat() if updated.created_at else None,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None,
        },
    })


@app.route("/automations/policies/evaluate", methods=["POST"])
@require_auth
@require_workspace_role("OPERATOR")
def automation_policies_evaluate():
    """Evaluate a proposed rule against current workspace policies without persisting it.

    Body: { name, event_type, condition, actions, action_type, action_config }
    Returns: { allowed, effect, violations }
    """
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")
    data = request.json or {}

    rule_payload = {
        "name": data.get("name", ""),
        "event_type": data.get("event_type", ""),
        "condition": data.get("condition") or {},
        "actions": data.get("actions") or [],
        "action_type": data.get("action_type", ""),
        "action_config": data.get("action_config") or {},
    }

    result = evaluate_automation_policy(workspace_id, rule_payload)
    _log_automation_event(
        "automation_policy_evaluated",
        ctx,
        metadata={"allowed": result.allowed, "effect": result.effect, "violation_count": len(result.violations)},
    )
    return jsonify(result.to_dict())




def _serialize_budget(budget) -> dict[str, Any]:
    return {
        "id": budget.id,
        "workspace_id": budget.workspace_id,
        "name": budget.name,
        "rule_id": budget.rule_id,
        "period": budget.period,
        "limit_value": budget.limit_value,
        "action": budget.action,
        "enabled": budget.enabled,
        "created_at": budget.created_at.isoformat() if budget.created_at else None,
        "updated_at": budget.updated_at.isoformat() if budget.updated_at else None,
    }


@app.route("/automations/budgets", methods=["GET", "POST"])
@require_auth
@require_workspace_role("ADMIN")
def automation_budgets_index():
    """List or create automation budgets for the current workspace."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    if request.method == "GET":
        budgets = list_automation_budgets(workspace_id, enabled_only=request.args.get("enabled", "true").lower() != "false")
        return jsonify({"ok": True, "budgets": [_serialize_budget(b) for b in budgets]})

    data = request.json or {}
    name = (data.get("name") or "").strip()
    period = (data.get("period") or "").strip().lower()
    limit_value = data.get("limit_value")
    action = (data.get("action") or "block").strip().lower()
    rule_id = data.get("rule_id")

    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    if period not in {"hour", "day", "month", "total"}:
        return jsonify({"ok": False, "error": "period must be hour, day, month, or total"}), 400
    try:
        limit_value = int(limit_value)
        if limit_value < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "limit_value must be a non-negative integer"}), 400
    if action not in {"block", "warn"}:
        return jsonify({"ok": False, "error": "action must be 'block' or 'warn'"}), 400

    budget = create_automation_budget(
        workspace_id=workspace_id,
        name=name,
        period=period,
        limit_value=limit_value,
        action=action,
        rule_id=rule_id,
        enabled=bool(data.get("enabled", True)),
    )
    _log_automation_event("automation_budget_created", ctx, metadata={"budget_id": budget.id, "name": budget.name})
    return jsonify({"ok": True, "budget": _serialize_budget(budget)}), 201


@app.route("/automations/budgets/check", methods=["GET", "POST"])
@require_auth
@require_workspace_role("OPERATOR")
def automation_budgets_check():
    """Evaluate automation budgets for a workspace/rule without executing."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")
    data = request.get_json(silent=True) or {}
    rule_id = request.args.get("rule_id") or data.get("rule_id")
    result = check_automation_budget(str(workspace_id), rule_id=rule_id)
    return jsonify({"ok": True, **result.to_dict()})


def _check_automation_policy(workspace_id: str, rule: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a proposed automation rule against workspace policies.

    Returns a dict with keys: allowed (bool), effect (str), violations (list).
    """
    result = evaluate_automation_policy(str(workspace_id), rule)
    return {
        "allowed": result.allowed,
        "effect": result.effect,
        "violations": [v.to_dict() if hasattr(v, "to_dict") else v for v in result.violations],
    }


def _apply_policy_decision(
    data: dict[str, Any],
    policy_result: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None]:
    """Return (proceed, error_response) based on policy evaluation.

    If the rule is blocked, return an error response. If it requires approval,
    mutate data to set approval_required=True and return (True, None).
    """
    if policy_result["allowed"]:
        return True, None
    if policy_result["effect"] == "require_approval":
        data["approval_required"] = True
        data["approver_message"] = "Policy requires approval: " + "; ".join(
            (v.get("message", "") if isinstance(v, dict) else getattr(v, "message", "")) for v in policy_result["violations"]
        )
        return True, None
    return False, {
        "ok": False,
        "error": "policy violation",
        "policy_effect": policy_result["effect"],
        "violations": policy_result["violations"],
    }


@app.route("/automations/budgets/<budget_id>", methods=["GET", "PATCH", "DELETE"])
@require_auth
@require_workspace_role("ADMIN")
def automation_budget_detail(budget_id: str):
    """Get, update, or delete a single automation budget."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    budget = get_automation_budget(budget_id, workspace_id=workspace_id)
    if not budget:
        return jsonify({"ok": False, "error": "budget not found"}), 404

    if request.method == "GET":
        return jsonify({"ok": True, "budget": _serialize_budget(budget)})

    if request.method == "DELETE":
        delete_automation_budget(budget_id, workspace_id=workspace_id)
        _log_automation_event("automation_budget_deleted", ctx, metadata={"budget_id": budget_id})
        return jsonify({"ok": True})

    data = request.json or {}
    name = data.get("name")
    period = data.get("period")
    limit_value = data.get("limit_value")
    action = data.get("action")
    rule_id = data.get("rule_id")
    enabled = data.get("enabled")

    if period is not None and period not in {"hour", "day", "month", "total"}:
        return jsonify({"ok": False, "error": "period must be hour, day, month, or total"}), 400
    if limit_value is not None:
        try:
            limit_value = int(limit_value)
            if limit_value < 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "limit_value must be a non-negative integer"}), 400
    if action is not None and action not in {"block", "warn"}:
        return jsonify({"ok": False, "error": "action must be 'block' or 'warn'"}), 400

    updated = update_automation_budget(
        budget,
        name=name.strip() if isinstance(name, str) else None,
        period=period,
        limit_value=limit_value,
        action=action,
        rule_id=rule_id,
        enabled=enabled if isinstance(enabled, bool) else None,
    )
    _log_automation_event("automation_budget_updated", ctx, metadata={"budget_id": budget_id})
    return jsonify({"ok": True, "budget": _serialize_budget(updated)})


@app.route("/automations/test-condition", methods=["POST"])
@require_auth
def automation_test_condition():
    """Test an automation condition against a sample event payload.

    Accepts: { condition: dict, payload: dict }
    Returns: { ok: true, matches: bool }
    """
    data = request.json or {}
    condition = data.get("condition", {})
    payload = data.get("payload", {})
    try:
        matches = evaluate_condition(condition, payload)
        return jsonify({"ok": True, "matches": matches})
    except Exception as e:
        logger.warning("Failed to evaluate condition: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

# ── Automation governance & audit logs (Phase 40) ────────────────────────────

@app.route("/automations/audit", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def automation_audit_index():
    """Query automation governance audit logs for the current workspace.

    Query params:
      action  - filter by audit action (optional)
      module  - filter by module (default: automations)
      limit   - max rows to return (default 100, max 1000)
      offset  - pagination offset (default 0)
    """
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")
    action = request.args.get("action")
    module = request.args.get("module", "automations")
    limit = min(1000, max(1, request.args.get("limit", 100, type=int)))
    offset = max(0, request.args.get("offset", 0, type=int))

    result = get_governance().query_audit(
        workspace_id=workspace_id,
        action=action,
        module=module,
        limit=limit,
        offset=offset,
    )
    return jsonify(result)


@app.route("/automations/audit/export", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def automation_audit_export():
    """Export automation governance audit logs as a sanitized JSON payload."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")
    module = request.args.get("module", "automations")
    limit = min(10000, max(1, request.args.get("limit", 1000, type=int)))

    result = get_governance().query_audit(
        workspace_id=workspace_id,
        module=module,
        limit=limit,
        offset=0,
    )
    export = get_governance().export_audit(result.get("rows", []), format="json")
    return jsonify(export)


# ── Inbound webhook management (Phase 21) ───────────────────────────────────
# ── Automation import / export / blueprints (Phase 37) ─────────────────────

# Fields that are generated by Supabase and should not be re-imported.
_EXPORT_STRIPPED_FIELDS = frozenset({
    "id",
    "workspace_id",
    "created_at",
    "updated_at",
    "last_run_at",
    "next_run_at",
    "last_triggered_at",
})


def _strip_rule_for_export(rule: dict) -> dict:
    """Return a workspace-portable copy of an automation rule."""
    return {k: v for k, v in rule.items() if k not in _EXPORT_STRIPPED_FIELDS}


@app.route("/automations/export", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def automations_export():
    """Export automation rules as a portable JSON payload.

    Query params:
      rule_id  - optional, export a single rule instead of all workspace rules.
    """
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    try:
        rule_id = request.args.get("rule_id")
        params: dict[str, Any] = {"workspace_id": f"eq.{workspace_id}"}
        if rule_id:
            params["id"] = f"eq.{rule_id}"
        r = requests.get(
            f"{supabase_url}/rest/v1/automation_rules",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params=params,
            timeout=10,
        )
        r.raise_for_status()
        rules = r.json() or []
        _log_automation_event("automation_exported", ctx, metadata={"count": len(rules), "rule_id": request.args.get("rule_id")})
        return jsonify({
            "ok": True,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "aeon-automation-v1",
            "source_workspace_id": workspace_id,
            "count": len(rules),
            "rules": [_strip_rule_for_export(rule) for rule in rules],
        })
    except Exception as e:
        logger.warning("Failed to export automation rules: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/automations/import", methods=["POST"])
@require_auth
@require_workspace_role("OPERATOR")
def automations_import():
    """Import automation rules from a portable JSON payload.

    Accepts either a single rule object or an object with a `rules` array.
    Returns the list of created rules.
    """
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    data = request.json or {}
    if isinstance(data, dict) and "rules" in data:
        raw_rules = data.get("rules") or []
    elif isinstance(data, list):
        raw_rules = data
    elif isinstance(data, dict):
        raw_rules = [data]
    else:
        return jsonify({"ok": False, "error": "import body must be a rule object, a list of rules, or {rules: [...]}"}), 400

    if not raw_rules:
        return jsonify({"ok": False, "error": "no rules to import"}), 400

    created: list[dict] = []
    errors: list[dict] = []
    for idx, raw in enumerate(raw_rules):
        ok, err = _validate_automation_payload(raw)
        if not ok:
            errors.append({"index": idx, "error": err})
            continue

        actions = raw.get("actions") or []
        if actions:
            first = actions[0]
            action_type = first.get("type") or first.get("action_type")
            action_config = first.get("config") or first.get("action_config") or {}
        else:
            action_type = raw.get("action_type")
            action_config = raw.get("action_config") or {}
            actions = [{"type": action_type, "config": action_config}]

        schedule_type = (raw.get("schedule_type") or "event").strip()
        cron_expression = (raw.get("cron_expression") or "").strip()

        # Phase 41: enforce automation policies on imported rules.
        rule_payload = {
            "name": (raw.get("name") or "").strip(),
            "event_type": (raw.get("event_type") or "").strip(),
            "condition": raw.get("condition", {}),
            "action_type": action_type,
            "action_config": action_config,
            "actions": actions,
        }
        policy_result = _check_automation_policy(workspace_id, rule_payload)
        if not policy_result["allowed"]:
            if policy_result["effect"] == "require_approval":
                raw["approval_required"] = True
                raw["approver_message"] = "Policy requires approval: " + "; ".join(
                    (v.get("message", "") if isinstance(v, dict) else getattr(v, "message", "")) for v in policy_result["violations"]
                )
            else:
                errors.append({"index": idx, "error": "policy violation", "violations": policy_result["violations"]})
                continue

        next_run_at = None
        if schedule_type == "cron" and cron_expression:
            next_run_at = _compute_next_run(cron_expression)
            if next_run_at is None:
                errors.append({"index": idx, "error": "invalid cron_expression"})
                continue

        try:
            payload = {
                "name": (raw.get("name") or "").strip(),
                "event_type": (raw.get("event_type") or "").strip(),
                "condition": raw.get("condition", {}),
                "action_type": action_type,
                "action_config": action_config,
                "actions": actions,
                "enabled": raw.get("enabled", True),
                "approval_required": raw.get("approval_required", False),
                "approver_message": raw.get("approver_message", ""),
                "schedule_type": schedule_type,
                "cron_expression": cron_expression if schedule_type == "cron" else None,
                "next_run_at": next_run_at.isoformat() if next_run_at else None,
                "cooldown_minutes": int(raw.get("cooldown_minutes", 0)),
                "workspace_id": workspace_id,
            }
            r = requests.post(
                f"{supabase_url}/rest/v1/automation_rules",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
                json=payload,
                timeout=10,
            )
            r.raise_for_status()
            rows = r.json()
            created.append(rows[0] if rows else None)
        except Exception as e:
            logger.warning("Failed to import automation rule: %s", e)
            errors.append({"index": idx, "error": str(e)})

    _log_automation_event("automation_imported", ctx, metadata={"imported": len(created), "errors": len(errors)})
    return jsonify({
        "ok": len(errors) == 0,
        "imported": len(created),
        "rules": created,
        "errors": errors,
    }), 200 if not errors else 207


@app.route("/automations/blueprints", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def automations_blueprints():
    """Return a curated list of reusable automation rule templates."""
    blueprints = [
        {
            "id": "webhook-to-slack",
            "name": "Slack Alert on Workflow Failure",
            "description": "Posts a Slack message whenever a workflow fails in the workspace.",
            "event_type": "workflow_status",
            "condition": {"status": {"$eq": "failed"}},
            "actions": [
                {
                    "type": "outbound_webhook",
                    "config": {
                        "method": "POST",
                        "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
                        "headers": {"Content-Type": "application/json"},
                        "body": '{"text": "Workflow {{ event.payload.workflow_id }} failed: {{ event.payload.error }}"}',
                    },
                }
            ],
            "enabled": True,
            "schedule_type": "event",
            "cooldown_minutes": 0,
        },
        {
            "id": "swarm-on-inbound-webhook",
            "name": "Inbound Webhook -> Swarm",
            "description": "Trigger a swarm of agents when an inbound webhook is received.",
            "event_type": "inbound_webhook",
            "condition": {},
            "actions": [
                {
                    "type": "swarm",
                    "config": {
                        "prompt": "Summarize the incoming webhook payload and suggest next steps.",
                        "app_ids": ["default"],
                    },
                }
            ],
            "enabled": True,
            "schedule_type": "event",
            "cooldown_minutes": 0,
        },
        {
            "id": "escalation-chain",
            "name": "Escalation Chain",
            "description": "Run a workflow, then notify via webhook if it fails.",
            "event_type": "workflow_status",
            "condition": {"status": {"$eq": "failed"}},
            "actions": [
                {
                    "type": "workflow",
                    "config": {"workflow_id": "escalation-workflow", "initial_input": "Escalate {{ event.payload.workflow_id }}"},
                },
                {
                    "type": "webhook",
                    "config": {"url": "https://example.com/escalate"},
                },
            ],
            "enabled": True,
            "schedule_type": "event",
            "cooldown_minutes": 5,
        },
        {
            "id": "daily-report-cron",
            "name": "Daily Report (Cron)",
            "description": "Runs a workflow every weekday at 9 AM.",
            "event_type": "system",
            "condition": {},
            "actions": [
                {
                    "type": "workflow",
                    "config": {"workflow_id": "daily-report", "initial_input": "Generate daily report"},
                }
            ],
            "enabled": True,
            "schedule_type": "cron",
            "cron_expression": "0 9 * * 1-5",
            "cooldown_minutes": 0,
        },
    ]
    return jsonify({"ok": True, "blueprints": blueprints})



# ── Automation rule snapshots & rollback (Phase 38) ───────────────────────────

@app.route("/automations/<rule_id>/snapshots", methods=["GET", "POST"])
@require_auth
@require_workspace_role("VIEWER")
def automation_snapshots(rule_id: str):
    """List or create snapshots for an automation rule."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    # Verify the rule exists and belongs to the workspace
    try:
        r = requests.get(
            f"{supabase_url}/rest/v1/automation_rules",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={"id": f"eq.{rule_id}", "workspace_id": f"eq.{workspace_id}"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return jsonify({"ok": False, "error": "rule not found"}), 404
        rule = rows[0]
    except Exception as e:
        logger.warning("Failed to fetch automation rule for snapshots: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

    if request.method == "POST":
        snapshot = _create_rule_snapshot(supabase_url, service_key, rule, ctx)
        if snapshot is None:
            return jsonify({"ok": False, "error": "failed to create snapshot"}), 500
        _log_automation_event("automation_snapshot_created", ctx, rule_id=rule_id, metadata={"rule_id": rule_id, "snapshot_id": snapshot.get("id")})
        return jsonify({"ok": True, "snapshot": snapshot}), 201

    # GET
    try:
        r = requests.get(
            f"{supabase_url}/rest/v1/automation_rule_snapshots",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={
                "rule_id": f"eq.{rule_id}",
                "workspace_id": f"eq.{workspace_id}",
                "order": "created_at.desc",
                "limit": 100,
            },
            timeout=10,
        )
        r.raise_for_status()
        return jsonify({"ok": True, "snapshots": r.json()})
    except Exception as e:
        logger.warning("Failed to list automation rule snapshots: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/automations/<rule_id>/rollback/<snapshot_id>", methods=["POST"])
@require_auth
@require_workspace_role("OPERATOR")
def automation_rollback(rule_id: str, snapshot_id: str):
    """Restore an automation rule from a previous snapshot.

    The current rule state is snapshotted first, then the chosen snapshot is
    applied back to the rule.
    """
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    # Fetch the current rule
    try:
        r = requests.get(
            f"{supabase_url}/rest/v1/automation_rules",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={"id": f"eq.{rule_id}", "workspace_id": f"eq.{workspace_id}"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return jsonify({"ok": False, "error": "rule not found"}), 404
        rule = rows[0]
    except Exception as e:
        logger.warning("Failed to fetch automation rule for rollback: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

    # Fetch the snapshot
    try:
        r = requests.get(
            f"{supabase_url}/rest/v1/automation_rule_snapshots",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={
                "id": f"eq.{snapshot_id}",
                "rule_id": f"eq.{rule_id}",
                "workspace_id": f"eq.{workspace_id}",
            },
            timeout=10,
        )
        r.raise_for_status()
        snapshots = r.json()
        if not snapshots:
            return jsonify({"ok": False, "error": "snapshot not found"}), 404
        snapshot = snapshots[0]
    except Exception as e:
        logger.warning("Failed to fetch automation rule snapshot: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

    # Snapshot current state before rolling back
    _create_rule_snapshot(supabase_url, service_key, rule, ctx)

    # Restore snapshot fields
    restore_fields = (
        "name",
        "event_type",
        "condition",
        "action_type",
        "action_config",
        "actions",
        "enabled",
        "approval_required",
        "approver_message",
        "schedule_type",
        "cron_expression",
        "cooldown_minutes",
    )
    updates = {field: snapshot.get(field) for field in restore_fields}

    # Preserve next_run_at based on restored cron expression
    if updates.get("schedule_type") == "cron" and updates.get("cron_expression"):
        next_run_at = _compute_next_run(updates["cron_expression"])
        if next_run_at:
            updates["next_run_at"] = next_run_at.isoformat()
        else:
            updates["next_run_at"] = None
    else:
        updates["next_run_at"] = None

    try:
        r = requests.patch(
            f"{supabase_url}/rest/v1/automation_rules",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=updates,
            params={"id": f"eq.{rule_id}", "workspace_id": f"eq.{workspace_id}"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return jsonify({"ok": False, "error": "rule not found"}), 404
        _log_automation_event("automation_rollback", ctx, rule_id=rule_id, metadata={"rule_id": rule_id, "snapshot_id": snapshot_id})
        return jsonify({"ok": True, "rule": rows[0]})
    except Exception as e:
        logger.warning("Failed to rollback automation rule: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

def _generate_inbound_token() -> str:
    import secrets
    return secrets.token_urlsafe(32)


@app.route("/inbound-webhooks", methods=["GET", "POST"])
@require_auth
@require_workspace_role("OPERATOR")
def inbound_webhooks_index():
    """List or create inbound webhooks for the current workspace."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    if request.method == "GET":
        try:
            r = requests.get(
                f"{supabase_url}/rest/v1/inbound_webhooks",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
                params={
                    "workspace_id": f"eq.{workspace_id}",
                    "order": "created_at.desc",
                },
                timeout=10,
            )
            r.raise_for_status()
            return jsonify({"ok": True, "webhooks": r.json()})
        except Exception as e:
            logger.warning("Failed to list inbound webhooks: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500

    # POST
    data = request.json or {}
    name = (data.get("name") or "Inbound Webhook").strip()
    try:
        payload = {
            "workspace_id": workspace_id,
            "name": name,
            "token": _generate_inbound_token(),
        }
        r = requests.post(
            f"{supabase_url}/rest/v1/inbound_webhooks",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        created = r.json()
        return jsonify({"ok": True, "webhook": created[0] if created else None}), 201
    except Exception as e:
        logger.warning("Failed to create inbound webhook: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/inbound-webhooks/<webhook_id>", methods=["DELETE"])
@require_auth
@require_workspace_role("OPERATOR")
def inbound_webhook_detail(webhook_id: str):
    """Delete an inbound webhook."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    try:
        r = requests.delete(
            f"{supabase_url}/rest/v1/inbound_webhooks",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={"id": f"eq.{webhook_id}", "workspace_id": f"eq.{workspace_id}"},
            timeout=10,
        )
        r.raise_for_status()
        return jsonify({"ok": True})
    except Exception as e:
        logger.warning("Failed to delete inbound webhook: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500
# ---- Approval endpoints (Phase 19: HITL) ---------------------------------
@app.route("/approvals", methods=["GET", "POST"])
@require_auth
@require_workspace_role("VIEWER")
def approvals_index():
    """List pending approval requests for the current workspace or create one."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    if request.method == "GET":
        status = request.args.get("status", "pending")
        try:
            r = requests.get(
                f"{supabase_url}/rest/v1/approval_requests",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
                params={
                    "workspace_id": f"eq.{workspace_id}",
                    "status": f"eq.{status}" if status != "all" else None,
                    "order": "created_at.desc",
                    "limit": 100,
                },
                timeout=10,
            )
            r.raise_for_status()
            return jsonify({"ok": True, "approvals": r.json()})
        except Exception as e:
            logger.warning("Failed to list approval requests: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500

    # POST - manual creation of an approval request
    data = request.json or {}
    try:
        payload = {
            "rule_id": data.get("rule_id"),
            "event_type": data.get("event_type", "manual"),
            "event_payload": json.dumps(data.get("event_payload") or {}),
            "action_type": data.get("action_type", "webhook"),
            "action_config": json.dumps(data.get("action_config") or {}),
            "status": "pending",
            "workspace_id": workspace_id,
            "user_id": ctx.get("user_id"),
            "requested_by": ctx.get("user_id"),
        }
        r = requests.post(
            f"{supabase_url}/rest/v1/approval_requests",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        created = r.json()
        return jsonify({"ok": True, "approval": created[0] if created else None}), 201
    except Exception as e:
        logger.warning("Failed to create approval request: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/approvals/<approval_id>", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def approval_detail(approval_id: str):
    """Get a single approval request."""
    ctx = _governance_context()
    workspace_id = ctx.get("workspace_id")

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    try:
        r = requests.get(
            f"{supabase_url}/rest/v1/approval_requests",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={
                "id": f"eq.{approval_id}",
                "workspace_id": f"eq.{workspace_id}",
            },
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json() or []
        if not rows:
            return jsonify({"ok": False, "error": "approval not found"}), 404
        return jsonify({"ok": True, "approval": rows[0]})
    except Exception as e:
        logger.warning("Failed to get approval request: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/approvals/<approval_id>/resolve", methods=["POST"])
@require_auth
@require_workspace_role("OPERATOR")
def approval_resolve(approval_id: str):
    """Approve or reject a pending approval request."""
    ctx = _governance_context()
    data = request.json or {}
    decision = (data.get("decision") or "").strip().lower()
    reason = data.get("reason")
    resolver_user_id = ctx.get("user_id")

    if not decision:
        return jsonify({"ok": False, "error": "decision is required"}), 400

    result = resolve_approval(approval_id, decision, resolver_user_id, reason)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)



# ── Inbound webhooks (Phase 21) ─────────────────────────────────────────────
@app.route("/inbound/<token>", methods=["POST"])
def inbound_webhook(token: str):
    """Receive an inbound webhook from a third-party service and trigger AEON automations."""
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    try:
        import requests

        r = requests.get(
            f"{supabase_url}/rest/v1/inbound_webhooks",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={"token": f"eq.{token}", "select": "id,name,workspace_id"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json() or []
        if not rows:
            return jsonify({"ok": False, "error": "unknown webhook token"}), 404
        hook = rows[0]

        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            body = {}

        payload = {
            "webhook_id": hook.get("id"),
            "webhook_name": hook.get("name"),
            "data": body,
        }
        log_activity(
            "inbound_webhook",
            payload,
            user_id=None,
            workspace_id=hook.get("workspace_id"),
        )
        return jsonify({"ok": True, "message": "event accepted"}), 202
    except Exception as e:
        logger.warning("Inbound webhook failed for token %s: %s", token, e)
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Slack interactive approvals (Phase 21) ──────────────────────────────────
def _verify_slack_signature(raw_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify the HMAC-SHA256 signature Slack sends with interactive payloads."""
    secret = os.environ.get("SLACK_SIGNING_SECRET")
    if not secret:
        return False
    import hashlib
    import hmac
    sig_prefix = "v0="
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=f"v0:{timestamp}:{raw_body.decode('utf-8')}".encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"{sig_prefix}{expected}", signature)


@app.route("/slack/interactions", methods=["POST"])
def slack_interactions():
    """Handle Slack interactive component callbacks (Block Kit button clicks)."""
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    raw_body = request.get_data()

    if not _verify_slack_signature(raw_body, timestamp, signature):
        return jsonify({"ok": False, "error": "invalid slack signature"}), 403

    encoded = request.form.get("payload", "")
    if not encoded:
        return jsonify({"ok": False, "error": "missing payload"}), 400

    try:
        payload = json.loads(encoded)
    except Exception as e:
        logger.warning("Failed to parse Slack payload: %s", e)
        return jsonify({"ok": False, "error": "invalid payload"}), 400

    action = payload.get("actions", [{}])[0]
    action_value = action.get("value")
    if not action_value:
        return jsonify({"ok": False, "error": "no action value"}), 400

    try:
        value = json.loads(action_value)
    except Exception as e:
        logger.warning("Failed to parse Slack action value: %s", e)
        return jsonify({"ok": False, "error": "invalid action value"}), 400

    approval_id = value.get("approval_id")
    decision = value.get("decision")
    if not approval_id or not decision:
        return jsonify({"ok": False, "error": "missing approval_id or decision"}), 400

    slack_user = (payload.get("user") or {}).get("id") or "slack"
    result = resolve_approval(str(approval_id), str(decision), str(slack_user), "Resolved via Slack")
    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error", "unknown")}), 400

    return jsonify({
        "ok": True,
        "text": f"Approval {decision}.",
    }), 200
# ── Graceful shutdown ────────────────────────────────────────────────────────
def _shutdown():
    logger.info("Shutting down AEON kernel...")
    try:
        job_queue.shutdown()
    except Exception as e:
        logger.warning("Job queue shutdown error: %s", e)
    try:
        get_governance().shutdown()
    except Exception as e:
        logger.warning("Governance shutdown error: %s", e)


import atexit

atexit.register(_shutdown)


# ── Main entrypoint ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    env_report = validate_environment()
    logger.info("AEON Python Kernel starting on %s:%d", HOST, PORT)
    logger.info("Environment readiness: %s", env_report["ok"])
    for warning in env_report.get("warnings", []):
        logger.info("Env warning: %s", warning)
    for missing in env_report.get("missing", []):
        logger.error("Missing required env: %s", missing)
    app.run(host=HOST, port=PORT, threaded=True)
