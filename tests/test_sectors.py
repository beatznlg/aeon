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
    assert data["tool_count"] == 58
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
        "telecom",
        "agriculture",
        "education",
        "public_safety",
        "real_estate",
        "professional",
    }
    heritage_tools = {tool["id"] for tool in sectors["heritage"]["tools"]}
    assert heritage_tools == {"visitors", "sites", "exhibitions", "tours"}
    assert "cultural_heritage" in sectors["heritage"]["aliases"]


def test_frontend_sector_registry_matches_backend():
    """The frontend registry (web/lib/sector-registry.ts) and the backend
    tenant sector catalog must stay in sync after canonicalizing aliases.

    A sector added on one side without the other (or an alias drift) fails
    this suite with a diff of the mismatched ids.
    """
    import re
    from pathlib import Path

    from aeon_sectors import SECTOR_ALIASES, list_sector_catalog

    frontend_path = Path(__file__).resolve().parents[1] / "web" / "lib" / "sector-registry.ts"
    text = frontend_path.read_text(encoding="utf-8")
    frontend_ids = set(re.findall(r'^    id: "([^"]+)"', text, re.MULTILINE))
    assert frontend_ids, "could not extract sector ids from web/lib/sector-registry.ts"

    backend_ids = {sector["id"] for sector in list_sector_catalog()}
    # Normalize frontend ids through the backend's canonical alias map
    # (e.g. cultural_heritage -> heritage).
    frontend_normalized = {SECTOR_ALIASES.get(sector_id, sector_id) for sector_id in frontend_ids}

    assert frontend_normalized == backend_ids, (
        "frontend/backend sector registries drifted — "
        f"frontend-only: {sorted(frontend_normalized - backend_ids)}, "
        f"backend-only: {sorted(backend_ids - frontend_normalized)}"
    )


def test_static_sector_seed_covers_every_registry_tool():
    """The canonical static seed (aeon_seed_sectors._sector_data) must cover
    every sector and tool in the tenant registry, so the ``live=False``
    fallback can never produce a gap when the live generator is unavailable.
    """
    from aeon_seed_sectors import _sector_data
    from aeon_sectors import SECTOR_ALIASES, list_sector_catalog

    data = _sector_data()
    for sector in list_sector_catalog():
        seed_key = next(
            (key for key in data if SECTOR_ALIASES.get(key, key) == sector["id"]),
            None,
        )
        assert seed_key is not None, f"no static seed data for sector {sector['id']}"
        missing = [tool["id"] for tool in sector["tools"] if tool["id"] not in data[seed_key]]
        assert not missing, f"static seed missing tools for {sector['id']}: {missing}"


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
