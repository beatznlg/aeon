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


# ── Main entrypoint ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"AEON Python Kernel starting on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, threaded=True)
