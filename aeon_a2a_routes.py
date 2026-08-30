"""AEON OS — A2A (Agent-to-Agent) HTTP API.

Routes registered via :func:`register_a2a_routes` (called from
``aeon_server.py``). Reads require ``VIEWER``; mutations and delegation
require ``OPERATOR``. Everything is scoped to the caller's workspace and
tokens are masked — the same contract as the MCP routes (docs/MCP.md).

Discovery (outbound): ``GET /a2a/agents`` lists registered remote agents and
``POST /a2a/agents/<id>/refresh`` pulls the peer's
``/.well-known/agent.json`` agent card.

Delegation (outbound): ``POST /a2a/agents/<id>/message`` sends a task via
``message/send``; ``GET /a2a/agents/<id>/tasks/<task_id>`` polls ``tasks/get``.

Discovery (inbound): ``GET /.well-known/agent.json`` exposes THIS AEON
instance's own agent card so remote A2A peers can discover it.
"""

from __future__ import annotations

from typing import Any

from flask import g, jsonify, request

from aeon_a2a import get_a2a_manager
from aeon_auth import require_auth, require_workspace_role

_A2A_PROTOCOL_VERSION = "0.3.0"


def _own_agent_card(base_url: str) -> dict[str, Any]:
    """This AEON instance's A2A agent card (inbound discovery)."""
    return {
        "name": "AEON OS",
        "description": (
            "AEON OS agent control plane: multi-tenant workspaces, workflow "
            "orchestration, model-agnostic LLM gateway, RAG knowledge bases, "
            "and human-in-the-loop approvals."
        ),
        "url": base_url,
        "version": "1.0.0",
        "protocolVersion": _A2A_PROTOCOL_VERSION,
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": [
            {"name": "agent-orchestration", "description": "Create and supervise cooperating agents."},
            {"name": "workflow-automation", "description": "Event-driven and scheduled workflow execution."},
            {"name": "knowledge-retrieval", "description": "RAG search over workspace knowledge bases."},
        ],
        "provider": {"organization": "AEON OS", "url": base_url},
    }


def register_a2a_routes(app: Any) -> None:
    manager = get_a2a_manager

    # ── Inbound discovery: our own agent card ─────────────────────────────
    @app.route("/.well-known/agent.json", methods=["GET"])
    def a2a_well_known_agent():
        base = request.url_root.rstrip("/")
        return jsonify(_own_agent_card(base))

    # ── Registry CRUD ─────────────────────────────────────────────────────
    @app.route("/a2a/agents", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def a2a_agent_list():
        agents = manager().list_agents(g.workspace_id)
        return jsonify({"ok": True, "workspace_id": g.workspace_id, "agents": agents, "count": len(agents)})

    @app.route("/a2a/agents", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def a2a_agent_add():
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()
        url = str(data.get("url", "")).strip()
        token = str(data.get("token", "") or "")
        enabled = bool(data.get("enabled", True))
        try:
            agent = manager().add_agent(g.workspace_id, name, url, token=token, enabled=enabled)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "agent": agent.to_dict(mask=True)}), 201

    @app.route("/a2a/agents/<agent_id>", methods=["DELETE"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def a2a_agent_delete(agent_id: str):
        if not manager().remove_agent(g.workspace_id, agent_id):
            return jsonify({"ok": False, "error": "agent not found"}), 404
        return jsonify({"ok": True})

    @app.route("/a2a/agents/<agent_id>/enable", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def a2a_agent_enable(agent_id: str):
        agent = manager().set_enabled(g.workspace_id, agent_id, True)
        if agent is None:
            return jsonify({"ok": False, "error": "agent not found"}), 404
        return jsonify({"ok": True, "agent": agent.to_dict(mask=True)})

    @app.route("/a2a/agents/<agent_id>/disable", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def a2a_agent_disable(agent_id: str):
        agent = manager().set_enabled(g.workspace_id, agent_id, False)
        if agent is None:
            return jsonify({"ok": False, "error": "agent not found"}), 404
        return jsonify({"ok": True, "agent": agent.to_dict(mask=True)})

    # ── Discovery (outbound): pull the peer's agent card ──────────────────
    @app.route("/a2a/agents/<agent_id>/refresh", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def a2a_agent_refresh(agent_id: str):
        result = manager().refresh_agent(g.workspace_id, agent_id)
        if result.get("ok"):
            return jsonify({"ok": True, "agent_card": result["agent_card"]})
        status = 404 if result.get("error") == "agent not found" else 502
        return jsonify({"ok": False, "error": result.get("error", "refresh failed")}), status

    # ── Delegation ────────────────────────────────────────────────────────
    @app.route("/a2a/agents/<agent_id>/message", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def a2a_agent_message(agent_id: str):
        data = request.get_json(silent=True) or {}
        message = data.get("message")
        if not isinstance(message, dict) or not str(message.get("content", "")).strip():
            return jsonify({"ok": False, "error": "message.content is required"}), 400
        result = manager().delegate(g.workspace_id, agent_id, message)
        if result.get("ok"):
            return jsonify({"ok": True, "result": result.get("result", {})})
        status = 404 if result.get("error") == "agent not found" else 502
        return jsonify({"ok": False, "error": result.get("error", "delegation failed")}), status

    @app.route("/a2a/agents/<agent_id>/tasks/<task_id>", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def a2a_agent_task(agent_id: str, task_id: str):
        result = manager().task_status(g.workspace_id, agent_id, task_id)
        if result.get("ok"):
            return jsonify({"ok": True, "task": result.get("result", {})})
        status = 404 if result.get("error") == "agent not found" else 502
        return jsonify({"ok": False, "error": result.get("error", "task query failed")}), status

    # ── Agent-facing directory ────────────────────────────────────────────
    @app.route("/a2a/agent-directory", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def a2a_agent_directory():
        entries = manager().agent_directory(g.workspace_id)
        return jsonify({"ok": True, "workspace_id": g.workspace_id, "agents": entries, "count": len(entries)})


__all__ = ["register_a2a_routes"]
