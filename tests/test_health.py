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


def test_ready_returns_environment_report(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert "environment" in data
    assert "agents_loaded" in data
    assert "queue_size" in data
