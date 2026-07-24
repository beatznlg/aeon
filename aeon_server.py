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

import os
import sys
import re
import json
import time
import queue
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from functools import wraps
from flask import Flask, request, jsonify, g, Response

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, os.environ.get("AEON_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("aeon_server")

from aeon import ReflectiveAgent
from aeon_os import AeonOS
import aeon_workflows  # patches AeonOS with workflow/swarm helpers
from aeon_integrations import IntegrationManager, IntegrationConfig, WebhookDelivery
from aeon_usage import UsageMeter, BillingCalculator, HealthCollector
from aeon_governance import GovernanceManager, get_governance

app = Flask(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
HOST = os.environ.get("AEON_PYTHON_HOST", "0.0.0.0")
PORT = int(os.environ.get("AEON_PYTHON_PORT", "5000"))
AEON_ROOT = Path(os.environ.get("AEON_ROOT", "./aeon_state/server"))
AEON_ROOT.mkdir(parents=True, exist_ok=True)


# ── Environment validation ───────────────────────────────────────────────────
def validate_environment() -> Dict[str, Any]:
    """Check environment variables and return a readiness report."""
    checks = {
        "SUPABASE_URL": "optional",
        "SUPABASE_ANON_KEY": "optional",
        "SUPABASE_SERVICE_ROLE_KEY": "optional",
        "HUGGINGFACE_TOKEN": "optional",
        "OPENAI_API_KEY": "optional",
        "ANTHROPIC_API_KEY": "optional",
    }
    report: Dict[str, Any] = {"ok": True, "missing": [], "warnings": []}
    for name, kind in checks.items():
        if not os.environ.get(name):
            if kind == "required":
                report["ok"] = False
                report["missing"].append(name)
            else:
                report["warnings"].append(f"{name} not set")
    return report


# ── Simple in-memory rate limiter ───────────────────────────────────────────
class RateLimiter:
    """Sliding-window rate limiter keyed by client IP or user header."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._buckets: Dict[str, list] = {}

    def is_allowed(self, key: str) -> bool:
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
        self._counters: Dict[str, Dict[tuple, int]] = {}
        self._histograms: Dict[str, Dict[tuple, Dict[str, Any]]] = {}
        self._gauges: Dict[str, float] = {}

    def inc(self, name: str, amount: int = 1, labels: Optional[Dict[str, str]] = None):
        label_key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._counters.setdefault(name, {})[label_key] = self._counters.get(name, {}).get(label_key, 0) + amount

    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        label_key = tuple(sorted((labels or {}).items()))
        with self._lock:
            hist = self._histograms.setdefault(name, {})
            if label_key not in hist:
                hist[label_key] = {
                    "buckets": {b: 0 for b in self.BUCKETS},
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

    def _format_labels(self, labels: Dict[str, str]) -> str:
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

    def snapshot_summary(self) -> Dict[str, Any]:
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
_agents: Dict[str, ReflectiveAgent] = {}


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


# ── In-memory async job queue ───────────────────────────────────────────────
class JobQueue:
    """Tiny in-memory background task queue backed by a daemon worker thread."""

    def __init__(self, workers: int = 2):
        self._queue: queue.Queue[Optional[tuple]] = queue.Queue()
        self._results: Dict[str, Any] = {}
        self._threads = []
        for _ in range(workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
            self._threads.append(t)

    def _worker_loop(self):
        while True:
            task = self._queue.get()
            if task is None:
                self._queue.task_done()
                break
            job_id, app_id, action, payload = task
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
                self._results[job_id] = {
                    "status": "done",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "result": result,
                }
            except Exception as e:
                self._results[job_id] = {
                    "status": "error",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(e),
                }
            finally:
                self._queue.task_done()

    def submit(self, app_id: str, action: str, payload: Dict[str, Any]) -> str:
        job_id = f"{app_id}-{action}-{int(time.time() * 1000)}-{id(payload)}"
        self._results[job_id] = {"status": "queued", "submitted_at": datetime.now(timezone.utc).isoformat()}
        self._queue.put((job_id, app_id, action, payload))
        return job_id

    def status(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._results.get(job_id)

    def shutdown(self):
        for _ in self._threads:
            self._queue.put(None)
        for t in self._threads:
            t.join(timeout=2)


job_queue = JobQueue(workers=2)


# ── Flask routes ───────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "backend": "aeon_python_kernel"})


@app.route("/live", methods=["GET"])
def live():
    """Liveness probe: returns 200 as long as the server process is responsive."""
    return jsonify({"ok": True, "status": "alive"}), 200


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
        "queue_size": job_queue._queue.qsize(),
    }
    status = 200 if env_report["ok"] else 503
    return jsonify(readiness), status


def _governance_context() -> Dict[str, Any]:
    """Extract optional governance identifiers from the request body/headers."""
    data = request.json or {}
    return {
        "user_id": data.get("user_id") or request.headers.get("X-User-Id"),
        "workspace_id": data.get("workspace_id") or request.headers.get("X-Workspace-Id"),
        "email": data.get("email") or request.headers.get("X-User-Email"),
    }


@app.route("/chat", methods=["POST"])
def chat():
    """Global chat endpoint. Uses the 'default' agent context."""
    data = request.json or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "missing query"}), 400
    ctx = _governance_context()
    try:
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
            metadata={"backend": result.get("backend", "unknown")},
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
_aeon_os_instance: Optional[AeonOS] = None


def get_os() -> AeonOS:
    """Return a singleton AeonOS orchestrator (loads workflow/swarm helpers)."""
    global _aeon_os_instance
    with _aeon_os_lock:
        if _aeon_os_instance is None:
            _aeon_os_instance = AeonOS(root=AEON_ROOT)
        return _aeon_os_instance


# ── Workflow endpoints ─────────────────────────────────────────────────────
@app.route("/workflows", methods=["GET", "POST"])
def workflows_index():
    """List all workflows or create a new one."""
    os_inst = get_os()
    if request.method == "GET":
        return jsonify({"ok": True, "workflows": os_inst.list_workflows()})

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
def workflow_detail(workflow_id: str):
    os_inst = get_os()
    if request.method == "GET":
        wf = os_inst.get_workflow(workflow_id)
        if wf is None:
            return jsonify({"ok": False, "error": "workflow not found"}), 404
        return jsonify({"ok": True, "workflow": wf.to_dict()})

    # DELETE
    if os_inst.delete_workflow(workflow_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "workflow not found"}), 404


@app.route("/workflows/<workflow_id>/run", methods=["POST"])
def workflow_run(workflow_id: str):
    data = request.json or {}
    initial_input = (data.get("initial_input") or "").strip()
    ctx = _governance_context()
    try:
        result = get_os().run_workflow(workflow_id, initial_input)
        metrics_collector.inc("aeon_workflow_runs_total", labels={"workflow_id": workflow_id, "ok": str(result.get("ok", True))})
        get_governance_manager().log_audit(
            action="WORKFLOW_RUN",
            module="workflow",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"workflow_id": workflow_id, "ok": result.get("ok", True)},
        )
        return jsonify(result)
    except Exception as e:
        get_governance_manager().log_audit(
            action="WORKFLOW_RUN_ERROR",
            module="workflow",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"workflow_id": workflow_id, "error": str(e)},
        )
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Swarm endpoints ────────────────────────────────────────────────────────
@app.route("/swarm/run", methods=["POST"])
def swarm_run():
    data = request.json or {}
    app_ids = data.get("app_ids") or []
    prompt = (data.get("prompt") or "").strip()
    ctx = _governance_context()
    if not app_ids or not prompt:
        return jsonify({"ok": False, "error": "app_ids and prompt required"}), 400
    try:
        result = get_os().run_swarm(app_ids, prompt)
        metrics_collector.inc("aeon_swarm_runs_total", labels={"ok": str(result.get("ok", True))})
        get_governance_manager().log_audit(
            action="SWARM_RUN",
            module="swarm",
            user_id=ctx.get("user_id"),
            workspace_id=ctx.get("workspace_id"),
            email=ctx.get("email"),
            metadata={"app_ids": app_ids, "ok": result.get("ok", True)},
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


# ── Usage / Billing / Observability endpoints ────────────────────────────
_usage_meter: Optional[UsageMeter] = None
_billing_calculator: Optional[BillingCalculator] = None
_health_collector: Optional[HealthCollector] = None


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
def governance_audit():
    workspace_id = request.args.get("workspace_id")
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
def governance_compliance():
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
def governance_retention():
    if request.method == "GET":
        workspace_id = request.args.get("workspace_id")
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
_integration_manager: Optional[IntegrationManager] = None


def get_integration_manager() -> IntegrationManager:
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = IntegrationManager(AEON_ROOT)
    return _integration_manager


@app.route("/integrations", methods=["GET", "POST"])
def integrations_index():
    mgr = get_integration_manager()
    if request.method == "GET":
        return jsonify({"ok": True, "integrations": mgr.list_integrations(mask=True)})

    data = request.json or {}
    integration_id = data.get("id")
    cfg = mgr.save(data, integration_id=integration_id)
    return jsonify({"ok": True, "integration": cfg.to_dict(mask=True)})


@app.route("/integrations/<integration_id>", methods=["GET", "DELETE"])
def integration_detail(integration_id: str):
    mgr = get_integration_manager()
    if request.method == "GET":
        cfg = mgr.get(integration_id)
        if cfg is None:
            return jsonify({"ok": False, "error": "integration not found"}), 404
        return jsonify({"ok": True, "integration": cfg.to_dict(mask=True)})

    if mgr.delete(integration_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "integration not found"}), 404


@app.route("/integrations/<integration_id>/run", methods=["POST"])
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
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/proxy", methods=["POST"])
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


@app.route("/webhooks/deliveries", methods=["GET"])
def webhook_deliveries():
    limit = min(100, max(1, request.args.get("limit", 100, type=int)))
    return jsonify({"ok": True, "deliveries": get_integration_manager().list_deliveries(limit=limit)})


# ── Usage, Billing & Observability endpoints ───────────────────────────────
@app.route("/usage", methods=["POST"])
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
def usage_summary():
    workspace_id = request.args.get("workspace_id")
    days = min(365, max(1, request.args.get("days", 30, type=int)))
    summary = get_usage_meter().get_summary(workspace_id=workspace_id, days=days)
    return jsonify({"ok": True, "summary": summary})


@app.route("/billing/<workspace_id>", methods=["GET"])
def billing_status(workspace_id: str):
    days = min(365, max(1, request.args.get("days", 30, type=int)))
    return jsonify({"ok": True, "billing": get_billing_calculator().workspace_status(workspace_id, days=days)})


@app.route("/billing/<workspace_id>/plan", methods=["POST"])
def billing_set_plan(workspace_id: str):
    data = request.json or {}
    plan_id = data.get("plan_id", "free")
    credits = float(data.get("credits", 0))
    ctx = _governance_context()
    get_billing_calculator().set_plan(workspace_id, plan_id, credits)
    get_governance_manager().log_audit(
        action="BILLING_PLAN_SET",
        module="billing",
        user_id=ctx.get("user_id"),
        workspace_id=workspace_id,
        email=ctx.get("email"),
        metadata={"plan_id": plan_id, "credits": credits},
    )
    return jsonify({"ok": True})


@app.route("/billing/<workspace_id>/credits", methods=["POST"])
def billing_add_credits(workspace_id: str):
    data = request.json or {}
    amount = float(data.get("amount", 0))
    ctx = _governance_context()
    get_billing_calculator().add_credits(workspace_id, amount)
    get_governance_manager().log_audit(
        action="BILLING_CREDITS_ADDED",
        module="billing",
        user_id=ctx.get("user_id"),
        workspace_id=workspace_id,
        email=ctx.get("email"),
        metadata={"amount": amount},
    )
    return jsonify({"ok": True})


@app.route("/health/detailed", methods=["GET"])
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
            queue_size=job_queue._queue.qsize(),
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
    metrics_collector.set_gauge("aeon_job_queue_size", job_queue._queue.qsize())

    body = metrics_collector.render()
    return Response(body, mimetype="text/plain; version=0.0.4; charset=utf-8")


# ── Prompt Registry & RAG endpoints ──────────────────────────────────────────
_prompt_registry: Optional[Any] = None
_kb_manager: Optional[Any] = None
_rag_orchestrator: Optional[Any] = None


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
def knowledge_base_stats(kb_id: str):
    try:
        stats = get_kb_manager().stats(kb_id)
        return jsonify({"ok": True, "stats": stats})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/rag/chat", methods=["POST"])
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
