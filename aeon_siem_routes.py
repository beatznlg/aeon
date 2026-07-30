"""
AEON OS Phase 49 — SIEM Integration API routes.
"""

from typing import Any

from flask import Blueprint, g, jsonify, request

from aeon_auth import require_auth, require_workspace_role
from aeon_db import (
    SiemExportLog,
    SiemIntegration,
    create_siem_export_log,
    create_siem_integration,
    delete_siem_integration,
    get_siem_integration,
    list_siem_export_logs,
    list_siem_integrations,
    update_siem_export_log_status,
    update_siem_integration,
)
from aeon_siem import SiemExporter, list_supported_providers

siem_bp = Blueprint("siem", __name__)

_ALLOWED_PROVIDERS = {"splunk", "datadog", "elastic", "webhook", "qradar", "sentinel"}


# --- Serialization helpers --------------------------------------------------

def _integration_to_dict(i: SiemIntegration) -> dict[str, Any]:
    return {
        "id": i.id,
        "workspace_id": i.workspace_id,
        "provider": i.provider,
        "name": i.name,
        "endpoint_url": i.endpoint_url,
        "auth_type": i.auth_type,
        "custom_headers": i.custom_headers,
        "event_filters": i.event_filters,
        "log_level": i.log_level,
        "batch_size": i.batch_size,
        "enabled": i.enabled,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


def _export_log_to_dict(log: SiemExportLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "workspace_id": log.workspace_id,
        "integration_id": log.integration_id,
        "event_type": log.event_type,
        "event_id": log.event_id,
        "status": log.status,
        "http_status": log.http_status,
        "payload_size": log.payload_size,
        "response_text": log.response_text,
        "retry_count": log.retry_count,
        "created_at": log.created_at.isoformat() if log.created_at else None,
        "sent_at": log.sent_at.isoformat() if log.sent_at else None,
    }


# --- Providers ----------------------------------------------------------------

@siem_bp.route("/siem/providers", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def list_siem_providers():
    """Return supported SIEM providers."""
    return jsonify({"ok": True, "providers": list_supported_providers()})


# --- Integrations -------------------------------------------------------------

@siem_bp.route("/siem/integrations", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def list_siem_integrations_endpoint():
    """List SIEM integrations for the current workspace."""
    ctx = g.user
    rows = list_siem_integrations(ctx.get("workspace_id"))
    return jsonify({"ok": True, "integrations": [_integration_to_dict(i) for i in rows]})


@siem_bp.route("/siem/integrations", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def create_siem_integration_endpoint():
    """Create a new SIEM integration."""
    ctx = g.user
    data = request.get_json(silent=True) or {}
    provider = (data.get("provider") or "").strip().lower()
    name = (data.get("name") or "").strip()
    endpoint_url = (data.get("endpoint_url") or "").strip()

    if not name or not endpoint_url:
        return jsonify({"ok": False, "error": "name and endpoint_url are required"}), 400
    if provider not in _ALLOWED_PROVIDERS:
        return jsonify({"ok": False, "error": f"provider must be one of: {', '.join(sorted(_ALLOWED_PROVIDERS))}"}), 400

    integration = create_siem_integration(
        workspace_id=ctx.get("workspace_id"),
        provider=provider,
        name=name,
        endpoint_url=endpoint_url,
        auth_type=(data.get("auth_type") or "token").strip().lower(),
        api_token=data.get("api_token"),
        username=data.get("username"),
        password=data.get("password"),
        custom_headers=data.get("custom_headers") or {},
        event_filters=data.get("event_filters") or ["audit", "anomaly", "incident", "dlp"],
        log_level=(data.get("log_level") or "all").strip().lower(),
        batch_size=int(data.get("batch_size", 100)),
        enabled=bool(data.get("enabled", True)),
    )
    return jsonify({"ok": True, "integration": _integration_to_dict(integration)}), 201


@siem_bp.route("/siem/integrations/<integration_id>", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def get_siem_integration_endpoint(integration_id: str):
    """Fetch a single SIEM integration."""
    ctx = g.user
    integration = get_siem_integration(integration_id, workspace_id=ctx.get("workspace_id"))
    if not integration:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "integration": _integration_to_dict(integration)})


@siem_bp.route("/siem/integrations/<integration_id>", methods=["PATCH"])
@require_auth
@require_workspace_role("ADMIN")
def update_siem_integration_endpoint(integration_id: str):
    """Update a SIEM integration."""
    ctx = g.user
    integration = get_siem_integration(integration_id, workspace_id=ctx.get("workspace_id"))
    if not integration:
        return jsonify({"ok": False, "error": "not found"}), 404

    data = request.get_json(silent=True) or {}
    data.get("provider") and (data.get("provider") or "").strip().lower() not in _ALLOWED_PROVIDERS

    integration = update_siem_integration(
        integration,
        name=data.get("name"),
        provider=data.get("provider"),
        endpoint_url=data.get("endpoint_url"),
        auth_type=data.get("auth_type"),
        api_token=data.get("api_token"),
        username=data.get("username"),
        password=data.get("password"),
        custom_headers=data.get("custom_headers"),
        event_filters=data.get("event_filters"),
        log_level=data.get("log_level"),
        batch_size=data.get("batch_size"),
        enabled=data.get("enabled"),
    )
    return jsonify({"ok": True, "integration": _integration_to_dict(integration)})


@siem_bp.route("/siem/integrations/<integration_id>", methods=["DELETE"])
@require_auth
@require_workspace_role("ADMIN")
def delete_siem_integration_endpoint(integration_id: str):
    """Delete a SIEM integration."""
    ctx = g.user
    deleted = delete_siem_integration(integration_id, workspace_id=ctx.get("workspace_id"))
    if not deleted:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True})


@siem_bp.route("/siem/integrations/<integration_id>/test", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def test_siem_integration_endpoint(integration_id: str):
    """Send a test event to a SIEM integration."""
    ctx = g.user
    exporter = SiemExporter(ctx.get("workspace_id"))
    result = exporter.send_test_event(integration_id)
    return jsonify({"ok": result.get("ok", False), **result}), 200 if result.get("ok") else 502


# --- Export logs --------------------------------------------------------------

@siem_bp.route("/siem/export-logs", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def list_siem_export_logs_endpoint():
    """List recent SIEM export attempts for the current workspace."""
    ctx = g.user
    integration_id = request.args.get("integration_id")
    event_type = request.args.get("event_type")
    limit = min(1000, max(1, request.args.get("limit", 100, type=int)))
    rows = list_siem_export_logs(
        ctx.get("workspace_id"),
        integration_id=integration_id,
        event_type=event_type,
        limit=limit,
    )
    return jsonify({"ok": True, "logs": [_export_log_to_dict(log) for log in rows]})


# --- Public export helpers for other modules ----------------------------------

def export_audit_event(workspace_id: str, action: str, metadata: dict[str, Any]) -> None:
    """Fire an audit event to enabled SIEM integrations (best-effort)."""
    try:
        SiemExporter(workspace_id).export_event("audit", {"action": action, "metadata": metadata})
    except Exception:
        pass


def export_anomaly_event(workspace_id: str, anomaly_id: str, data: dict[str, Any]) -> None:
    """Fire an anomaly event to enabled SIEM integrations (best-effort)."""
    try:
        SiemExporter(workspace_id).export_event("anomaly", data, event_id=anomaly_id)
    except Exception:
        pass


def export_incident_event(workspace_id: str, incident_id: str, data: dict[str, Any]) -> None:
    """Fire an incident event to enabled SIEM integrations (best-effort)."""
    try:
        SiemExporter(workspace_id).export_event("incident", data, event_id=incident_id)
    except Exception:
        pass


def export_dlp_event(workspace_id: str, event_id: str | None, data: dict[str, Any]) -> None:
    """Fire a DLP event to enabled SIEM integrations (best-effort)."""
    try:
        SiemExporter(workspace_id).export_event("dlp", data, event_id=event_id)
    except Exception:
        pass
