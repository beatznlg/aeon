"""AEON OS — MCP (Model Context Protocol) HTTP API.

Routes registered via :func:`register_mcp_routes` (called from
``aeon_server.py``). Reads require ``VIEWER``; mutations require ``OPERATOR``.
Everything is scoped to the caller's workspace and tokens are masked.
"""

from __future__ import annotations

from typing import Any

from flask import g, jsonify, request

from aeon_auth import require_auth, require_workspace_role
from aeon_mcp import get_mcp_manager


def register_mcp_routes(app: Any) -> None:
    @app.route("/mcp/servers", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def mcp_server_list():
        servers = get_mcp_manager().list_servers(g.workspace_id)
        return jsonify({"ok": True, "workspace_id": g.workspace_id, "servers": servers, "count": len(servers)})

    @app.route("/mcp/servers", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def mcp_server_add():
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()
        url = str(data.get("url", "")).strip()
        token = str(data.get("token", "") or "")
        enabled = bool(data.get("enabled", True))
        try:
            server = get_mcp_manager().add_server(g.workspace_id, name, url, token=token, enabled=enabled)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "server": server.to_dict(mask=True)}), 201

    @app.route("/mcp/servers/<server_id>", methods=["DELETE"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def mcp_server_delete(server_id: str):
        if not get_mcp_manager().remove_server(g.workspace_id, server_id):
            return jsonify({"ok": False, "error": "server not found"}), 404
        return jsonify({"ok": True})

    @app.route("/mcp/servers/<server_id>/enable", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def mcp_server_enable(server_id: str):
        server = get_mcp_manager().set_enabled(g.workspace_id, server_id, True)
        if server is None:
            return jsonify({"ok": False, "error": "server not found"}), 404
        return jsonify({"ok": True, "server": server.to_dict(mask=True)})

    @app.route("/mcp/servers/<server_id>/disable", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def mcp_server_disable(server_id: str):
        server = get_mcp_manager().set_enabled(g.workspace_id, server_id, False)
        if server is None:
            return jsonify({"ok": False, "error": "server not found"}), 404
        return jsonify({"ok": True, "server": server.to_dict(mask=True)})

    @app.route("/mcp/servers/<server_id>/refresh", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def mcp_server_refresh(server_id: str):
        result = get_mcp_manager().refresh_tools(g.workspace_id, server_id)
        if result.get("ok"):
            return jsonify({"ok": True, "tool_count": result["tool_count"], "tools": result["tools"]})
        return jsonify({"ok": False, "error": result.get("error", "refresh failed")}), 502

    @app.route("/mcp/tools/call", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def mcp_tool_call():
        data = request.get_json(silent=True) or {}
        server_id = str(data.get("server_id", "")).strip()
        tool = str(data.get("tool", "")).strip()
        arguments = data.get("arguments") or {}
        if not server_id or not tool:
            return jsonify({"ok": False, "error": "server_id and tool are required"}), 400
        result = get_mcp_manager().call_tool(g.workspace_id, server_id, tool, arguments)
        if result.get("ok"):
            return jsonify({"ok": True, "result": result.get("result", {})})
        return jsonify({"ok": False, "error": result.get("error", "call failed")}), 502

    @app.route("/mcp/agent-tools", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def mcp_agent_tools():
        tools = get_mcp_manager().agent_tools(g.workspace_id)
        return jsonify({"ok": True, "workspace_id": g.workspace_id, "tools": tools, "count": len(tools)})
