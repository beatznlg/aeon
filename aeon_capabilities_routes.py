"""HTTP API for the unified AEON capability registry."""

from __future__ import annotations

from typing import Any

from flask import g, jsonify, request

from aeon_auth import require_auth, require_workspace_role
from aeon_capabilities import get_capability_registry


def _audit_capability_decision(
    capability_id: str,
    result: dict[str, Any],
    user_role: str | None,
) -> None:
    """Record a capability decision without persisting invocation arguments."""
    try:
        error = str(result.get("error") or "")
        if result.get("ok"):
            reason = "success"
        elif error == "capability not found in workspace":
            reason = "not_found"
        elif error.startswith("capability requires "):
            reason = "role_denied"
        elif error == "capability blocked by workspace policy":
            reason = "policy_denied"
        elif error == "capability requires approval by workspace policy":
            reason = "approval_required"
        elif error.startswith("arguments "):
            reason = "invalid_arguments"
        else:
            reason = "execution_failed"

        from aeon_governance import get_governance

        get_governance().log_audit(
            action="capability_invocation",
            module="capabilities",
            user_id=g.user.get("user_id"),
            email=g.user.get("email"),
            workspace_id=g.workspace_id,
            metadata={
                "capability_id": capability_id,
                "decision": "allowed" if result.get("ok") else "denied",
                "reason": reason,
                "user_role": user_role,
                "policy_violation_count": len(result.get("policy") or []),
            },
        )
    except Exception:
        # Audit delivery must never change capability authorization semantics.
        pass


def _create_capability_approval(
    capability_id: str,
    arguments: dict[str, Any],
    policy: dict[str, Any],
    *,
    user_role: str | None,
) -> dict[str, Any]:
    """Persist a pending capability approval without executing the capability."""
    try:
        from aeon_automations import _create_approval_request

        event = {
            "type": "capability_invocation",
            "payload": {
                "capability_id": capability_id,
                "arguments": arguments,
                "policy": policy.get("violations") or [],
                "user_role": user_role,
            },
            "user_id": g.user.get("user_id"),
            "workspace_id": g.workspace_id,
        }
        rule = {
            "id": None,
            "name": f"Capability approval: {capability_id}",
            "action_type": "capability",
            "action_config": {
                "capability_id": capability_id,
                "arguments": arguments,
                "user_role": user_role,
            },
            "workspace_id": g.workspace_id,
        }
        result = _create_approval_request(rule, event)
        if not result.get("ok"):
            return {"ok": False, "error": "approval service unavailable"}
        approval = result.get("approval") or {}
        return {
            "ok": True,
            "approval_id": approval.get("id"),
            "status": "pending",
            "policy": policy.get("violations") or [],
        }
    except Exception:
        return {"ok": False, "error": "approval service unavailable"}


def register_capability_routes(app: Any) -> None:
    @app.route("/capabilities", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def capability_list():
        registry = get_capability_registry()
        capabilities = registry.discover(g.workspace_id)
        source_counts: dict[str, int] = {}
        for capability in capabilities:
            source = capability["source"]
            source_counts[source] = source_counts.get(source, 0) + 1
        return jsonify(
            {
                "ok": True,
                "workspace_id": g.workspace_id,
                "capabilities": capabilities,
                "count": len(capabilities),
                "source_counts": source_counts,
            }
        )

    @app.route("/capabilities/audit", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def capability_audit():
        """Return recent capability decisions for the authenticated workspace."""
        try:
            limit = min(100, max(1, request.args.get("limit", 25, type=int)))
            offset = max(0, request.args.get("offset", 0, type=int))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "limit and offset must be integers"}), 400

        try:
            from aeon_governance import get_governance

            result = get_governance().query_audit(
                workspace_id=g.workspace_id,
                action="capability_invocation",
                module="capabilities",
                limit=limit + 1,
                offset=offset,
            )
        except Exception:
            return jsonify({"ok": False, "error": "audit service unavailable"}), 503

        if not result.get("ok"):
            return jsonify({"ok": False, "error": "audit service unavailable"}), 503

        rows = result.get("rows") or []
        has_more = len(rows) > limit
        rows = rows[:limit]
        return jsonify(
            {
                "ok": True,
                "workspace_id": g.workspace_id,
                "logs": rows,
                "count": len(rows),
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
            }
        )

    @app.route("/capabilities/<path:capability_id>", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def capability_detail(capability_id: str):
        capability = get_capability_registry().get(g.workspace_id, capability_id)
        if capability is None:
            return jsonify({"ok": False, "error": "capability not found"}), 404
        return jsonify({"ok": True, "capability": capability})

    @app.route("/capabilities/invoke", methods=["POST"])
    @require_auth
    @require_workspace_role("OPERATOR")
    def capability_invoke():
        payload = request.get_json(silent=True)
        if payload is None:
            data = {}
        elif not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "request body must be an object"}), 400
        else:
            data = payload
        capability_id = str(data.get("capability_id", "")).strip()
        arguments = data.get("arguments", {})
        if not capability_id:
            return jsonify({"ok": False, "error": "capability_id is required"}), 400
        membership = getattr(g, "membership", None)
        user_role = getattr(membership, "role", None) or g.user.get("role")
        result = get_capability_registry().invoke(
            g.workspace_id, capability_id, arguments, user_role=user_role
        )
        _audit_capability_decision(capability_id, result, user_role)
        if not result.get("ok"):
            error = str(result.get("error") or "")
            if error == "capability requires approval by workspace policy":
                approval = _create_capability_approval(
                    capability_id,
                    arguments,
                    {"violations": result.get("policy") or []},
                    user_role=user_role,
                )
                if approval.get("ok"):
                    result = {**result, **approval}
                    return jsonify(result), 202
                return jsonify(approval), 503
            status = (
                404
                if error == "capability not found in workspace"
                else 403
                if error.startswith("capability requires ") or error == "capability blocked by workspace policy"
                else 400
            )
            return jsonify(result), status
        return jsonify({"ok": True, "capability_id": capability_id, "result": result})
