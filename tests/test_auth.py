"""Tests for authentication endpoints."""

import json
from types import SimpleNamespace

import pytest

from aeon_auth import can_access_workspace


def test_register_creates_user_and_returns_token(client):
    payload = {
        "email": "alice@test.local",
        "password": "secure123",
        "name": "Alice",
    }
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert "token" in data
    assert data["user"]["email"] == "alice@test.local"


def test_register_rejects_duplicate_email(client):
    payload = {"email": "bob@test.local", "password": "secure123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 409
    data = json.loads(resp.data)
    assert data["ok"] is False


def test_login_with_fallback_admin(client):
    resp = client.post(
        "/auth/login",
        json={"email": "admin@test.local", "password": "adminpass"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert "token" in data


def test_login_rejects_invalid_credentials(client):
    resp = client.post(
        "/auth/login",
        json={"email": "admin@test.local", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_auth_me_returns_user_profile(client):
    # Register a user and use the returned token.
    resp = client.post(
        "/auth/register",
        json={"email": "charlie@test.local", "password": "secure123", "name": "Charlie"},
    )
    token = json.loads(resp.data)["token"]
    resp2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    data = json.loads(resp2.data)
    assert data["ok"] is True
    assert data["user"]["email"] == "charlie@test.local"
    assert "workspace" in data["user"]


def test_protected_route_rejects_missing_token(client):
    resp = client.get("/workspaces")
    assert resp.status_code == 401


def test_production_auth_does_not_use_dev_secret(monkeypatch):
    import aeon_auth

    monkeypatch.setenv("AEON_ENV", "production")
    monkeypatch.delenv("AEON_JWT_SECRET", raising=False)
    monkeypatch.delenv("NEXTAUTH_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="must be configured"):
        aeon_auth._resolve_jwt_secret()


def test_fallback_admin_is_disabled_in_production(monkeypatch):
    import aeon_auth

    monkeypatch.setenv("AEON_ENV", "production")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@test.local")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "scrypt:32768:8:1$test$not-a-valid-production-login")

    assert aeon_auth._FallbackAdmin.matches("admin@test.local", "adminpass") is False


def test_production_workspace_access_fails_closed_on_db_error(monkeypatch):
    class BrokenDatabase:
        def get_membership(self, workspace_id, user_id):
            raise RuntimeError("database unavailable")

    monkeypatch.setenv("AEON_ENV", "production")
    monkeypatch.setattr("aeon_db.get_db", lambda: BrokenDatabase())

    assert can_access_workspace("user-1", "workspace-1") is False


def test_sso_provider_detail_does_not_cross_workspace(client, monkeypatch):
    registration = client.post(
        "/auth/register",
        json={"email": "sso-scope@test.local", "password": "secure123", "name": "SSO Scope"},
    )
    assert registration.status_code == 201
    token = registration.get_json()["token"]
    workspace_id = registration.get_json()["user"]["workspace_id"]

    monkeypatch.setattr(
        "aeon_server._get_sso_provider",
        lambda _provider_id: SimpleNamespace(
            id="provider-other-workspace",
            workspace_id="workspace-other",
            protocol="oidc",
            name="Other workspace",
            active=True,
            config={},
            attribute_mapping={},
        ),
    )

    response = client.get(
        "/sso/providers/provider-other-workspace",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.get_json()["error"] == "provider not found"
    assert workspace_id != "workspace-other"


def test_protected_route_accepts_valid_token(client):
    resp = client.post(
        "/auth/register",
        json={"email": "dave@test.local", "password": "secure123", "name": "Dave"},
    )
    token = json.loads(resp.data)["token"]
    resp2 = client.get("/workspaces", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    data = json.loads(resp2.data)
    assert data["ok"] is True
    assert "workspaces" in data
