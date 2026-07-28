"""Tests for the /automations/metrics endpoints (Phase 39)."""

import json
from unittest import mock

import pytest
import requests as _requests


@pytest.fixture
def viewer_token(client):
    """Register a user and return a JWT with VIEWER role."""
    import uuid as _uuid

    email = f"metrics-viewer-{_uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Metrics Viewer"},
    )
    data = json.loads(resp.data)
    return data["token"]


@pytest.fixture
def sample_executions():
    return [
        {
            "id": "exec-1",
            "rule_id": "rule-1",
            "workspace_id": "ws-123",
            "status": "completed",
            "result": {"runtime_ms": 120},
            "created_at": "2025-07-27T10:00:00Z",
        },
        {
            "id": "exec-2",
            "rule_id": "rule-1",
            "workspace_id": "ws-123",
            "status": "failed",
            "result": {"runtime_ms": 80},
            "created_at": "2025-07-27T11:00:00Z",
        },
        {
            "id": "exec-3",
            "rule_id": "rule-2",
            "workspace_id": "ws-123",
            "status": "completed",
            "result": {"runtime_ms": 200},
            "created_at": "2025-07-26T09:00:00Z",
        },
        {
            "id": "exec-4",
            "rule_id": "rule-1",
            "workspace_id": "ws-123",
            "status": "throttled",
            "result": None,
            "created_at": "2025-07-25T08:00:00Z",
        },
        {
            "id": "exec-5",
            "rule_id": "rule-1",
            "workspace_id": "ws-123",
            "status": "pending_approval",
            "result": None,
            "created_at": "2025-07-24T07:00:00Z",
        },
    ]


def test_automation_metrics_requires_auth(client):
    resp = client.get("/automations/metrics")
    assert resp.status_code == 401


def test_automation_metrics_workspace_aggregates(client, viewer_token, sample_executions, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    with mock.patch.object(_requests, "get") as mock_get:
        mock_resp = mock.Mock()
        mock_resp.json.return_value = sample_executions
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        resp = client.get(
            "/automations/metrics",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["total_runs"] == 5
    assert data["completed_count"] == 2
    assert data["failed_count"] == 1
    assert data["throttled_count"] == 1
    assert data["pending_count"] == 1
    assert data["success_rate"] == 40.0
    assert data["failure_rate"] == 20.0
    assert data["average_runtime_ms"] == 133.33
    assert len(data["top_rules"]) == 2
    assert data["top_rules"][0]["rule_id"] == "rule-1"
    assert data["top_rules"][0]["runs"] == 4


def test_automation_metrics_workspace_returns_zero_when_empty(client, viewer_token, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    with mock.patch.object(_requests, "get") as mock_get:
        mock_resp = mock.Mock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        resp = client.get(
            "/automations/metrics",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["total_runs"] == 0
    assert data["success_rate"] == 0.0
    assert data["daily_counts"] == []


def test_automation_metrics_workspace_limits_days_parameter(client, viewer_token, sample_executions, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    with mock.patch.object(_requests, "get") as mock_get:
        mock_resp = mock.Mock()
        mock_resp.json.return_value = sample_executions
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        resp = client.get(
            "/automations/metrics?days=7",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["days"] == 7

    # Verify the query was forwarded to Supabase with a date filter
    call_args = mock_get.call_args
    assert call_args.kwargs["params"]["created_at"].startswith("gte.")


def test_automation_metrics_rule_endpoint(client, viewer_token, sample_executions, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    with mock.patch.object(_requests, "get") as mock_get:
        mock_resp = mock.Mock()
        mock_resp.json.return_value = [e for e in sample_executions if e["rule_id"] == "rule-1"]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        resp = client.get(
            "/automations/rule-1/metrics",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["rule_id"] == "rule-1"
    assert data["total_runs"] == 4
    assert data["completed_count"] == 1
    assert data["failed_count"] == 1


def test_automation_metrics_returns_503_when_supabase_missing(client, viewer_token, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    resp = client.get(
        "/automations/metrics",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert resp.status_code == 503
    data = json.loads(resp.data)
    assert data["ok"] is False
    assert "Supabase not configured" in data["error"]


def test_automation_metrics_rule_returns_503_when_supabase_missing(client, viewer_token, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    resp = client.get(
        "/automations/rule-1/metrics",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert resp.status_code == 503
    data = json.loads(resp.data)
    assert data["ok"] is False
    assert "Supabase not configured" in data["error"]


def test_automation_metrics_daily_counts_are_sorted(client, viewer_token, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    executions = [
        {"id": "e1", "rule_id": "r1", "workspace_id": "ws-123", "status": "completed", "result": None, "created_at": "2025-07-28T00:00:00Z"},
        {"id": "e2", "rule_id": "r1", "workspace_id": "ws-123", "status": "completed", "result": None, "created_at": "2025-07-27T00:00:00Z"},
        {"id": "e3", "rule_id": "r1", "workspace_id": "ws-123", "status": "failed", "result": None, "created_at": "2025-07-26T00:00:00Z"},
    ]

    with mock.patch.object(_requests, "get") as mock_get:
        mock_resp = mock.Mock()
        mock_resp.json.return_value = executions
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        resp = client.get(
            "/automations/metrics",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    data = json.loads(resp.data)
    dates = [d["date"] for d in data["daily_counts"]]
    assert dates == sorted(dates)
