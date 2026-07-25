"""Tests for authentication endpoints."""

import json


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
