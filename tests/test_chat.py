"""Tests for the /chat endpoint."""

import json


def _register_and_get_token(client, email):
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Test"},
    )
    return json.loads(resp.data)["token"]


def test_chat_requires_query(client):
    token = _register_and_get_token(client, "chat1@test.local")
    resp = client.post(
        "/chat",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data["ok"] is False


def test_chat_returns_agent_response(client):
    token = _register_and_get_token(client, "chat2@test.local")
    resp = client.post(
        "/chat",
        json={"query": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert "data" in data
    assert "backend" in data


def test_chat_requires_auth(client):
    resp = client.post("/chat", json={"query": "hello"})
    assert resp.status_code == 401
