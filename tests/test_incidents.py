"""Tests for Phase 46 incident response and runbooks."""

import uuid

import pytest

from aeon_db import (
    Workspace,
    create_anomaly,
    create_incident,
    create_incident_runbook,
    get_db,
    get_incident,
    update_incident,
)
from aeon_incidents import (
    _runbook_matches,
    handle_anomaly,
)


@pytest.fixture
def workspace_id(client):
    db = get_db()
    slug = f"incident-test-{uuid.uuid4().hex[:8]}"
    with db.session() as s:
        ws = Workspace(slug=slug, name="Incident Test", plan="enterprise")
        s.add(ws)
        s.commit()
        return str(ws.id)


def _auth_headers(client, workspace_id):
    """Register a user, add them to the workspace, and return auth headers."""
    email = f"incident-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Incident Tester"},
    )
    if resp.status_code == 201:
        token = resp.json["token"]
    else:
        resp = client.post(
            "/auth/login",
            json={"email": email, "password": "secure123"},
        )
        token = resp.json["token"]

    db = get_db()
    from aeon_db import Membership, User

    with db.session() as s:
        user = s.query(User).filter(User.email == email).first()
        if user:
            existing = (
                s.query(Membership)
                .filter(Membership.workspace_id == str(workspace_id), Membership.user_id == user.id)
                .first()
            )
            if not existing:
                s.add(Membership(workspace_id=str(workspace_id), user_id=user.id, role="ADMIN"))
                s.commit()

    return {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(workspace_id)}


@pytest.fixture
def runbook(workspace_id):
    return create_incident_runbook(
        workspace_id=workspace_id,
        name="Test Runbook",
        triggers=[{"anomaly_type": "automation_failure_spike"}],
        actions=[{"type": "notify", "target": "admins"}],
    )


@pytest.fixture
def anomaly(workspace_id):
    return create_anomaly(
        workspace_id=workspace_id,
        anomaly_type="automation_failure_spike",
        severity="critical",
        title="Failure spike",
    )


def test_runbook_matches(runbook):
    assert _runbook_matches(runbook, "automation_failure_spike", "critical") is True
    assert _runbook_matches(runbook, "other_type", "critical") is False
    assert _runbook_matches(runbook, "automation_failure_spike", "warning") is True


def test_runbook_disabled_does_not_match(workspace_id):
    rb = create_incident_runbook(
        workspace_id=workspace_id,
        name="Disabled Runbook",
        triggers=[{"anomaly_type": "*"}],
        actions=[],
        enabled=False,
    )
    assert _runbook_matches(rb, "anything", "critical") is False


def test_handle_anomaly_creates_incident(workspace_id, runbook, anomaly):
    result = handle_anomaly(anomaly)
    assert result["ok"] is True
    assert result["incident_created"] is True
    assert result["matched_runbooks"] == 1
    incident = get_incident(result["incident_id"])
    assert incident is not None
    assert incident.workspace_id == workspace_id


def test_handle_anomaly_no_match(workspace_id, anomaly):
    create_incident_runbook(
        workspace_id=workspace_id,
        name="No Match Runbook",
        triggers=[{"anomaly_type": "other"}],
        actions=[],
    )
    result = handle_anomaly(anomaly)
    assert result["ok"] is True
    assert result["incident_created"] is False


def test_update_incident_status(workspace_id):
    incident = create_incident(
        workspace_id=workspace_id,
        title="Test incident",
        severity="warning",
        status="open",
    )
    updated = update_incident(incident, status="resolved")
    assert updated.status == "resolved"
    assert updated.resolved_at is not None


def test_create_incident_runbook(workspace_id):
    rb = create_incident_runbook(
        workspace_id=workspace_id,
        name="Runbook",
        triggers=[{"anomaly_type": "audit_volume_spike"}],
        actions=[{"type": "webhook", "url": "https://example.com/hook"}],
    )
    assert rb.workspace_id == workspace_id
    assert rb.enabled is True


# --- API route tests ---


def test_api_runbook_crud(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    resp = client.get("/runbooks", headers=headers)
    assert resp.status_code == 200
    assert resp.json["ok"] is True

    resp = client.post(
        "/runbooks",
        json={
            "name": "My Runbook",
            "triggers": [{"anomaly_type": "*"}],
            "actions": [{"type": "notify", "target": "admins"}],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    runbook = resp.json["runbook"]
    assert runbook["name"] == "My Runbook"

    resp = client.patch(
        f"/runbooks/{runbook['id']}",
        json={"name": "Updated Runbook"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json["runbook"]["name"] == "Updated Runbook"

    resp = client.delete(f"/runbooks/{runbook['id']}", headers=headers)
    assert resp.status_code == 200


def test_api_incident_crud(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    resp = client.post(
        "/incidents",
        json={"title": "Manual incident", "severity": "warning"},
        headers=headers,
    )
    assert resp.status_code == 201
    incident = resp.json["incident"]
    assert incident["title"] == "Manual incident"

    resp = client.patch(
        f"/incidents/{incident['id']}",
        json={"status": "resolved"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json["incident"]["status"] == "resolved"
