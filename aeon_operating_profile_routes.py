"""HTTP API for AEON workspace operating profiles."""

from __future__ import annotations

from typing import Any

from flask import g, jsonify, request

from aeon_auth import has_role, require_auth, require_workspace_role
from aeon_operating_profiles import (
    get_operating_profile_manager,
    get_profile,
    list_profiles,
    recommend_profiles,
)


def _workspace_id() -> str:
    return str(getattr(g, "workspace_id", None) or g.user.get("workspace_id") or "")


def _audit(action: str, workspace_id: str, metadata: dict[str, Any] | None = None) -> None:
    try:
        from aeon_governance import get_governance

        get_governance().log_audit(
            action=action,
            module="operating_profiles",
            user_id=g.user.get("user_id"),
            email=g.user.get("email"),
            workspace_id=workspace_id,
            metadata=metadata or {},
        )
    except Exception:
        # A telemetry failure must not change profile authorization behavior.
        pass


def register_operating_profile_routes(app: Any) -> None:
    """Register profile catalog and workspace selection routes."""

    @app.route("/operating-profiles", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def operating_profile_catalog():
        profiles = list_profiles(
            sector=request.args.get("sector"),
            organization_type=request.args.get("organization_type"),
            deployment_mode=request.args.get("deployment_mode"),
        )
        return jsonify({"ok": True, "profiles": profiles, "count": len(profiles), "version": 1})

    @app.route("/operating-profiles/recommend", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def operating_profile_recommendations():
        recommendations = recommend_profiles(
            sector=request.args.get("sector"),
            organization_type=request.args.get("organization_type"),
            deployment_mode=request.args.get("deployment_mode"),
            data_classification=request.args.get("data_classification"),
        )
        return jsonify({"ok": True, "recommendations": recommendations})

    @app.route("/operating-profiles/<profile_id>", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def operating_profile_detail(profile_id: str):
        profile = get_profile(profile_id)
        if profile is None:
            return jsonify({"ok": False, "error": "operating profile not found"}), 404
        return jsonify({"ok": True, "profile": profile.to_dict()})

    @app.route("/workspace/operating-profile", methods=["GET", "PUT"])
    @require_auth
    @require_workspace_role("VIEWER")
    def workspace_operating_profile():
        workspace_id = _workspace_id()
        if not workspace_id:
            return jsonify({"ok": False, "error": "workspace not selected"}), 400
        manager = get_operating_profile_manager()
        if request.method == "GET":
            return jsonify({"ok": True, **manager.effective(workspace_id)})

        membership_role = getattr(getattr(g, "membership", None), "role", None)
        user_role = g.user.get("role")
        if not (has_role(membership_role, "ADMIN") or has_role(user_role, "ADMIN")):
            return jsonify({"ok": False, "error": "workspace admin role required"}), 403
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "request body must be an object"}), 400
        try:
            selection = manager.set(
                workspace_id,
                profile_id=body.get("profile_id", ""),
                sector=body.get("sector", "general"),
                organization_type=body.get("organization_type", "enterprise"),
                deployment_mode=body.get("deployment_mode", "cloud"),
                data_classification=body.get("data_classification", "internal"),
                compliance_frameworks=body.get("compliance_frameworks") or (),
            )
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        _audit("OPERATING_PROFILE_SELECTED", workspace_id, {"profile_id": selection.profile_id, "sector": selection.sector, "deployment_mode": selection.deployment_mode})
        return jsonify({"ok": True, **manager.effective(workspace_id)}), 200


__all__ = ["register_operating_profile_routes"]
