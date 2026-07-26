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
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, Response, g, jsonify, request

from aeon_cache import get_cache

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
from aeon_governance import GovernanceManager, get_governance
from aeon_integrations import IntegrationManager, WebhookDelivery, get_integration_catalog
from aeon_llm import get_llm_provider, list_providers, set_active_provider
from aeon_llm import test_provider as _test_llm_provider
from aeon_automations import resolve_approval, start_scheduler, _compute_next_run
from aeon_notify import broadcast_event
from aeon_notify import log_activity
from aeon_notify import notify as _notify
from aeon_os import AeonOS
from aeon_stripe import get_stripe_client, init_stripe
from aeon_usage import BillingCalculator, HealthCollector, UsageMeter

app = Flask(__name__)

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
rate_limiter = RateLimiter(max_requests=_rate_limit_max, window_seconds=60)


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


# Initialize Stripe at startup
init_stripe(AEON_ROOT)


# ── Auth routes ────────────────────────────────────────────────────────────
@app.route("/auth/login", methods=["POST"])
def auth_login():
    """Issue a short-lived JWT access token for a valid user."""
    from werkzeug.security import check_password_hash

    from aeon_auth import _FallbackAdmin, create_access_token
    from aeon_db import get_db

    data = request.json or {}
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
            metadata={"backend": result.get("backend", "unknown"), "provider_override": provider_override},
        )
        return jsonify({"ok": True, "data": result, "backend": result.get("backend", "unknown")})
    except Exception as e:
        get_governance_manager().log_audit(
            action="WORKSPACE_CHAT_ERROR",
            module="workspace",
            user_id=user_id,
            workspace_id=workspace_id,
            email=ctx.get("email"),
            metadata={"error": str(e)},
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
            metadata={"backend": result.get("backend", "unknown"), "provider_override": provider_override},
        )
        return jsonify({"ok": True, "data": result, "backend": result.get("backend", "unknown")})
    except Exception as e:
        get_governance_manager().log_audit(
            action="CHAT_ERROR",
            module="global",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"error": str(e)},
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
            metadata={"backend": result.get("backend", "unknown")},
        )
        return jsonify({"ok": True, "data": result, "backend": result.get("backend", "unknown")})
    except Exception as e:
        get_governance_manager().log_audit(
            action="APP_CHAT_ERROR",
            module=app_id,
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"error": str(e)},
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
    action_type = (data.get("action_type") or "").strip()
    schedule_type = (data.get("schedule_type") or "event").strip()
    cron_expression = (data.get("cron_expression") or "").strip()
    if not name or not event_type or not action_type:
        return jsonify({"ok": False, "error": "name, event_type, and action_type are required"}), 400
    if action_type not in {"webhook", "swarm", "workflow"}:
        return jsonify({"ok": False, "error": "action_type must be webhook, swarm, or workflow"}), 400
    if schedule_type not in {"event", "cron"}:
        return jsonify({"ok": False, "error": "schedule_type must be event or cron"}), 400
    if schedule_type == "cron" and not cron_expression:
        return jsonify({"ok": False, "error": "cron_expression is required for scheduled rules"}), 400

    next_run_at = None
    if schedule_type == "cron":
        next_run_at = _compute_next_run(cron_expression)
        if next_run_at is None:
            return jsonify({"ok": False, "error": "invalid cron_expression"}), 400

    try:
        payload = {
            "name": name,
            "event_type": event_type,
            "condition": data.get("condition", {}),
            "action_type": action_type,
            "action_config": data.get("action_config", {}),
            "enabled": data.get("enabled", True),
            "approval_required": data.get("approval_required", False),
            "approver_message": data.get("approver_message", ""),
            "schedule_type": schedule_type,
            "cron_expression": cron_expression if schedule_type == "cron" else None,
            "next_run_at": next_run_at.isoformat() if next_run_at else None,
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
        "enabled",
        "approval_required",
        "approver_message",
        "schedule_type",
        "cron_expression",
    ):
        if field in data:
            updates[field] = data[field]

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

        from aeon_automations import execute_action_by_type
        event = {
            "type": rule.get("event_type") or "system",
            "payload": {"manual": True, "rule_id": rule_id},
            "user_id": ctx.get("user_id"),
            "workspace_id": workspace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        result = execute_action_by_type(rule.get("action_type"), rule.get("action_config") or {}, event)
        return jsonify({"ok": result.get("ok"), "result": result})
    except Exception as e:
        logger.warning("Failed to run automation rule manually: %s", e)
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






# ── Inbound webhook management (Phase 21) ───────────────────────────────────
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
    import hmac
    import hashlib
    sig_prefix = "v0="
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=f"v0:{timestamp}:{raw_body.decode('utf-8')}".encode("utf-8"),
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
