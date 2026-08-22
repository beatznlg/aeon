"""Tests for public health and readiness endpoints."""

import json


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["backend"] == "aeon_python_kernel"


def test_live_returns_alive(client):
    resp = client.get("/live")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["status"] == "alive"


def test_versioned_health_probes_preserve_contract(client):
    for path in ("/api/v1/health", "/api/v1/live", "/api/v1/ready"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["X-AEON-API-Version"] == "1"
        assert response.headers["X-Request-ID"].startswith("aeon-")


def test_legacy_health_probe_advertises_api_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-AEON-API-Version"] == "1"


def test_request_id_is_generated_and_returned(client):
    resp = client.get("/health")
    request_id = resp.headers.get("X-Request-ID")
    assert resp.status_code == 200
    assert request_id
    assert request_id.startswith("aeon-")


def test_request_id_is_preserved_for_distributed_tracing(client):
    request_id = "proxy-request-123"
    resp = client.get("/health", headers={"X-Request-ID": request_id})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == request_id


def test_invalid_request_id_is_replaced(client):
    resp = client.get("/health", headers={"X-Request-ID": "bad id value"})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"].startswith("aeon-")


def test_ready_returns_environment_report(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert "environment" in data
    assert "agents_loaded" in data
    assert "queue_size" in data


def test_operations_snapshot_requires_auth(client):
    resp = client.get("/operations/snapshot")
    assert resp.status_code == 401


def test_operations_snapshot_is_workspace_scoped_and_count_only(client):
    registration = client.post(
        "/auth/register",
        json={
            "email": "operations-viewer@test.local",
            "password": "secure123",
            "name": "Operations Viewer",
        },
    )
    assert registration.status_code == 201
    token = registration.get_json()["token"]
    workspace_id = registration.get_json()["user"]["workspace_id"]

    resp = client.get(
        "/operations/snapshot",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["workspace_id"] == workspace_id
    assert data["runtime"]["backend"] == "aeon_python_kernel"
    assert data["agent"]["app_id"] == f"ws-{workspace_id}"
    assert data["memory"]["episodic_events"] == 0
    assert data["goals"]["open"] == 0
    assert data["worker"]["pending"] >= 0
    assert data["automations"]["policies"]["total"] == 0
    assert data["automations"]["budgets"]["total"] == 0
    assert data["automations"]["executions_last_24h"] == 0
    assert data["ai_ledger"]["ok"] is True
    assert data["ai_ledger"]["total_records"] == 0
    assert data["ai_ledger"]["daily"] == []
    assert data["dead_letters"]["total"] == 0
    assert data["dead_letters"]["recent"] == []
    assert "results" not in data["worker"]


def test_operations_snapshot_includes_workspace_ai_execution_summary(client):
    registration = client.post(
        "/auth/register",
        json={
            "email": "operations-ai@test.local",
            "password": "secure123",
            "name": "AI Operations Viewer",
        },
    )
    assert registration.status_code == 201
    token = registration.get_json()["token"]

    resp = client.get(
        "/operations/snapshot",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    ledger = resp.get_json()["ai_ledger"]
    assert ledger["ok"] is True
    assert ledger["days"] == 30
    assert set(("total_records", "total_executions", "total_tokens", "daily")) <= set(ledger)


def test_operations_snapshot_rejects_another_agent_key(client):
    registration = client.post(
        "/auth/register",
        json={
            "email": "operations-scope@test.local",
            "password": "secure123",
            "name": "Scope Viewer",
        },
    )
    assert registration.status_code == 201
    token = registration.get_json()["token"]

    resp = client.get(
        "/operations/snapshot?app_id=other-agent",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 403
    assert resp.get_json()["error"] == "app_id must match the workspace agent"
