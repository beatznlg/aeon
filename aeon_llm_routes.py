"""HTTP routes for AEON's credential-free LLM provider bridge."""

from __future__ import annotations

import os
from typing import Any

from flask import g, jsonify, request

from aeon_auth import has_role, require_auth, require_workspace_role
from aeon_db import get_workspace_llm_preference, update_workspace_llm_preference
from aeon_llm import list_models, list_providers, provider_health, set_active_provider, test_provider


def _workspace_id() -> str:
    return str(getattr(g, "workspace_id", None) or g.user.get("workspace_id") or "")


def _effective_preference(workspace_id: str) -> dict[str, Any]:
    """Resolve workspace preference, falling back to legacy process settings."""
    preference = get_workspace_llm_preference(workspace_id)
    provider = preference.get("provider") or os.environ.get("AEON_LLM_PROVIDER") or "stub"
    model = preference.get("model") or os.environ.get("AEON_LLM_MODEL")
    return {**preference, "provider": provider, "model": model, "source": "workspace" if preference.get("provider") else "environment"}


def _is_workspace_admin() -> bool:
    membership_role = getattr(getattr(g, "membership", None), "role", None)
    return has_role(membership_role, "ADMIN") or has_role(g.user.get("role"), "ADMIN")


def register_llm_routes(app: Any) -> None:
    """Register model-aware LLM routes before legacy aliases are declared."""

    @app.route("/llm/providers", methods=["GET"], endpoint="llm_provider_catalog")
    @require_auth
    @require_workspace_role("VIEWER")
    def llm_provider_catalog():
        return jsonify({"ok": True, "providers": list_providers(), "preference": _effective_preference(_workspace_id())})

    @app.route("/llm/models", methods=["GET"], endpoint="llm_model_catalog")
    @require_auth
    @require_workspace_role("VIEWER")
    def llm_model_catalog():
        return jsonify({"ok": True, "models": list_models(request.args.get("provider"))})

    @app.route("/llm/preferences", methods=["GET", "PUT"], endpoint="llm_workspace_preference")
    @require_auth
    @require_workspace_role("VIEWER")
    def llm_workspace_preference():
        workspace_id = _workspace_id()
        if request.method == "GET":
            return jsonify({"ok": True, "preference": _effective_preference(workspace_id)})
        if not _is_workspace_admin():
            return jsonify({"ok": False, "error": "workspace admin role required"}), 403
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"ok": False, "error": "request body must be an object"}), 400
        provider = str(data.get("provider", "")).strip().lower()
        model_value = data.get("model")
        model = str(model_value).strip() if model_value is not None else None
        if not provider:
            return jsonify({"ok": False, "error": "provider required"}), 400
        if len(provider) > 50 or (model is not None and len(model) > 255):
            return jsonify({"ok": False, "error": "provider or model is too long"}), 400
        try:
            preference = update_workspace_llm_preference(workspace_id, provider=provider, model=model or None)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        return jsonify({"ok": True, "preference": {**preference, "source": "workspace"}})

    @app.route("/llm/switch", methods=["POST"], endpoint="llm_provider_switch")
    @require_auth
    @require_workspace_role("VIEWER")
    def llm_provider_switch():
        data = request.get_json(silent=True) or {}
        provider = str(data.get("provider", "")).strip().lower()
        model = str(data.get("model", "")).strip() or None
        if not provider:
            return jsonify({"ok": False, "error": "provider required"}), 400
        result = set_active_provider(provider, model=model)
        if result.get("ok"):
            workspace_id = _workspace_id()
            if _is_workspace_admin():
                try:
                    preference = update_workspace_llm_preference(workspace_id, provider=provider, model=result.get("model") or model)
                    result["preference"] = {**preference, "source": "workspace"}
                except ValueError:
                    pass
            else:
                result["preference"] = {**_effective_preference(workspace_id), "source": "environment"}
        return jsonify(result), 200 if result.get("ok") else 400

    @app.route("/llm/health", methods=["GET"], endpoint="llm_provider_health")
    @require_auth
    @require_workspace_role("VIEWER")
    def llm_provider_health():
        provider = request.args.get("provider")
        model = request.args.get("model")
        return jsonify(provider_health(provider, model=model))

    @app.route("/llm/test", methods=["POST"], endpoint="llm_provider_test")
    @require_auth
    @require_workspace_role("VIEWER")
    def llm_provider_test():
        data = request.get_json(silent=True) or {}
        provider = str(data.get("provider", "")).strip() or None
        model = str(data.get("model", "")).strip() or None
        prompt = str(data.get("prompt", "")).strip() or None
        return jsonify(test_provider(provider, prompt, model=model))


__all__ = ["register_llm_routes"]
