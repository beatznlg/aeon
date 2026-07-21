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
import json
import time
import queue
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from flask import Flask, request, jsonify

from aeon import ReflectiveAgent
from aeon_os import AeonOS
import aeon_workflows  # patches AeonOS with workflow/swarm helpers
from aeon_integrations import IntegrationManager, IntegrationConfig, WebhookDelivery
from aeon_usage import UsageMeter, BillingCalculator, HealthCollector

app = Flask(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
HOST = os.environ.get("AEON_PYTHON_HOST", "0.0.0.0")
PORT = int(os.environ.get("AEON_PYTHON_PORT", "5000"))
AEON_ROOT = Path(os.environ.get("AEON_ROOT", "./aeon_state/server"))
AEON_ROOT.mkdir(parents=True, exist_ok=True)

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


@app.route("/chat", methods=["POST"])
def chat():
    """Global chat endpoint. Uses the 'default' agent context."""
    data = request.json or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "missing query"}), 400
    try:
        agent = get_agent("default")
        result = agent.act(query)
        return jsonify({"ok": True, "data": result, "backend": result.get("backend", "unknown")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/apps/<app_id>/chat", methods=["POST"])
def app_chat(app_id: str):
    """Module-aware chat endpoint."""
    data = request.json or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "missing query"}), 400
    try:
        agent = get_agent(app_id)
        # Inject module context into the query so the agent is aware of the vertical
        system_hint = data.get("system")
        if system_hint:
            query = f"[{app_id} module context] {system_hint}\n\n{query}"
        result = agent.act(query)
        return jsonify({"ok": True, "data": result, "backend": result.get("backend", "unknown")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/apps/<app_id>/tick", methods=["POST"])
def app_tick(app_id: str):
    """Run one agent tick for the given app."""
    data = request.json or {}
    query = (data.get("query") or "tick").strip()
    async_mode = bool(data.get("async"))

    if async_mode:
        job_id = job_queue.submit(app_id, "act", {"query": query})
        return jsonify({"ok": True, "status": "queued", "job_id": job_id})

    try:
        agent = get_agent(app_id)
        result = agent.act(query)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/apps/<app_id>/reflect", methods=["POST"])
def app_reflect(app_id: str):
    """Return the agent's current reflection."""
    try:
        agent = get_agent(app_id)
        return jsonify({"ok": True, "data": agent.reflect()})
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
    try:
        result = get_os().run_workflow(workflow_id, initial_input)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Swarm endpoints ────────────────────────────────────────────────────────
@app.route("/swarm/run", methods=["POST"])
def swarm_run():
    data = request.json or {}
    app_ids = data.get("app_ids") or []
    prompt = (data.get("prompt") or "").strip()
    if not app_ids or not prompt:
        return jsonify({"ok": False, "error": "app_ids and prompt required"}), 400
    try:
        result = get_os().run_swarm(app_ids, prompt)
        return jsonify(result)
    except Exception as e:
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
    try:
        result = get_integration_manager().run(integration_id, endpoint=endpoint, method=method, payload=payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/proxy", methods=["POST"])
def proxy_request():
    data = request.json or {}
    integration_id = data.get("integration_id")
    if not integration_id:
        return jsonify({"ok": False, "error": "integration_id required"}), 400
    endpoint = data.get("endpoint", "")
    method = data.get("method", "GET")
    payload = data.get("payload")
    try:
        result = get_integration_manager().proxy(integration_id, endpoint=endpoint, method=method, payload=payload)
        return jsonify(result)
    except Exception as e:
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
    get_billing_calculator().set_plan(workspace_id, plan_id, credits)
    return jsonify({"ok": True})


@app.route("/billing/<workspace_id>/credits", methods=["POST"])
def billing_add_credits(workspace_id: str):
    data = request.json or {}
    amount = float(data.get("amount", 0))
    get_billing_calculator().add_credits(workspace_id, amount)
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
    days = min(365, max(1, request.args.get("days", 30, type=int)))
    summary = get_usage_meter().get_summary(workspace_id=None, days=days)
    return jsonify({"ok": True, "metrics": summary})


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
    if request.method == "GET":
        return jsonify({"ok": True, "prompts": reg.list_prompts()})

    data = request.json or {}
    if not data.get("name"):
        return jsonify({"ok": False, "error": "name is required"}), 400
    prompt = reg.save_prompt(data)
    return jsonify({"ok": True, "prompt": prompt.to_dict()})


@app.route("/prompts/<prompt_id>", methods=["GET", "DELETE"])
def prompt_detail(prompt_id: str):
    reg = get_prompt_registry()
    if request.method == "GET":
        prompt = reg.get_prompt(prompt_id)
        if not prompt:
            return jsonify({"ok": False, "error": "prompt not found"}), 404
        return jsonify({"ok": True, "prompt": prompt.to_dict()})

    if reg.delete_prompt(prompt_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "prompt not found"}), 404


@app.route("/knowledge-bases", methods=["GET", "POST"])
def knowledge_bases_index():
    mgr = get_kb_manager()
    if request.method == "GET":
        return jsonify({"ok": True, "knowledge_bases": mgr.list_kbs()})

    data = request.json or {}
    if not data.get("name"):
        return jsonify({"ok": False, "error": "name is required"}), 400
    kb = mgr.create_kb(data)
    return jsonify({"ok": True, "knowledge_base": kb.to_dict()})


@app.route("/knowledge-bases/<kb_id>", methods=["GET", "DELETE"])
def knowledge_base_detail(kb_id: str):
    mgr = get_kb_manager()
    if request.method == "GET":
        kb = mgr.get_kb(kb_id)
        if not kb:
            return jsonify({"ok": False, "error": "knowledge base not found"}), 404
        return jsonify({"ok": True, "knowledge_base": kb.to_dict()})

    if mgr.delete_kb(kb_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "knowledge base not found"}), 404


@app.route("/knowledge-bases/<kb_id>/documents", methods=["POST"])
def knowledge_base_upload(kb_id: str):
    data = request.json or {}
    text = (data.get("text") or "").strip()
    doc_id = data.get("doc_id") or f"doc-{int(time.time() * 1000)}"
    if not text:
        return jsonify({"ok": False, "error": "text is required"}), 400
    try:
        result = get_kb_manager().add_document(kb_id, doc_id, text, metadata=data.get("metadata", {}))
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
    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400
    try:
        chunks = get_kb_manager().query(kb_id, query, top_k=top_k, mode=mode)
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

    try:
        result = get_rag_orchestrator().chat(
            kb_id=kb_id,
            prompt_id=prompt_id,
            variables=variables,
            query=query,
            top_k=top_k,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Main entrypoint ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"AEON Python Kernel starting on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, threaded=True)
