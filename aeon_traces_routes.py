"""AEON OS — LLM tracing HTTP API.

Read-only observability routes registered via :func:`register_trace_routes`
(called from ``aeon_server.py``). All routes require authentication and are
scoped to the caller's workspace.
"""

from __future__ import annotations

from typing import Any

from flask import g, jsonify, request

from aeon_auth import require_auth, require_workspace_role
from aeon_traces import get_trace_store


def register_trace_routes(app: Any) -> None:
    @app.route("/traces", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def trace_list():
        limit = min(int(request.args.get("limit", 50)), 500)
        offset = max(int(request.args.get("offset", 0)), 0)
        status = (request.args.get("status") or None)
        if status not in {None, "ok", "error", "running"}:
            return jsonify({"ok": False, "error": "status must be ok|error|running"}), 400
        traces = get_trace_store().list_traces(g.workspace_id, limit=limit, offset=offset, status=status)
        return jsonify({"ok": True, "workspace_id": g.workspace_id, "traces": traces, "count": len(traces)})

    @app.route("/traces/summary", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def trace_summary():
        days = min(max(int(request.args.get("days", 7)), 1), 90)
        summary = get_trace_store().summary(g.workspace_id, days=days)
        return jsonify({"ok": True, "summary": summary})

    @app.route("/traces/<trace_id>", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def trace_detail(trace_id: str):
        trace = get_trace_store().get_trace(trace_id, g.workspace_id)
        if trace is None:
            return jsonify({"ok": False, "error": "trace not found"}), 404
        return jsonify({"ok": True, "trace": trace})
