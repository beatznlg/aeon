"""Tests for Phase 47 — Disaster Recovery & Backup Automation."""

import uuid

import pytest

from aeon_db import (
    Workspace,
    get_db,
)


@pytest.fixture
def workspace_id(client):
    """Create and return a workspace id."""
    db = get_db()
    slug = f"dr-test-{uuid.uuid4().hex[:8]}"
    with db.session() as s:
        ws = Workspace(slug=slug, name="DR Test", plan="enterprise")
        s.add(ws)
        s.commit()
        return str(ws.id)


def _auth_headers(client, workspace_id):
    """Register a user, add them to the workspace, and return auth headers."""
    from aeon_db import Membership, User

    email = f"dr-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "DR Tester"},
    )
    if resp.status_code == 201:
        token = resp.json["token"]
    else:
        resp = client.post(
            "/auth/login",
            json={"email": email, "password": "secure123"},
        )
        token = resp.json["token"]

    db = get_db()
    with db.session() as s:
        user = s.query(User).filter(User.email == email).first()
        if user:
            existing = (
                s.query(Membership)
                .filter(Membership.workspace_id == str(workspace_id), Membership.user_id == user.id)
                .first()
            )
            if not existing:
                s.add(Membership(workspace_id=str(workspace_id), user_id=user.id, role="ADMIN"))
                s.commit()

    return {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(workspace_id)}


def test_create_backup_policy(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    resp = client.post(
        "/dr/policies",
        json={"name": "Daily", "schedule": "0 2 * * *", "retention_days": 7},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json["ok"] is True
    assert resp.json["policy"]["name"] == "Daily"
    assert resp.json["policy"]["schedule"] == "0 2 * * *"


def test_list_backup_policies(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    client.post("/dr/policies", json={"name": "P1"}, headers=headers)
    client.post("/dr/policies", json={"name": "P2"}, headers=headers)
    resp = client.get("/dr/policies", headers=headers)
    assert resp.status_code == 200
    assert resp.json["ok"] is True
    names = {p["name"] for p in resp.json["policies"]}
    assert names >= {"P1", "P2"}


def test_get_backup_policy(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    created = client.post("/dr/policies", json={"name": "P1"}, headers=headers)
    policy_id = created.json["policy"]["id"]
    resp = client.get(f"/dr/policies/{policy_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json["policy"]["id"] == policy_id


def test_update_backup_policy(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    created = client.post("/dr/policies", json={"name": "P1"}, headers=headers)
    policy_id = created.json["policy"]["id"]
    resp = client.patch(
        f"/dr/policies/{policy_id}",
        json={"retention_days": 14, "enabled": False},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json["policy"]["retention_days"] == 14
    assert resp.json["policy"]["enabled"] is False


def test_delete_backup_policy(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    created = client.post("/dr/policies", json={"name": "P1"}, headers=headers)
    policy_id = created.json["policy"]["id"]
    resp = client.delete(f"/dr/policies/{policy_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json["ok"] is True
    resp = client.get(f"/dr/policies/{policy_id}", headers=headers)
    assert resp.status_code == 404


def test_run_backup_and_list(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    created = client.post("/dr/policies", json={"name": "P1"}, headers=headers)
    policy_id = created.json["policy"]["id"]
    resp = client.post(f"/dr/policies/{policy_id}/run", headers=headers)
    assert resp.status_code == 202
    assert resp.json["ok"] is True
    assert resp.json["job"]["status"] == "completed"

    resp = client.get("/dr/backups", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json["jobs"]) >= 1


def test_restore_backup(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    created = client.post("/dr/policies", json={"name": "P1"}, headers=headers)
    policy_id = created.json["policy"]["id"]
    run_resp = client.post(f"/dr/policies/{policy_id}/run", headers=headers)
    job_id = run_resp.json["job"]["id"]

    resp = client.post(f"/dr/backups/{job_id}/restore", headers=headers)
    assert resp.status_code == 202
    assert resp.json["ok"] is True
    assert resp.json["restore"]["status"] == "completed"

    resp = client.get("/dr/restores", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json["restores"]) >= 1


def test_apply_retention(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    created = client.post("/dr/policies", json={"name": "P1", "retention_days": 1}, headers=headers)
    policy_id = created.json["policy"]["id"]
    resp = client.post(f"/dr/policies/{policy_id}/retention", headers=headers)
    assert resp.status_code == 200
    assert resp.json["ok"] is True
    assert "deleted_keys" in resp.json


def test_create_dr_plan(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    resp = client.post(
        "/dr/plans",
        json={
            "name": "Primary",
            "rto_minutes": 30,
            "rpo_minutes": 15,
            "target_region": "us-east",
            "failover_regions": ["us-west"],
            "contact_info": {"email": "ops@example.com"},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json["ok"] is True
    assert resp.json["plan"]["name"] == "Primary"


def test_list_dr_plans(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    client.post("/dr/plans", json={"name": "Plan A"}, headers=headers)
    client.post("/dr/plans", json={"name": "Plan B"}, headers=headers)
    resp = client.get("/dr/plans", headers=headers)
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json["plans"]}
    assert names >= {"Plan A", "Plan B"}


def test_update_dr_plan(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    created = client.post("/dr/plans", json={"name": "Plan"}, headers=headers)
    plan_id = created.json["plan"]["id"]
    resp = client.patch(
        f"/dr/plans/{plan_id}",
        json={"rto_minutes": 10, "failover_regions": ["eu-west"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json["plan"]["rto_minutes"] == 10
    assert resp.json["plan"]["failover_regions"] == ["eu-west"]


def test_delete_dr_plan(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    created = client.post("/dr/plans", json={"name": "Plan"}, headers=headers)
    plan_id = created.json["plan"]["id"]
    resp = client.delete(f"/dr/plans/{plan_id}", headers=headers)
    assert resp.status_code == 200
    assert client.get(f"/dr/plans/{plan_id}", headers=headers).status_code == 404


def test_run_dr_drill(client, workspace_id):
    headers = _auth_headers(client, workspace_id)
    created = client.post("/dr/plans", json={"name": "Plan"}, headers=headers)
    plan_id = created.json["plan"]["id"]

    resp = client.post(f"/dr/plans/{plan_id}/drill", headers=headers)
    assert resp.status_code == 202
    assert resp.json["ok"] is True
    assert "drill" in resp.json
    assert resp.json["drill"]["status"] == "completed"
    assert "score" in resp.json["drill"]

    resp = client.get("/dr/drills", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json["drills"]) >= 1


def test_dr_manager_run_backup(workspace_id):
    from aeon_db import create_backup_policy, get_backup_job, list_backup_jobs
    from aeon_dr import BackupManager

    policy = create_backup_policy(workspace_id=workspace_id, name="test", schedule="0 2 * * *")
    manager = BackupManager(workspace_id)
    job = manager.run_backup(policy.id)
    assert job.status == "completed"
    assert job.size_bytes > 0
    assert list_backup_jobs(workspace_id)
    assert get_backup_job(job.id, workspace_id=workspace_id)


def test_dr_manager_restore_backup(workspace_id):
    from aeon_db import create_backup_policy
    from aeon_dr import BackupManager

    policy = create_backup_policy(workspace_id=workspace_id, name="test", schedule="0 2 * * *")
    manager = BackupManager(workspace_id)
    job = manager.run_backup(policy.id)
    restore = manager.restore_backup(job.id)
    assert restore.status == "completed"
    assert "restored_snapshot" in restore.metadata_json


def test_dr_manager_retention(workspace_id):
    from aeon_db import create_backup_policy
    from aeon_dr import BackupManager

    policy = create_backup_policy(
        workspace_id=workspace_id,
        name="test",
        schedule="0 2 * * *",
        retention_days=0,
    )
    manager = BackupManager(workspace_id)
    manager.run_backup(policy.id)
    deleted = manager.apply_retention(policy.id)
    assert isinstance(deleted, list)


def test_dr_plan_manager(workspace_id):
    from aeon_db import create_dr_plan
    from aeon_dr import DRDrillSimulator

    plan = create_dr_plan(workspace_id=workspace_id, name="test")
    simulator = DRDrillSimulator(workspace_id)
    drill = simulator.simulate_failover(plan.id)
    assert drill.status == "completed"
    assert drill.score is not None


def test_run_scheduled_backups(workspace_id):
    from aeon_db import create_backup_policy
    from aeon_dr import run_scheduled_backups

    create_backup_policy(workspace_id=workspace_id, name="scheduled", schedule="0 2 * * *")
    enqueued = run_scheduled_backups()
    assert isinstance(enqueued, list)
