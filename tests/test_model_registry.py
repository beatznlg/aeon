"""Model registry unit and route tests.

The registry records provider/model/adapter/eval evidence per deployment with
a fail-closed lifecycle. Unit tests pin the state machine and storage; route
tests pin authz (admin-only writes) using the LLM-preference test pattern.
"""

from __future__ import annotations

import pytest

import aeon_model_registry as registry
from aeon_db import Membership, User, get_db


@pytest.fixture
def isolated_root(tmp_path, monkeypatch):
    """Point registry + assurance storage at a throwaway directory."""
    monkeypatch.setenv("AEON_ROOT", str(tmp_path))
    return tmp_path


# ── Unit: lifecycle state machine ─────────────────────────────────────────────


def test_register_requires_provider(isolated_root):
    with pytest.raises(ValueError, match="provider is required"):
        registry.register_deployment("", "gpt-4o")


def test_register_requires_model(isolated_root):
    with pytest.raises(ValueError, match="model is required"):
        registry.register_deployment("openai", "  ")


def test_lifecycle_register_approve_activate_rollback(isolated_root):
    record = registry.register_deployment(
        "openai",
        "gpt-4o",
        adapter_version="lora-fin-1",
        sector_pack_id="financial-services-global",
        accuracy=0.96,
    )
    assert record["status"] == "registered"
    assert record["provider"] == "openai"
    assert record["adapter_version"] == "lora-fin-1"
    assert len(record["fingerprint"]) == 64

    approved = registry.approve_deployment(record["deployment_id"], "admin@acme.test")
    assert approved["status"] == "approved"
    assert approved["approved_by"] == "admin@acme.test"

    active = registry.activate_deployment(record["deployment_id"], "admin@acme.test")
    assert active["status"] == "active"

    rolled_back = registry.rollback_deployment(
        record["deployment_id"], "admin@acme.test", "eval regression on golden set"
    )
    assert rolled_back["status"] == "rolled_back"
    assert rolled_back["rollback_reason"] == "eval regression on golden set"


def test_activate_before_approve_raises(isolated_root):
    record = registry.register_deployment("anthropic", "claude-4")
    with pytest.raises(ValueError, match="cannot move deployment from 'registered' to 'active'"):
        registry.activate_deployment(record["deployment_id"], "admin@acme.test")


def test_rollback_requires_reason(isolated_root):
    record = registry.register_deployment("stub", "deterministic-stub")
    with pytest.raises(ValueError, match="reason is required"):
        registry.rollback_deployment(record["deployment_id"], "admin@acme.test", "")


def test_get_missing_returns_none(isolated_root):
    assert registry.get_deployment("does-not-exist") is None


def test_workspace_scoping(isolated_root):
    record = registry.register_deployment("stub", "ws-a-model", workspace_id="workspace-a")
    assert registry.get_deployment(record["deployment_id"], workspace_id="workspace-a") is not None
    assert registry.get_deployment(record["deployment_id"], workspace_id="workspace-b") is None
    assert registry.list_deployments(workspace_id="workspace-b") == []


def test_list_filters(isolated_root):
    a = registry.register_deployment("stub", "m1", workspace_id="ws-1")
    b = registry.register_deployment("openai", "m2", workspace_id="ws-1", sector_pack_id="finance")
    registry.register_deployment("stub", "m3", workspace_id="ws-2")

    assert {d["deployment_id"] for d in registry.list_deployments(workspace_id="ws-1")} == {
        a["deployment_id"],
        b["deployment_id"],
    }
    assert registry.list_deployments(workspace_id="ws-1", provider="openai") == [b]
    assert registry.list_deployments(workspace_id="ws-1", model="m2") == [b]
    assert registry.list_deployments(workspace_id="ws-1", sector_pack_id="finance") == [b]


# ── Unit: auto-attach of eval evidence ────────────────────────────────────────


def test_attach_eval_evidence_by_id(isolated_root):
    record = registry.register_deployment("openai", "gpt-4o", workspace_id="ws-1")
    updated = registry.attach_eval_evidence(
        record["deployment_id"],
        eval_report="scripts/output/sector_eval.json",
        eval_sha256="b" * 64,
        accuracy=0.97,
        metrics={"mean_groundedness": 0.96},
        workspace_id="ws-1",
    )
    assert updated is not None
    assert updated["eval_sha256"] == "b" * 64
    assert updated["accuracy"] == 0.97
    assert updated["eval_metrics"]["mean_groundedness"] == 0.96


def test_attach_eval_evidence_auto_match(isolated_root):
    registry.register_deployment("stub", "old-model", workspace_id="ws-1")
    target = registry.register_deployment("openai", "gpt-4o", workspace_id="ws-1")
    registry.register_deployment("openai", "gpt-4o", workspace_id="ws-2")

    updated = registry.attach_eval_evidence(
        provider="openai",
        model="gpt-4o",
        eval_report="scripts/output/sector_eval.json",
        eval_sha256="c" * 64,
        accuracy=0.9,
        workspace_id="ws-1",
    )
    assert updated is not None
    assert updated["deployment_id"] == target["deployment_id"]


def test_attach_eval_evidence_ignores_rolled_back(isolated_root):
    record = registry.register_deployment("openai", "gpt-4o", workspace_id="ws-1")
    registry.rollback_deployment(record["deployment_id"], "admin", "bad")
    assert (
        registry.attach_eval_evidence(
            provider="openai", model="gpt-4o", workspace_id="ws-1", accuracy=0.9
        )
        is None
    )


def test_attach_eval_evidence_no_match_returns_none(isolated_root):
    assert (
        registry.attach_eval_evidence(
            provider="openai", model="does-not-exist", workspace_id="ws-1"
        )
        is None
    )
    assert registry.attach_eval_evidence("missing-id") is None


def test_attach_requires_model_for_auto_match(isolated_root):
    with pytest.raises(ValueError, match="provider and model are required"):
        registry.attach_eval_evidence(provider="openai")


def test_record_eval_evidence_updates_fields(isolated_root):
    record = registry.register_deployment("openai", "gpt-4o", workspace_id="ws-1")
    updated = registry.record_eval_evidence(
        record["deployment_id"],
        eval_report="scripts/output/sector_eval_finance.json",
        eval_sha256="a" * 64,
        accuracy=0.98,
        metrics={"mean_groundedness": 0.96, "abstained": 0},
        workspace_id="ws-1",
    )
    assert updated["eval_sha256"] == "a" * 64
    assert updated["accuracy"] == 0.98
    assert updated["eval_metrics"]["mean_groundedness"] == 0.96


def test_accuracy_out_of_range_rejected(isolated_root):
    with pytest.raises(ValueError, match="accuracy must be between 0 and 1"):
        registry.register_deployment("openai", "gpt-4o", accuracy=1.5)


def test_eval_sha256_must_be_hex(isolated_root):
    with pytest.raises(ValueError, match="SHA-256 hex digest"):
        registry.register_deployment("openai", "gpt-4o", eval_sha256="not-a-hash")


def test_fingerprint_stable_and_content_sensitive(isolated_root):
    record = registry.register_deployment("stub", "m1")
    stored = registry.get_deployment(record["deployment_id"])
    assert stored["fingerprint"] == record["fingerprint"]
    mutated = dict(stored)
    mutated["model"] = "m2"
    assert registry._fingerprint(mutated) != record["fingerprint"]


# ── Route: authz and lifecycle over HTTP ─────────────────────────────────────


def _register(client, email: str) -> tuple[str, str]:
    response = client.post("/auth/register", json={"email": email, "password": "secure123"})
    assert response.status_code == 201
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _promote_to_admin(workspace_id: str) -> None:
    with get_db().session() as session:
        membership = session.query(Membership).filter_by(workspace_id=workspace_id).one()
        user = session.query(User).filter_by(id=membership.user_id).one()
        membership.role = "ADMIN"
        user.role = "ADMIN"
        session.commit()


def test_registry_requires_auth(client, isolated_root):
    assert client.get("/models/registry").status_code == 401


def test_registry_write_requires_admin(client, isolated_root):
    token, workspace_id = _register(client, "reg-viewer@test.local")
    # New users are admin by default; demote to VIEWER to prove the guard.
    with get_db().session() as session:
        membership = session.query(Membership).filter_by(workspace_id=workspace_id).one()
        user = session.query(User).filter_by(id=membership.user_id).one()
        membership.role = "VIEWER"
        user.role = "VIEWER"
        session.commit()
    response = client.post(
        "/models/registry",
        json={"provider": "openai", "model": "gpt-4o"},
        headers=_headers(token),
    )
    assert response.status_code == 403


def test_registry_admin_lifecycle(client, isolated_root):
    token, workspace_id = _register(client, "reg-admin@test.local")
    _promote_to_admin(workspace_id)

    created = client.post(
        "/models/registry",
        json={
            "provider": "openai",
            "model": "gpt-4o",
            "adapter_version": "lora-fin-1",
            "sector_pack_id": "financial-services-global",
            "accuracy": 0.96,
            "eval_report": "scripts/output/sector_eval_finance.json",
        },
        headers=_headers(token),
    )
    assert created.status_code == 201
    deployment = created.get_json()["deployment"]
    assert deployment["status"] == "registered"

    listed = client.get("/models/registry", headers=_headers(token))
    assert listed.status_code == 200
    assert len(listed.get_json()["deployments"]) == 1

    approved = client.post(
        f"/models/registry/{deployment['deployment_id']}/approve",
        json={"note": "gate passed"},
        headers=_headers(token),
    )
    assert approved.status_code == 200
    assert approved.get_json()["deployment"]["status"] == "approved"

    active = client.post(
        f"/models/registry/{deployment['deployment_id']}/activate",
        headers=_headers(token),
    )
    assert active.status_code == 200
    assert active.get_json()["deployment"]["status"] == "active"

    active_list = client.get("/models/registry/active", headers=_headers(token))
    assert active_list.status_code == 200
    assert len(active_list.get_json()["deployments"]) == 1

    rolled_back = client.post(
        f"/models/registry/{deployment['deployment_id']}/rollback",
        json={"reason": "drift detected on golden set"},
        headers=_headers(token),
    )
    assert rolled_back.status_code == 200
    assert rolled_back.get_json()["deployment"]["status"] == "rolled_back"

    eval_ev = client.post(
        f"/models/registry/{deployment['deployment_id']}/eval",
        json={"accuracy": 0.99, "metrics": {"mean_groundedness": 0.98}},
        headers=_headers(token),
    )
    assert eval_ev.status_code == 200
    assert eval_ev.get_json()["deployment"]["accuracy"] == 0.99


def test_registry_detail_404(client, isolated_root):
    token, workspace_id = _register(client, "reg-404@test.local")
    _promote_to_admin(workspace_id)
    response = client.get("/models/registry/missing-id", headers=_headers(token))
    assert response.status_code == 404
