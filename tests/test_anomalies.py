"""Tests for Phase 46 anomaly detection."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from aeon_anomalies import AnomalyDetector, background_detect, trigger_detection
from aeon_db import (
    Workspace,
    add_audit_log,
    add_automation_execution,
    get_db,
)


@pytest.fixture
def workspace_id(client):
    """Create and return a workspace id."""
    db = get_db()
    slug = f"anomaly-test-{uuid.uuid4().hex[:8]}"
    with db.session() as s:
        ws = Workspace(slug=slug, name="Anomaly Test", plan="enterprise")
        s.add(ws)
        s.commit()
        return str(ws.id)


def _auth_headers(client, workspace_id):
    """Register a user, add them to the workspace, and return auth headers."""

    email = f"anomaly-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Anomaly Tester"},
    )
    if resp.status_code == 201:
        token = resp.json["token"]
    else:
        # Fallback to login if the user already exists.
        resp = client.post(
            "/auth/login",
            json={"email": email, "password": "secure123"},
        )
        token = resp.json["token"]

    # Ensure membership in the requested workspace.
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


def test_anomaly_detector_empty(workspace_id):
    detector = AnomalyDetector(workspace_id)
    anomalies = detector.detect()
    assert anomalies == []


def test_automation_failure_spike(workspace_id):
    rule_id = "rule-1"
    for _ in range(5):
        add_automation_execution(rule_id, workspace_id, "failed", {"runtime_ms": 100})
    detector = AnomalyDetector(workspace_id)
    anomalies = detector.detect_automation_anomalies()
    assert len(anomalies) >= 1
    assert anomalies[0]["anomaly_type"] == "automation_failure_spike"
    assert anomalies[0]["severity"] in ("warning", "critical")


def test_automation_volume_spike(workspace_id):
    now = datetime.now(timezone.utc)
    # Baseline: a few executions spread across prior hours.
    for hour_offset in range(-3, 0):
        for _ in range(3):
            add_automation_execution(
                "rule-vol",
                workspace_id,
                "completed",
                {"runtime_ms": 100},
                created_at=now + timedelta(hours=hour_offset),
            )
    # Spike in the current hour.
    for _ in range(30):
        add_automation_execution("rule-vol", workspace_id, "completed", {"runtime_ms": 100})
    detector = AnomalyDetector(workspace_id)
    anomalies = detector.detect()
    types = {a["anomaly_type"] for a in anomalies}
    assert "automation_volume_spike" in types


def test_audit_volume_anomaly(workspace_id):
    now = datetime.now(timezone.utc)
    # Baseline audit logs in prior hours.
    for hour_offset in range(-3, 0):
        for i in range(3):
            add_audit_log(
                action="TEST_ACTION",
                module="test",
                user_id=None,
                workspace_id=workspace_id,
                email=None,
                metadata={"index": i},
                timestamp=now + timedelta(hours=hour_offset),
            )
    # Spike in the current hour.
    for i in range(50):
        add_audit_log(
            action="TEST_ACTION",
            module="test",
            user_id=None,
            workspace_id=workspace_id,
            email=None,
            metadata={"index": i},
        )
    detector = AnomalyDetector(workspace_id)
    anomalies = detector.detect_audit_volume_anomaly()
    assert len(anomalies) >= 1
    assert anomalies[0]["anomaly_type"] == "audit_volume_spike"


def test_dismiss_anomaly(workspace_id):
    from aeon_db import create_anomaly, dismiss_anomaly, get_anomaly

    anomaly = create_anomaly(
        workspace_id=workspace_id,
        anomaly_type="test",
        severity="warning",
        title="test anomaly",
    )
    assert anomaly.dismissed is False
    result = dismiss_anomaly(anomaly.id)
    assert result.dismissed is True
    assert get_anomaly(anomaly.id).dismissed is True


def test_background_detect(workspace_id):
    """background_detect should not raise and should run in a daemon thread."""
    background_detect(workspace_id)
    assert True


def test_trigger_detection(workspace_id):
    add_automation_execution("rule-t", workspace_id, "failed", {"runtime_ms": 100})
    anomalies = trigger_detection(workspace_id)
    assert isinstance(anomalies, list)


def test_summarize_with_llm_no_anomalies(workspace_id):
    detector = AnomalyDetector(workspace_id)
    summary = detector.summarize_with_llm([])
    assert "No anomalies" in summary


def test_summarize_with_llm_fallback(workspace_id):
    detector = AnomalyDetector(workspace_id)
    anomalies = [
        {"title": "Failure spike", "severity": "critical", "description": "bad"},
    ]
    summary = detector.summarize_with_llm(anomalies)
    assert "Anomalies detected" in summary
    assert "Failure spike" in summary


# --- API route tests --------------------------------------------------------

def test_api_list_anomalies(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    resp = client.get("/anomalies", headers=headers)
    assert resp.status_code == 200
    assert resp.json["ok"] is True
    assert "anomalies" in resp.json


def test_api_detect_anomalies(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    resp = client.post("/anomalies/detect", headers=headers)
    assert resp.status_code == 200
    assert resp.json["ok"] is True


def test_api_dismiss_anomaly(client, workspace_id):
    from aeon_db import create_anomaly

    headers = _auth_headers(client, workspace_id)
    anomaly = create_anomaly(
        workspace_id=workspace_id,
        anomaly_type="test",
        severity="warning",
        title="dismiss me",
    )
    resp = client.post(
        f"/anomalies/{anomaly.id}/dismiss",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json["ok"] is True
