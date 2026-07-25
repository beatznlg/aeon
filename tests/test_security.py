"""Tests for Phase 13 security hardening (headers, CORS, RBAC, rotation)."""

import json


def _register_and_get_token(client, email):
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Test"},
    )
    return json.loads(resp.data)["token"]


def _admin_token(client):
    resp = client.post(
        "/auth/login",
        json={"email": "admin@test.local", "password": "adminpass"},
    )
    return json.loads(resp.data)["token"]


def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Content-Security-Policy" in resp.headers
    assert "Permissions-Policy" in resp.headers


def test_cors_preflight_allowed(client):
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 204
    assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    assert "GET" in resp.headers.get("Access-Control-Allow-Methods", "")


def test_workflows_require_authentication(client):
    resp = client.get("/workflows")
    assert resp.status_code == 401
    data = json.loads(resp.data)
    assert data["ok"] is False


def test_jwt_status_requires_admin(client):
    token = _admin_token(client)
    resp = client.get("/auth/jwt/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert "active_secret_hash" in data
    assert data["algorithm"] == "HS256"


def test_jwt_status_rejects_non_admin(client):
    token = _register_and_get_token(client, "viewer@test.local")
    resp = client.get("/auth/jwt/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_api_key_rotation(client):
    token = _register_and_get_token(client, "keyowner@test.local")
    create_resp = client.post(
        "/api-keys",
        json={"name": "Test Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 200
    created = json.loads(create_resp.data)
    key_id = created["key"]["id"]

    rotate_resp = client.post(
        f"/api-keys/{key_id}/rotate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rotate_resp.status_code == 200
    rotated = json.loads(rotate_resp.data)
    assert rotated["ok"] is True
    assert rotated["key"]["id"] != key_id
    assert "plaintext_key" in rotated
