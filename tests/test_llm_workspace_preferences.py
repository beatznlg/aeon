"""Workspace-scoped LLM preference regression tests."""

from __future__ import annotations

from aeon_db import Membership, User, Workspace, get_db


def _register(client, email: str) -> tuple[str, str]:
    response = client.post("/auth/register", json={"email": email, "password": "secure123"})
    assert response.status_code == 201
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_workspace_preference_reads_environment_fallback(client, monkeypatch):
    token, workspace_id = _register(client, "llm-pref-read@test.local")
    monkeypatch.setenv("AEON_LLM_PROVIDER", "stub")

    response = client.get("/llm/preferences", headers=_headers(token))

    assert response.status_code == 200
    assert response.get_json()["preference"] == {
        "workspace_id": workspace_id,
        "provider": "stub",
        "model": None,
        "source": "environment",
    }


def test_admin_switch_persists_only_identifiers(client):
    token, workspace_id = _register(client, "llm-pref-write@test.local")

    response = client.post(
        "/llm/switch",
        json={"provider": "stub", "model": "deterministic stub"},
        headers=_headers(token),
    )

    assert response.status_code == 200
    assert response.get_json()["preference"]["source"] == "workspace"
    with get_db().session() as session:
        workspace = session.query(Workspace).filter_by(id=workspace_id).one()
        assert workspace.llm_provider == "stub"
        assert workspace.llm_model == "deterministic stub"


def test_preference_write_rejects_non_admin_workspace_member(client):
    token, workspace_id = _register(client, "llm-pref-viewer@test.local")
    with get_db().session() as session:
        workspace = session.query(Workspace).filter_by(id=workspace_id).one()
        membership = session.query(Membership).filter_by(workspace_id=workspace_id).one()
        user = session.query(User).filter_by(id=membership.user_id).one()
        membership.role = "VIEWER"
        user.role = "VIEWER"
        session.commit()
        assert workspace is not None

    response = client.put(
        "/llm/preferences",
        json={"provider": "stub", "model": "deterministic stub"},
        headers=_headers(token),
    )

    assert response.status_code == 403


def test_preference_route_never_persists_credentials(client):
    token, workspace_id = _register(client, "llm-pref-secret@test.local")
    with get_db().session() as session:
        membership = session.query(Membership).filter_by(workspace_id=workspace_id).one()
        user = session.query(User).filter_by(id=membership.user_id).one()
        membership.role = "ADMIN"
        user.role = "ADMIN"
        session.commit()

    response = client.put(
        "/llm/preferences",
        json={"provider": "custom", "model": "private-model", "api_key": "must-not-store"},
        headers=_headers(token),
    )

    assert response.status_code == 200
    with get_db().session() as session:
        workspace = session.query(Workspace).filter_by(id=workspace_id).one()
        assert workspace.llm_provider == "custom"
        assert workspace.llm_model == "private-model"
        assert "must-not-store" not in str(workspace.__dict__)
