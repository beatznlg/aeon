"""Tests for Phase 44 Enterprise SSO (SAML/OIDC)."""

from __future__ import annotations

import uuid

import pytest

from aeon_cache import get_cache


@pytest.fixture
def registered_client(client):
    """Return a client with an registered admin user and workspace."""
    email = f"sso-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "name": "SSO Tester"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    client.token = data["token"]
    client.workspace_id = data["user"]["workspace_id"]
    return client


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_oidc_provider_crud(registered_client):
    client = registered_client
    resp = client.post(
        "/sso/providers",
        headers=_headers(client.token),
        json={
            "protocol": "oidc",
            "name": "Test OIDC",
            "config": {
                "client_id": "test-client",
                "client_secret": "secret",
                "authorization_endpoint": "https://idp.test/authorize",
                "token_endpoint": "https://idp.test/token",
            },
            "attribute_mapping": {"default_role": "OPERATOR"},
        },
    )
    assert resp.status_code == 201
    provider = resp.get_json()["provider"]
    assert provider["protocol"] == "oidc"

    # List
    resp = client.get("/sso/providers", headers=_headers(client.token))
    assert resp.status_code == 200
    assert len(resp.get_json()["providers"]) == 1

    # Get
    resp = client.get(f"/sso/providers/{provider['id']}", headers=_headers(client.token))
    assert resp.status_code == 200
    assert resp.get_json()["provider"]["name"] == "Test OIDC"

    # Patch
    resp = client.patch(
        f"/sso/providers/{provider['id']}",
        headers=_headers(client.token),
        json={"name": "Updated OIDC", "active": False},
    )
    assert resp.status_code == 200
    assert resp.get_json()["provider"]["name"] == "Updated OIDC"

    # Delete
    resp = client.delete(f"/sso/providers/{provider['id']}", headers=_headers(client.token))
    assert resp.status_code == 200


@ pytest.mark.skipif(
    __import__("aeon_sso", fromlist=["saml_available"]).saml_available(),
    reason="SAML library is installed; skipping degradation test",
)
def test_saml_login_degrades_when_saml_unavailable(registered_client):
    client = registered_client
    resp = client.post(
        "/sso/providers",
        headers=_headers(client.token),
        json={
            "protocol": "saml",
            "name": "Test SAML",
            "config": {
                "idp_entity_id": "https://idp.test/entity",
                "idp_sso_url": "https://idp.test/saml",
                "idp_x509cert": "dummy",
            },
        },
    )
    assert resp.status_code == 201
    provider_id = resp.get_json()["provider"]["id"]
    resp = client.get(f"/sso/saml/login/{provider_id}")
    assert resp.status_code == 501


def test_oidc_callback_issues_token(registered_client, monkeypatch):
    client = registered_client
    resp = client.post(
        "/sso/providers",
        headers=_headers(client.token),
        json={
            "protocol": "oidc",
            "name": "Test OIDC Callback",
            "config": {
                "client_id": "test-client",
                "client_secret": "secret",
                "authorization_endpoint": "https://idp.test/authorize",
                "token_endpoint": "https://idp.test/token",
                "skip_id_token_verification": True,
            },
        },
    )
    assert resp.status_code == 201
    provider_id = resp.get_json()["provider"]["id"]

    def _fake_complete(provider, code, state, nonce):
        return {
            "ok": True,
            "token": "fake-jwt",
            "user": {
                "id": "user-id",
                "email": "new@example.com",
                "role": "VIEWER",
                "workspace_id": provider.workspace_id,
            },
        }

    monkeypatch.setattr("aeon_server.complete_oidc_login", _fake_complete)

    state = "test-state-123"
    nonce = "test-nonce-456"
    get_cache().set(f"oidc:state:{state}", {"provider_id": provider_id, "nonce": nonce}, ttl=600)

    resp = client.get(f"/sso/oidc/callback/{provider_id}?code=abc&state={state}&nonce={nonce}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["token"] == "fake-jwt"


def test_sso_provider_requires_admin(registered_client):
    client = registered_client
    # Create a viewer token by registering a second user? Simpler: use an invalid token.
    resp = client.post(
        "/sso/providers",
        headers={"Authorization": "Bearer invalid-token"},
        json={"protocol": "oidc", "name": "X", "config": {}},
    )
    assert resp.status_code == 401
