"""
AEON OS — Plugin Marketplace HTTP API
=====================================
Route definitions for the plugin marketplace. The routes are registered on
the Flask app via :func:`register_marketplace_routes` (called from
``aeon_server.py``) so this module stays lightweight and independently
testable.

All routes require authentication and are scoped to the caller's workspace.
Lifecycle mutations (install / uninstall / enable / disable / config / run)
require at least the ``OPERATOR`` workspace role; catalog browsing requires
``VIEWER``.
"""

from __future__ import annotations

from typing import Any

from flask import g, jsonify, request

from aeon_auth import require_auth, require_permission
from aeon_marketplace import MarketplaceManager
from aeon_marketplace import get_marketplace_manager as _get_shared_manager


def get_marketplace_manager() -> MarketplaceManager:
    """Return the process-wide marketplace manager bound to AEON_ROOT.

    Delegates to the module-level singleton in :mod:`aeon_marketplace` so the
    HTTP routes, automation actions, kernel tools, and workflow nodes all
    share one consistent, workspace-scoped store. Resolving with no explicit
    root (rather than a module-level constant) keeps every caller pinned to
    the live ``AEON_ROOT`` value, so tests and deployments never diverge.
    """
    return _get_shared_manager()


def _log_audit(action: str, workspace_id: str, plugin_id: str, metadata: dict[str, Any] | None = None) -> None:
    """Record a marketplace lifecycle audit event for a workspace."""
    from aeon_server import _governance_context, get_governance_manager

    ctx = _governance_context()
    get_governance_manager().log_audit(
        action=action,
        module="marketplace",
        user_id=ctx.get("user_id"),
        workspace_id=workspace_id,
        email=ctx.get("email"),
        metadata=dict(metadata or {}, plugin_id=plugin_id),
    )


def register_marketplace_routes(app) -> None:  # type: ignore[no-untyped-def]
    """Attach marketplace routes to the given Flask application."""

    @app.route("/marketplace/plugins", methods=["GET"])
    @require_auth
    @require_permission("plugins.read")
    def marketplace_plugins():
        """Return the plugin catalog enriched with the workspace's install state."""
        mgr = get_marketplace_manager()
        return jsonify(
            {"ok": True, "plugins": mgr.list_catalog(workspace_id=g.workspace_id), "summary": mgr.catalog_summary()}
        )

    @app.route("/marketplace/installed", methods=["GET"])
    @require_auth
    @require_permission("plugins.read")
    def marketplace_installed():
        """Return the plugins installed in the caller's workspace."""
        return jsonify({"ok": True, "installed": get_marketplace_manager().list_installed(g.workspace_id)})

    @app.route("/marketplace/agent-tools", methods=["GET"])
    @require_auth
    @require_permission("plugins.read")
    def marketplace_agent_tools():
        """Return the plugin tools an agent may call in the caller's workspace.

        Mirrors kernel discovery (installed + enabled + ``execute`` permission)
        so the chat UI can show exactly what the agent can invoke.
        """
        tools = get_marketplace_manager().agent_tools(g.workspace_id)
        return jsonify({"ok": True, "workspace_id": g.workspace_id, "plugins": tools, "count": len(tools)})

    @app.route("/marketplace/plugins/<plugin_id>", methods=["GET"])
    @require_auth
    @require_permission("plugins.read")
    def marketplace_plugin_detail(plugin_id: str):
        """Return a single plugin manifest."""
        manifest = get_marketplace_manager().get_plugin(plugin_id)
        if manifest is None:
            return jsonify({"ok": False, "error": "plugin not found"}), 404
        return jsonify({"ok": True, "plugin": manifest.to_dict()})

    @app.route("/marketplace/plugins/<plugin_id>/install", methods=["POST"])
    @require_auth
    @require_permission("plugins.manage")
    def marketplace_plugin_install(plugin_id: str):
        """Install a plugin into the caller's workspace."""
        data = request.json or {}
        result = get_marketplace_manager().install(g.workspace_id, plugin_id, data.get("config"))
        if not result["ok"]:
            return jsonify(result), 400
        _log_audit("PLUGIN_INSTALLED", g.workspace_id, plugin_id, {"version": result["install"]["version"]})
        return jsonify(result), 201

    @app.route("/marketplace/plugins/<plugin_id>/uninstall", methods=["POST"])
    @require_auth
    @require_permission("plugins.manage")
    def marketplace_plugin_uninstall(plugin_id: str):
        """Uninstall a plugin from the caller's workspace."""
        result = get_marketplace_manager().uninstall(g.workspace_id, plugin_id)
        if not result["ok"]:
            return jsonify(result), 404
        _log_audit("PLUGIN_UNINSTALLED", g.workspace_id, plugin_id)
        return jsonify(result)

    @app.route("/marketplace/plugins/<plugin_id>/enable", methods=["POST"])
    @require_auth
    @require_permission("plugins.manage")
    def marketplace_plugin_enable(plugin_id: str):
        """Enable an installed plugin."""
        result = get_marketplace_manager().set_enabled(g.workspace_id, plugin_id, True)
        if not result["ok"]:
            return jsonify(result), 404
        _log_audit("PLUGIN_ENABLED", g.workspace_id, plugin_id)
        return jsonify(result)

    @app.route("/marketplace/plugins/<plugin_id>/disable", methods=["POST"])
    @require_auth
    @require_permission("plugins.manage")
    def marketplace_plugin_disable(plugin_id: str):
        """Disable an installed plugin."""
        result = get_marketplace_manager().set_enabled(g.workspace_id, plugin_id, False)
        if not result["ok"]:
            return jsonify(result), 404
        _log_audit("PLUGIN_DISABLED", g.workspace_id, plugin_id)
        return jsonify(result)

    @app.route("/marketplace/plugins/<plugin_id>/config", methods=["POST"])
    @require_auth
    @require_permission("plugins.manage")
    def marketplace_plugin_config(plugin_id: str):
        """Update an installed plugin's configuration (validated against its schema)."""
        data = request.json or {}
        result = get_marketplace_manager().update_config(g.workspace_id, plugin_id, data.get("config", {}))
        if not result["ok"]:
            return jsonify(result), 400
        _log_audit("PLUGIN_CONFIG_UPDATED", g.workspace_id, plugin_id)
        return jsonify(result)

    @app.route("/marketplace/plugins/<plugin_id>/run", methods=["POST"])
    @require_auth
    @require_permission("plugins.manage")
    def marketplace_plugin_run(plugin_id: str):
        """Invoke a plugin entry point for the caller's workspace."""
        data = request.json or {}
        entry = data.get("entry")
        if not entry:
            return jsonify({"ok": False, "error": "entry required"}), 400

        result = get_marketplace_manager().run_entry(g.workspace_id, plugin_id, entry, data.get("params"))

        from aeon_server import metrics_collector

        metrics_collector.inc(
            "aeon_plugin_runs_total", labels={"plugin_id": plugin_id, "entry": entry, "ok": str(result.get("ok", True))}
        )

        if not result["ok"]:
            status = {
                "plugin not installed": 404,
                "plugin no longer in catalog": 404,
                "plugin disabled": 403,
                "plugin does not declare execute permission": 403,
            }.get(result["error"], 400)
            _log_audit("PLUGIN_RUN_ERROR", g.workspace_id, plugin_id, {"entry": entry, "error": result["error"]})
            return jsonify(result), status
        _log_audit("PLUGIN_RUN", g.workspace_id, plugin_id, {"entry": entry})
        return jsonify(result)
