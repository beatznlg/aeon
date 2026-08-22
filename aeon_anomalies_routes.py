"""
AEON OS Phase 46 — Anomaly & Incident API routes.

This module is a Flask Blueprint so it can be registered from aeon_server.py
without causing circular imports.
"""

from typing import Any

from flask import Blueprint, g, jsonify, request

from aeon_anomalies import AnomalyDetector
from aeon_auth import require_auth, require_permission
from aeon_db import (
    Anomaly,
    Incident,
    IncidentRunbook,
    create_incident,
    create_incident_runbook,
    delete_incident_runbook,
    dismiss_anomaly,
    get_incident,
    get_incident_runbook,
    list_anomalies,
    list_incident_runbooks,
    list_incidents,
    update_incident,
    update_incident_runbook,
)

anomalies_bp = Blueprint("anomalies", __name__)


# --- Serialization helpers --------------------------------------------------

def _anomaly_to_dict(a: Anomaly) -> dict[str, Any]:
    return {
        "id": a.id,
        "workspace_id": a.workspace_id,
        "anomaly_type": a.anomaly_type,
        "severity": a.severity,
        "title": a.title,
        "description": a.description,
        "score": a.score,
        "source_rule_id": a.source_rule_id,
        "source_metric": a.source_metric,
        "metadata": a.metadata_json,
        "dismissed": a.dismissed,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _incident_to_dict(i: Incident) -> dict[str, Any]:
    return {
        "id": i.id,
        "workspace_id": i.workspace_id,
        "title": i.title,
        "severity": i.severity,
        "status": i.status,
        "root_cause_anomaly_id": i.root_cause_anomaly_id,
        "runbook_id": i.runbook_id,
        "assignee_user_id": i.assignee_user_id,
        "metadata": i.metadata_json,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
        "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
    }


def _runbook_to_dict(rb: IncidentRunbook) -> dict[str, Any]:
    return {
        "id": rb.id,
        "workspace_id": rb.workspace_id,
        "name": rb.name,
        "description": rb.description,
        "triggers": rb.triggers,
        "actions": rb.actions,
        "enabled": rb.enabled,
        "created_at": rb.created_at.isoformat() if rb.created_at else None,
        "updated_at": rb.updated_at.isoformat() if rb.updated_at else None,
    }


# --- Routes ------------------------------------------------------------------

@anomalies_bp.route("/anomalies", methods=["GET"])
@require_auth
@require_permission("incident.read")
def list_anomalies_endpoint():
    """List anomalies for the current workspace."""
    ctx = g.user
    workspace_id = ctx.get("workspace_id")
    dismissed = request.args.get("dismissed")
    severity = request.args.get("severity")
    limit = min(1000, max(1, request.args.get("limit", 100, type=int)))
    if dismissed is not None:
        dismissed = dismissed.lower() in {"true", "1"}
    rows = list_anomalies(workspace_id, dismissed=dismissed, severity=severity, limit=limit)
    return jsonify({"ok": True, "anomalies": [_anomaly_to_dict(a) for a in rows]})


@anomalies_bp.route("/anomalies/detect", methods=["POST"])
@require_auth
@require_permission("incident.manage")
def detect_anomalies_endpoint():
    """Run anomaly detection for the current workspace."""
    ctx = g.user
    workspace_id = ctx.get("workspace_id")
    detector = AnomalyDetector(workspace_id)
    anomalies = detector.detect()
    return jsonify({"ok": True, "anomalies": anomalies})


@anomalies_bp.route("/anomalies/<anomaly_id>/dismiss", methods=["POST"])
@require_auth
@require_permission("incident.manage")
def dismiss_anomaly_endpoint(anomaly_id: str):
    """Dismiss an anomaly as a false positive."""
    anomaly = dismiss_anomaly(anomaly_id, workspace_id=g.workspace_id)
    if not anomaly:
        return jsonify({"ok": False, "error": "anomaly not found"}), 404
    return jsonify({"ok": True, "anomaly": _anomaly_to_dict(anomaly)})


@anomalies_bp.route("/incidents", methods=["GET"])
@require_auth
@require_permission("incident.read")
def list_incidents_endpoint():
    """List incidents for the current workspace."""
    ctx = g.user
    workspace_id = ctx.get("workspace_id")
    status = request.args.get("status")
    limit = min(1000, max(1, request.args.get("limit", 100, type=int)))
    rows = list_incidents(workspace_id, status=status, limit=limit)
    return jsonify({"ok": True, "incidents": [_incident_to_dict(i) for i in rows]})


@anomalies_bp.route("/incidents", methods=["POST"])
@require_auth
@require_permission("incident.manage")
def create_incident_endpoint():
    """Manually create an incident."""
    ctx = g.user
    workspace_id = ctx.get("workspace_id")
    data = request.json or {}
    title = (data.get("title") or "").strip()
    severity = (data.get("severity") or "warning").strip().lower()
    if not title:
        return jsonify({"ok": False, "error": "title is required"}), 400
    if severity not in {"info", "warning", "critical"}:
        return jsonify({"ok": False, "error": "severity must be info, warning, or critical"}), 400
    incident = create_incident(
        workspace_id=workspace_id,
        title=title,
        severity=severity,
        status=data.get("status", "open"),
        metadata=data.get("metadata", {}),
    )
    return jsonify({"ok": True, "incident": _incident_to_dict(incident)}), 201


@anomalies_bp.route("/incidents/<incident_id>", methods=["PATCH"])
@require_auth
@require_permission("incident.manage")
def update_incident_endpoint(incident_id: str):
    """Update an incident's status and/or assignee."""
    incident = get_incident(incident_id, workspace_id=g.workspace_id)
    if not incident:
        return jsonify({"ok": False, "error": "incident not found"}), 404
    data = request.json or {}
    status = data.get("status")
    assignee = data.get("assignee_user_id")
    if status and status not in {"open", "acknowledged", "resolved", "closed"}:
        return jsonify({"ok": False, "error": "invalid status"}), 400
    update_incident(incident, status=status, assignee_user_id=assignee)
    return jsonify({"ok": True, "incident": _incident_to_dict(incident)})


@anomalies_bp.route("/runbooks", methods=["GET"])
@require_auth
@require_permission("incident.read")
def list_runbooks_endpoint():
    """List incident runbooks for the current workspace."""
    ctx = g.user
    workspace_id = ctx.get("workspace_id")
    rows = list_incident_runbooks(workspace_id)
    return jsonify({"ok": True, "runbooks": [_runbook_to_dict(rb) for rb in rows]})


@anomalies_bp.route("/runbooks", methods=["POST"])
@require_auth
@require_permission("incident.manage")
def create_runbook_endpoint():
    """Create an incident runbook."""
    ctx = g.user
    workspace_id = ctx.get("workspace_id")
    data = request.json or {}
    name = (data.get("name") or "").strip()
    triggers = data.get("triggers") or []
    actions = data.get("actions") or []
    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    if not isinstance(triggers, list) or not isinstance(actions, list):
        return jsonify({"ok": False, "error": "triggers and actions must be lists"}), 400
    runbook = create_incident_runbook(
        workspace_id=workspace_id,
        name=name,
        description=data.get("description"),
        triggers=triggers,
        actions=actions,
        enabled=bool(data.get("enabled", True)),
    )
    return jsonify({"ok": True, "runbook": _runbook_to_dict(runbook)}), 201


@anomalies_bp.route("/runbooks/<runbook_id>", methods=["PATCH"])
@require_auth
@require_permission("incident.manage")
def update_runbook_endpoint(runbook_id: str):
    """Update an incident runbook."""
    runbook = get_incident_runbook(runbook_id, workspace_id=g.workspace_id)
    if not runbook:
        return jsonify({"ok": False, "error": "runbook not found"}), 404
    data = request.json or {}
    triggers = data.get("triggers")
    actions = data.get("actions")
    if triggers is not None and not isinstance(triggers, list):
        return jsonify({"ok": False, "error": "triggers must be a list"}), 400
    if actions is not None and not isinstance(actions, list):
        return jsonify({"ok": False, "error": "actions must be a list"}), 400
    update_incident_runbook(
        runbook,
        name=data.get("name"),
        description=data.get("description"),
        triggers=triggers,
        actions=actions,
        enabled=data.get("enabled"),
    )
    return jsonify({"ok": True, "runbook": _runbook_to_dict(runbook)})


@anomalies_bp.route("/runbooks/<runbook_id>", methods=["DELETE"])
@require_auth
@require_permission("incident.manage")
def delete_runbook_endpoint(runbook_id: str):
    """Delete an incident runbook."""
    if delete_incident_runbook(runbook_id, workspace_id=g.workspace_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "runbook not found"}), 404
