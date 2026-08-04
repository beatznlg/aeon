"""Regression coverage for the tenant-scoped sector contract."""

from __future__ import annotations

import uuid


def _register(client, label: str) -> tuple[str, str]:
    """Create a test workspace owner and return (token, workspace_id)."""
    response = client.post(
        "/auth/register",
        json={
            "email": f"sector-{label}-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": f"Sector {label}",
        },
    )
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_sector_catalog_exposes_registered_contract(client):
    token, _workspace_id = _register(client, "catalog")

    response = client.get("/sectors/catalog", headers=_headers(token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["tool_count"] == 40
    assert data["aliases"]["cultural_heritage"] == "heritage"

    sectors = {sector["id"]: sector for sector in data["sectors"]}
    assert set(sectors) == {
        "cybersecurity",
        "finance",
        "health",
        "heritage",
        "manufacturing",
        "retail",
        "sme",
        "tourism",
        "transport",
        "utilities",
    }
    heritage_tools = {tool["id"] for tool in sectors["heritage"]["tools"]}
    assert heritage_tools == {"visitors", "sites", "exhibitions", "tours"}
    assert "cultural_heritage" in sectors["heritage"]["aliases"]


def test_unknown_sector_tool_is_rejected_consistently(client):
    token, _workspace_id = _register(client, "unknown")
    headers = _headers(token)

    get_response = client.get("/sectors/data/health/not-a-tool", headers=headers)
    post_response = client.post(
        "/sectors/data/health/not-a-tool",
        headers=headers,
        json={},
    )

    assert get_response.status_code == 404
    assert get_response.get_json() == {
        "ok": False,
        "error": "unknown sector tool",
        "sector": "health",
        "tool": "not-a-tool",
    }
    assert post_response.status_code == 404
    assert post_response.get_json()["error"] == "unknown sector tool"


def test_dataset_upsert_enforces_registered_shape_and_accepts_alias(client):
    token, _workspace_id = _register(client, "validation")
    headers = _headers(token)

    invalid = client.post(
        "/sectors/data/health/vitals",
        headers=headers,
        json={"patient_id": "P-1"},
    )
    assert invalid.status_code == 400
    assert "must be a JSON array" in invalid.get_json()["error"]

    valid = client.post(
        "/sectors/data/cultural_heritage/sites",
        headers=headers,
        json=[{"site": "Test Site", "conservation_status": "good"}],
    )
    assert valid.status_code == 201
    assert valid.get_json()["ok"] is True

    aliased_read = client.get(
        "/sectors/data/cultural_heritage/sites",
        headers=headers,
    )
    canonical_read = client.get("/sectors/data/heritage/sites", headers=headers)
    assert aliased_read.status_code == 200
    assert canonical_read.status_code == 200
    assert aliased_read.get_json()["sites"] == [{"site": "Test Site", "conservation_status": "good"}]
    assert canonical_read.get_json()["sites"] == aliased_read.get_json()["sites"]


def test_sector_data_is_isolated_between_workspaces(client):
    owner_a, workspace_a = _register(client, "isolation-a")
    owner_b, workspace_b = _register(client, "isolation-b")
    assert workspace_a != workspace_b

    custom_data = [{"id": "ONLY-WORKSPACE-A", "severity": "low"}]
    saved = client.post(
        "/sectors/data/cybersecurity/threats",
        headers=_headers(owner_a),
        json=custom_data,
    )
    assert saved.status_code == 201

    read_a = client.get(
        "/sectors/data/cybersecurity/threats",
        headers=_headers(owner_a),
    )
    read_b = client.get(
        "/sectors/data/cybersecurity/threats",
        headers=_headers(owner_b),
    )

    assert read_a.status_code == 200
    assert read_b.status_code == 200
    assert read_a.get_json()["threats"] == custom_data
    assert all(item.get("id") != "ONLY-WORKSPACE-A" for item in read_b.get_json()["threats"])
