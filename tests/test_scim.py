"""Tests for Phase 44 SCIM 2.0 provisioning."""

from __future__ import annotations

import pytest

from aeon_db import get_db
from aeon_scim import create_scim_token


@pytest.fixture
def workspace_client(client):
    """Return a client with a workspace and helper token."""
    import uuid

    email = f"scim-admin-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "name": "SCIM Admin"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    client.token = data["token"]
    client.workspace_id = data["user"]["workspace_id"]
    return client


def test_scim_create_and_list_user(workspace_client):
    workspace_id = workspace_client.workspace_id
    plain_token, _ = create_scim_token(workspace_id, "test token")

    resp = workspace_client.post(
        "/scim/v2/Users",
        headers={"Authorization": f"Bearer {plain_token}"},
        json={
            "userName": "provisioned@test.local",
            "name": {"formatted": "Provisioned User"},
            "emails": [{"value": "provisioned@test.local", "primary": True}],
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["userName"] == "provisioned@test.local"

    resp = workspace_client.get(
        "/scim/v2/Users",
        headers={"Authorization": f"Bearer {plain_token}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["totalResults"] >= 1


def test_scim_filter_user(workspace_client):
    workspace_id = workspace_client.workspace_id
    plain_token, _ = create_scim_token(workspace_id, "test token")
    workspace_client.post(
        "/scim/v2/Users",
        headers={"Authorization": f"Bearer {plain_token}"},
        json={
            "userName": "filterme@test.local",
            "emails": [{"value": "filterme@test.local", "primary": True}],
        },
    )
    resp = workspace_client.get(
        "/scim/v2/Users?filter=userName eq \"filterme@test.local\"",
        headers={"Authorization": f"Bearer {plain_token}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["totalResults"] >= 1


def test_scim_deactivate_user(workspace_client):
    workspace_id = workspace_client.workspace_id
    plain_token, _ = create_scim_token(workspace_id, "test token")
    resp = workspace_client.post(
        "/scim/v2/Users",
        headers={"Authorization": f"Bearer {plain_token}"},
        json={
            "userName": "deactivateme@test.local",
            "emails": [{"value": "deactivateme@test.local", "primary": True}],
        },
    )
    assert resp.status_code == 201
    user_id = resp.get_json()["id"]

    resp = workspace_client.patch(
        f"/scim/v2/Users/{user_id}",
        headers={"Authorization": f"Bearer {plain_token}"},
        json={
            "Operations": [
                {"op": "Replace", "path": "active", "value": False},
            ]
        },
    )
    assert resp.status_code == 200
    # Membership should be removed after deactivation.
    db = get_db()
    membership = db.get_membership(workspace_id, user_id)
    assert membership is None


def test_scim_unauthorized_without_token(workspace_client):
    resp = workspace_client.get("/scim/v2/Users")
    assert resp.status_code == 401
