"""HTTP routes for the AEON model registry.

Registry records capture provider, model, adapter version, and eval evidence
for each deployment. Reads require the workspace ``VIEWER`` role; writes
(register, approve, activate, rollback, deprecate, eval) require a workspace
admin, mirroring the LLM preference route pattern.
"""

from __future__ import annotations

from typing import Any

from flask import g, jsonify, request

from aeon_auth import has_role, require_auth, require_workspace_role
from aeon_model_registry import (
    activate_deployment,
    approve_deployment,
    deprecate_deployment,
    get_active_deployments,
    get_deployment,
    list_deployments,
    record_eval_evidence,
    register_deployment,
    rollback_deployment,
)


def _workspace_id() -> str:
    return str(getattr(g, "workspace_id", None) or g.user.get("workspace_id") or "")


def _is_workspace_admin() -> bool:
    membership_role = getattr(getattr(g, "membership", None), "role", None)
    return has_role(membership_role, "ADMIN") or has_role(g.user.get("role"), "ADMIN")


def _admin_guard():
    if not _is_workspace_admin():
        return jsonify({"ok": False, "error": "workspace admin role required"}), 403
    return None


def _opt_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    return str(value).strip() if value not in (None, "") else None


def _opt_float(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc


def register_model_registry_routes(app: Any) -> None:
    """Register model-registry routes on the Flask application."""

    @app.route("/models/registry", methods=["GET"], endpoint="model_registry_list")
    @require_auth
    @require_workspace_role("VIEWER")
    def model_registry_list():
        try:
            deployments = list_deployments(
                workspace_id=_workspace_id(),
                status=request.args.get("status") or None,
                provider=request.args.get("provider") or None,
                sector_pack_id=request.args.get("sector_pack") or None,
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "deployments": deployments})

    @app.route("/models/registry", methods=["POST"], endpoint="model_registry_register")
    @require_auth
    @require_workspace_role("VIEWER")
    def model_registry_register():
        blocked = _admin_guard()
        if blocked:
            return blocked
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"ok": False, "error": "request body must be an object"}), 400
        try:
            deployment = register_deployment(
                provider=str(data.get("provider") or "").strip().lower(),
                model=str(data.get("model") or "").strip(),
                workspace_id=_workspace_id(),
                adapter_version=_opt_str(data, "adapter_version"),
                base_model=_opt_str(data, "base_model"),
                sector_pack_id=_opt_str(data, "sector_pack_id"),
                eval_report=_opt_str(data, "eval_report"),
                eval_sha256=_opt_str(data, "eval_sha256"),
                accuracy=_opt_float(data, "accuracy"),
                rollback_plan=_opt_str(data, "rollback_plan"),
                notes=_opt_str(data, "notes"),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "deployment": deployment}), 201

    @app.route("/models/registry/active", methods=["GET"], endpoint="model_registry_active")
    @require_auth
    @require_workspace_role("VIEWER")
    def model_registry_active():
        return jsonify(
            {
                "ok": True,
                "deployments": get_active_deployments(
                    workspace_id=_workspace_id(),
                    provider=request.args.get("provider") or None,
                    sector_pack_id=request.args.get("sector_pack") or None,
                ),
            }
        )

    @app.route(
        "/models/registry/<deployment_id>", methods=["GET"], endpoint="model_registry_detail"
    )
    @require_auth
    @require_workspace_role("VIEWER")
    def model_registry_detail(deployment_id: str):
        deployment = get_deployment(deployment_id, workspace_id=_workspace_id())
        if deployment is None:
            return jsonify({"ok": False, "error": "deployment not found"}), 404
        return jsonify({"ok": True, "deployment": deployment})

    @app.route(
        "/models/registry/<deployment_id>/approve",
        methods=["POST"],
        endpoint="model_registry_approve",
    )
    @require_auth
    @require_workspace_role("VIEWER")
    def model_registry_approve(deployment_id: str):
        blocked = _admin_guard()
        if blocked:
            return blocked
        data = request.get_json(silent=True) or {}
        try:
            deployment = approve_deployment(
                deployment_id,
                str(data.get("approved_by") or g.user.get("email") or "admin"),
                workspace_id=_workspace_id(),
                note=_opt_str(data, "note"),
            )
        except KeyError:
            return jsonify({"ok": False, "error": "deployment not found"}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "deployment": deployment})

    @app.route(
        "/models/registry/<deployment_id>/activate",
        methods=["POST"],
        endpoint="model_registry_activate",
    )
    @require_auth
    @require_workspace_role("VIEWER")
    def model_registry_activate(deployment_id: str):
        blocked = _admin_guard()
        if blocked:
            return blocked
        data = request.get_json(silent=True) or {}
        try:
            deployment = activate_deployment(
                deployment_id,
                str(data.get("activated_by") or g.user.get("email") or "admin"),
                workspace_id=_workspace_id(),
            )
        except KeyError:
            return jsonify({"ok": False, "error": "deployment not found"}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "deployment": deployment})

    @app.route(
        "/models/registry/<deployment_id>/rollback",
        methods=["POST"],
        endpoint="model_registry_rollback",
    )
    @require_auth
    @require_workspace_role("VIEWER")
    def model_registry_rollback(deployment_id: str):
        blocked = _admin_guard()
        if blocked:
            return blocked
        data = request.get_json(silent=True) or {}
        try:
            deployment = rollback_deployment(
                deployment_id,
                str(data.get("rolled_back_by") or g.user.get("email") or "admin"),
                str(data.get("reason") or ""),
                workspace_id=_workspace_id(),
            )
        except KeyError:
            return jsonify({"ok": False, "error": "deployment not found"}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "deployment": deployment})

    @app.route(
        "/models/registry/<deployment_id>/deprecate",
        methods=["POST"],
        endpoint="model_registry_deprecate",
    )
    @require_auth
    @require_workspace_role("VIEWER")
    def model_registry_deprecate(deployment_id: str):
        blocked = _admin_guard()
        if blocked:
            return blocked
        data = request.get_json(silent=True) or {}
        try:
            deployment = deprecate_deployment(
                deployment_id,
                str(data.get("reason") or ""),
                workspace_id=_workspace_id(),
            )
        except KeyError:
            return jsonify({"ok": False, "error": "deployment not found"}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "deployment": deployment})

    @app.route(
        "/models/registry/<deployment_id>/eval",
        methods=["POST"],
        endpoint="model_registry_eval",
    )
    @require_auth
    @require_workspace_role("VIEWER")
    def model_registry_eval(deployment_id: str):
        blocked = _admin_guard()
        if blocked:
            return blocked
        data = request.get_json(silent=True) or {}
        try:
            deployment = record_eval_evidence(
                deployment_id,
                eval_report=_opt_str(data, "eval_report"),
                eval_sha256=_opt_str(data, "eval_sha256"),
                accuracy=_opt_float(data, "accuracy"),
                metrics=data.get("metrics") if isinstance(data.get("metrics"), dict) else None,
                workspace_id=_workspace_id(),
            )
        except KeyError:
            return jsonify({"ok": False, "error": "deployment not found"}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "deployment": deployment})
