"""
AEON OS — Platform Foundation HTTP API
======================================

Routes for the universal platform layer: tenant configuration, module
enablement, connector enablement + health, industry packs, and the
universal data model.

All routes are workspace-scoped: the current tenant is derived from the
authenticated session (``g.workspace_id``), so no object is ever read or
written without tenant context. Lifecycle mutations require ``OPERATOR``;
config edits require ``ADMIN``.
"""

from __future__ import annotations

from typing import Any

from flask import g, jsonify, request

from aeon_auth import has_role, require_auth, require_workspace_role
from aeon_platform import (
    connector_credential_status,
    connector_health,
    get_tenant_config_manager,
    list_connectors,
    list_industry_packs,
    list_modules,
    list_universal_entities,
    normalize_entity,
)


def _workspace_id() -> str:
    return str(getattr(g, "workspace_id", None) or g.user.get("workspace_id") or "")


def _is_admin() -> bool:
    membership_role = getattr(getattr(g, "membership", None), "role", None)
    user_role = g.user.get("role")
    return bool(has_role(membership_role, "ADMIN") or has_role(user_role, "ADMIN"))


def _audit(action: str, workspace_id: str, metadata: dict[str, Any] | None = None) -> None:
    try:
        from aeon_governance import get_governance

        get_governance().log_audit(
            action=action,
            module="platform",
            user_id=g.user.get("user_id"),
            email=g.user.get("email"),
            workspace_id=workspace_id,
            metadata=metadata or {},
        )
    except Exception:  # nosec B110 - telemetry must never change behavior
        pass


def register_platform_routes(app: Any) -> None:
    """Attach platform routes to the given Flask application."""

    manager = get_tenant_config_manager

    # ── Tenant configuration ──────────────────────────────────────────
    @app.route("/platform/config", methods=["GET", "PUT"])
    @require_auth
    @require_workspace_role("VIEWER")
    def platform_config():
        workspace_id = _workspace_id()
        if not workspace_id:
            return jsonify({"ok": False, "error": "workspace not selected"}), 400
        if request.method == "GET":
            return jsonify({"ok": True, "config": manager().effective(workspace_id)})
        if not _is_admin():
            return jsonify({"ok": False, "error": "workspace admin role required"}), 403
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "request body must be an object"}), 400
        try:
            config = manager().set(
                workspace_id,
                company=body.get("company"),
                industry=body.get("industry"),
                currency=body.get("currency"),
                country=body.get("country"),
                modules=body.get("modules"),
                connectors=body.get("connectors"),
                deployment_mode=body.get("deployment_mode"),
            )
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        _audit("TENANT_CONFIG_UPDATED", workspace_id, {"industry": config.get("industry"), "company": config.get("company")})
        return jsonify({"ok": True, "config": config})

    # ── Module engine ─────────────────────────────────────────────────
    @app.route("/platform/modules", methods=["GET", "PUT"])
    @require_auth
    @require_workspace_role("VIEWER")
    def platform_modules():
        workspace_id = _workspace_id()
        if not workspace_id:
            return jsonify({"ok": False, "error": "workspace not selected"}), 400
        if request.method == "GET":
            return jsonify({"ok": True, "modules": list_modules(workspace_id), "version": 1})
        if not (has_role(getattr(getattr(g, "membership", None), "role", None), "OPERATOR") or has_role(g.user.get("role"), "OPERATOR")):
            return jsonify({"ok": False, "error": "workspace operator role required"}), 403
        body = request.get_json(silent=True)
        module_ids = list((body or {}).get("modules") or ())
        try:
            config = manager().set(workspace_id, modules=module_ids)
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        _audit("TENANT_MODULES_UPDATED", workspace_id, {"modules": list(config.get("modules", ()))})
        return jsonify({"ok": True, "config": config, "modules": list_modules(workspace_id)})

    # ── Connector engine ──────────────────────────────────────────────
    @app.route("/platform/connectors", methods=["GET", "PUT"])
    @require_auth
    @require_workspace_role("VIEWER")
    def platform_connectors():
        workspace_id = _workspace_id()
        if not workspace_id:
            return jsonify({"ok": False, "error": "workspace not selected"}), 400
        if request.method == "GET":
            return jsonify({"ok": True, "connectors": list_connectors(workspace_id), "contract": None, "version": 1})
        if not (has_role(getattr(getattr(g, "membership", None), "role", None), "OPERATOR") or has_role(g.user.get("role"), "OPERATOR")):
            return jsonify({"ok": False, "error": "workspace operator role required"}), 403
        body = request.get_json(silent=True)
        connector_ids = list((body or {}).get("connectors") or ())
        try:
            config = manager().set(workspace_id, connectors=connector_ids)
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        _audit("TENANT_CONNECTORS_UPDATED", workspace_id, {"connectors": list(config.get("connectors", ()))})
        return jsonify({"ok": True, "config": config, "connectors": list_connectors(workspace_id)})

    @app.route("/platform/connectors/status", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def platform_connector_status():
        """Masked credential readiness per connector (booleans only)."""
        workspace_id = _workspace_id()
        if not workspace_id:
            return jsonify({"ok": False, "error": "workspace not selected"}), 400
        return jsonify({"ok": True, "status": connector_credential_status()})

    @app.route("/platform/connectors/<connector_id>/health", methods=["POST"])
    @require_auth
    @require_workspace_role("VIEWER")
    def platform_connector_health(connector_id: str):
        workspace_id = _workspace_id()
        if not workspace_id:
            return jsonify({"ok": False, "error": "workspace not selected"}), 400
        try:
            result = connector_health(connector_id)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        _audit("CONNECTOR_HEALTH_CHECKED", workspace_id, {"connector_id": connector_id})
        return jsonify({"ok": True, "health": result})

    # ── Industry packs ────────────────────────────────────────────────
    @app.route("/platform/industry-packs", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def platform_industry_packs():
        return jsonify({"ok": True, "packs": list_industry_packs(), "version": 1})

    # ── Universal data model ──────────────────────────────────────────
    @app.route("/platform/universal-model", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def platform_universal_model():
        return jsonify({"ok": True, "entities": list_universal_entities(), "version": 1})

    @app.route("/platform/universal-model/normalize", methods=["POST"])
    @require_auth
    @require_workspace_role("VIEWER")
    def platform_universal_normalize():
        """Normalize a source record into the canonical AEON entity.

        Body: ``{"entity": "invoice", "source": "sage", "record": {...}}``.
        Useful for connector adapters and for demonstrating the universal
        data model end-to-end.
        """
        workspace_id = _workspace_id()
        if not workspace_id:
            return jsonify({"ok": False, "error": "workspace not selected"}), 400
        body = request.get_json(silent=True) or {}
        entity_id = str(body.get("entity") or "")
        source = str(body.get("source") or "unknown")
        record = body.get("record")
        if not isinstance(record, dict):
            return jsonify({"ok": False, "error": "record must be an object"}), 400
        try:
            normalized = normalize_entity(entity_id, record, source)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        _audit("UNIVERSAL_RECORD_NORMALIZED", workspace_id, {"entity": entity_id, "source": source})
        return jsonify({"ok": True, "normalized": normalized})


__all__ = ["register_platform_routes"]
