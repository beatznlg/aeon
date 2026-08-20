"""Regression coverage for the demo workspace seed.

The demo account flow seeds a brand-new workspace with realistic data through
``POST /workspaces/<id>/seed`` (``aeon_seed.seed_demo_workspace``). These tests
guard the full seed pipeline so a signature drift in one of the ``create_*``
helpers (e.g. a duplicate keyword argument) can never silently ship again and
break the demo account.
"""

import uuid


def _register(client, label: str) -> tuple[str, str]:
    email = f"seed-{label}-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": f"Seed {label}"},
    )
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    return data["token"], data["user"]["workspace_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_demo_seed_creates_full_demo_dataset(client):
    token, workspace_id = _register(client, "full")

    resp = client.post(f"/workspaces/{workspace_id}/seed", headers=_headers(token))
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data.get("ok") is True, data

    created = data.get("created") or {}
    assert created.get("anomalies") == 3
    assert created.get("incidents") == 2
    assert created.get("runbooks") == 1
    assert created.get("backup_policies") == 2
    assert created.get("backup_jobs") == 2
    assert created.get("restore_jobs") == 1
    assert created.get("dr_plans") == 1
    assert created.get("dr_drills") == 2
    assert created.get("automation_policies") == 2
    assert created.get("automation_budgets") == 2
    assert created.get("siem_integrations") == 1
    assert created.get("siem_export_logs") == 2
    assert created.get("audit_logs") >= 1


def test_demo_seed_is_idempotent(client):
    token, workspace_id = _register(client, "idem")

    first = client.post(f"/workspaces/{workspace_id}/seed", headers=_headers(token)).get_json()
    assert first.get("ok") is True, first

    second = client.post(f"/workspaces/{workspace_id}/seed", headers=_headers(token)).get_json()
    assert second.get("ok") is True, second

    # Re-running the seed must not duplicate the seeded records.
    anomalies = client.get(
        f"/anomalies?workspace_id={workspace_id}", headers=_headers(token)
    ).get_json()
    assert anomalies.get("ok") is True
    assert len(anomalies.get("anomalies") or []) == 3

    incidents = client.get(
        f"/incidents?workspace_id={workspace_id}", headers=_headers(token)
    ).get_json()
    assert incidents.get("ok") is True
    assert len(incidents.get("incidents") or []) == 2


def test_seeded_data_is_queryable(client):
    token, workspace_id = _register(client, "query")

    seed = client.post(f"/workspaces/{workspace_id}/seed", headers=_headers(token)).get_json()
    assert seed.get("ok") is True, seed

    anomalies = client.get(
        f"/anomalies?workspace_id={workspace_id}", headers=_headers(token)
    ).get_json()
    assert anomalies.get("ok") is True
    assert len(anomalies.get("anomalies") or []) == 3

    incidents = client.get(
        f"/incidents?workspace_id={workspace_id}", headers=_headers(token)
    ).get_json()
    assert incidents.get("ok") is True
    assert len(incidents.get("incidents") or []) == 2
