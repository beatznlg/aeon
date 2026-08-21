"""Tests for authentication endpoints."""

import json
from types import SimpleNamespace

import pytest
from flask import Flask

import aeon_auth
from aeon_auth import can_access_workspace, has_permission, require_permission


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


def test_named_permission_matrix_is_explicit():
    assert has_permission("VIEWER", "workspace.read") is True
    assert has_permission("VIEWER", "billing.manage") is False
    assert has_permission("OPERATOR", "automation.execute") is True
    assert has_permission("ADMIN", "billing.manage") is True
    assert has_permission("OWNER", "audit.read") is True
    assert has_permission("ADMIN", "unknown.permission") is False


def test_named_permission_decorator_enforces_membership_and_role(client):
    registration = client.post(
        "/auth/register",
        json={"email": "permission-owner@test.local", "password": "secure123", "name": "Permission Owner"},
    )
    token = registration.get_json()["token"]
    own_workspace = registration.get_json()["user"]["workspace_id"]
    other = client.post(
        "/auth/register",
        json={"email": "permission-other@test.local", "password": "secure123", "name": "Permission Other"},
    )
    other_workspace = other.get_json()["user"]["workspace_id"]

    protected = Flask("permission-regression")

    @protected.get("/secure/<workspace_id>")
    @require_permission("billing.manage")
    def secure_workspace(workspace_id):
        return {"ok": True, "workspace_id": workspace_id}

    with protected.test_client() as permission_client:
        headers = {"Authorization": f"Bearer {token}"}
        assert permission_client.get(f"/secure/{own_workspace}", headers=headers).status_code == 200
        assert permission_client.get(f"/secure/{other_workspace}", headers=headers).status_code == 403

    from aeon_db import get_db

    db = get_db()
    with db.session() as session:
        membership = db.get_membership(own_workspace, registration.get_json()["user"]["id"])
        assert membership is not None
        membership.role = "VIEWER"
        session.merge(membership)
        session.commit()

    with protected.test_client() as permission_client:
        denied = permission_client.get(f"/secure/{own_workspace}", headers={"Authorization": f"Bearer {token}"})
        assert denied.status_code == 403


def test_malformed_and_expired_tokens_are_rejected(client, monkeypatch):
    assert client.get("/workspaces", headers={"Authorization": "Bearer malformed"}).status_code == 401

    monkeypatch.setattr(aeon_auth, "ACCESS_TOKEN_TTL", -1)
    registration = client.post(
        "/auth/register",
        json={"email": "expired-token@test.local", "password": "secure123", "name": "Expired"},
    )
    assert registration.status_code == 201
    expired = registration.get_json()["token"]
    assert client.get("/workspaces", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_per_user_rate_limit_is_enforced_and_isolated(client, monkeypatch):
    import aeon_server
    from aeon_server import RateLimiter

    monkeypatch.setenv("AEON_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setattr(aeon_server, "_rate_limit_window", 60)
    monkeypatch.setattr(
        aeon_server,
        "user_rate_limiter",
        RateLimiter(max_requests=3, window_seconds=60),
    )
    monkeypatch.setattr(
        aeon_server,
        "workspace_rate_limiter",
        RateLimiter(max_requests=10000, window_seconds=60),
    )

    first = client.post(
        "/auth/register",
        json={"email": "rate-user-a@test.local", "password": "secure123", "name": "Rate A"},
    )
    assert first.status_code == 201
    token_a = first.get_json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Registration is an anonymous flow and does not consume the per-user
    # budget, so the three allowed requests are the /workspaces calls. The
    # fourth must be throttled before the route handler runs.
    assert client.get("/workspaces", headers=headers_a).status_code == 200
    assert client.get("/workspaces", headers=headers_a).status_code == 200
    assert client.get("/workspaces", headers=headers_a).status_code == 200
    throttled = client.get("/workspaces", headers=headers_a)
    assert throttled.status_code == 429
    assert throttled.get_json()["scope"] == "user"
    assert throttled.headers.get("Retry-After") is not None

    # A different authenticated identity is not throttled by user A's bucket.
    second = client.post(
        "/auth/register",
        json={"email": "rate-user-b@test.local", "password": "secure123", "name": "Rate B"},
    )
    assert second.status_code == 201
    headers_b = {"Authorization": f"Bearer {second.get_json()['token']}"}
    assert client.get("/workspaces", headers=headers_b).status_code == 200
