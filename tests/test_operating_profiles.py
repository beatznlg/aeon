"""Regression tests for governed AEON operating profiles."""

from __future__ import annotations

import uuid

from aeon_operating_profiles import (
    OPERATING_PROFILES,
    get_operating_profile_manager,
    list_profiles,
    recommend_profiles,
)


def _registered_user(client, prefix: str = "profiles"):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@test.local"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Profile Tester"},
    )
    assert response.status_code == 201
    body = response.get_json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]


def test_profile_catalog_is_valid_and_contains_government_and_air_gapped_options():
    ids = {profile.id for profile in OPERATING_PROFILES}
    assert len(ids) >= 9
    assert "government-agency" in ids
    assert "defense-air-gapped" in ids
    assert list_profiles(sector="government")
    assert any(
        profile["id"] == "defense-air-gapped"
        for profile in list_profiles(deployment_mode="air-gapped")
    )


def test_profile_recommendation_prefers_matching_regulated_context():
    recommendations = recommend_profiles(
        sector="health",
        organization_type="healthcare-provider",
        deployment_mode="cloud",
        data_classification="restricted",
    )
    assert recommendations[0]["profile"]["id"] == "healthcare-provider"
    assert recommendations[0]["match_score"] > recommendations[-1]["match_score"]


def test_profile_manager_persists_workspace_selection_and_rejects_incompatible_context(tmp_path):
    manager = get_operating_profile_manager(tmp_path)
    assert manager.effective("workspace-a")["profile_id"] == "general-business"

    selected = manager.set(
        "workspace-a",
        profile_id="government-agency",
        sector="government",
        organization_type="government-agency",
        deployment_mode="air-gapped",
        data_classification="restricted",
    )
    assert selected.profile_id == "government-agency"
    assert manager.effective("workspace-a")["effective"]["plugins"]

    reloaded = get_operating_profile_manager(tmp_path)
    assert reloaded.get("workspace-a").deployment_mode == "air-gapped"

    try:
        manager.set(
            "workspace-b",
            profile_id="government-agency",
            sector="finance",
            organization_type="government-agency",
        )
    except ValueError as exc:
        assert "sector" in str(exc)
    else:
        raise AssertionError("incompatible profile context should be rejected")


def test_operating_profile_routes_require_auth(client):
    assert client.get("/operating-profiles").status_code == 401
    assert client.get("/workspace/operating-profile").status_code == 401


def test_operating_profile_routes_are_workspace_scoped_and_admin_mutation_is_required(client):
    headers, user = _registered_user(client)

    catalog = client.get("/operating-profiles?sector=government", headers=headers)
    assert catalog.status_code == 200
    assert catalog.get_json()["count"] >= 1

    recommendation = client.get(
        "/operating-profiles/recommend?sector=health&organization_type=healthcare-provider",
        headers=headers,
    )
    assert recommendation.status_code == 200
    assert recommendation.get_json()["recommendations"][0]["profile"]["id"] == "healthcare-provider"

    detail = client.get("/operating-profiles/government-agency", headers=headers)
    assert detail.status_code == 200
    assert detail.get_json()["profile"]["audience"] == "government"

    current = client.get("/workspace/operating-profile", headers=headers)
    assert current.status_code == 200
    assert current.get_json()["profile_id"] == "general-business"

    # Registration creates an ADMIN workspace membership, so the owner can select.
    updated = client.put(
        "/workspace/operating-profile",
        headers=headers,
        json={
            "profile_id": "government-agency",
            "sector": "government",
            "organization_type": "government-agency",
            "deployment_mode": "air-gapped",
            "data_classification": "restricted",
        },
    )
    assert updated.status_code == 200
    assert updated.get_json()["profile_id"] == "government-agency"
    assert updated.get_json()["deployment_mode"] == "air-gapped"


def test_operating_profile_mutation_rejects_incompatible_context(client):
    headers, _ = _registered_user(client, "profiles-invalid")
    response = client.put(
        "/workspace/operating-profile",
        headers=headers,
        json={
            "profile_id": "defense-air-gapped",
            "sector": "health",
            "organization_type": "healthcare-provider",
            "deployment_mode": "cloud",
            "data_classification": "restricted",
        },
    )
    assert response.status_code == 400
    assert "not supported" in response.get_json()["error"]
