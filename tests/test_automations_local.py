"""Tests for the local SQLite automation store fallback.

When Supabase credentials are absent, /automations* routes fall back to the
local automation_rules table so the full automation surface works in preview
and self-hosted deployments. Rules and executions must persist across calls.
"""

import json
import uuid

import pytest


@pytest.fixture
def operator_token(client):
    email = f"auto-operator-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Auto Operator"},
    )
    data = json.loads(resp.data)
    assert data["ok"]
    return data["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_local_automations_crud_and_run(client, operator_token):
    # ── Create ──────────────────────────────────────────────────────────
    resp = client.post(
        "/automations",
        json={
            "name": "Local Rule",
            "event_type": "system",
            "actions": [{"type": "webhook", "config": {"url": "https://example.com/hook"}}],
        },
        headers=auth(operator_token),
    )
    assert resp.status_code == 201, resp.data
    rule = json.loads(resp.data)["rule"]
    rule_id = rule["id"]
    assert rule["name"] == "Local Rule"
    assert rule["workspace_id"]

    # ── List ────────────────────────────────────────────────────────────
    resp = client.get("/automations", headers=auth(operator_token))
    assert resp.status_code == 200
    rules = json.loads(resp.data)["rules"]
    assert any(r["id"] == rule_id for r in rules)

    # ── Get one ─────────────────────────────────────────────────────────
    resp = client.get(f"/automations/{rule_id}", headers=auth(operator_token))
    assert resp.status_code == 200
    assert json.loads(resp.data)["rule"]["id"] == rule_id

    # ── Update ──────────────────────────────────────────────────────────
    resp = client.patch(
        f"/automations/{rule_id}",
        json={"enabled": False, "name": "Local Rule v2"},
        headers=auth(operator_token),
    )
    assert resp.status_code == 200
    updated = json.loads(resp.data)["rule"]
    assert updated["name"] == "Local Rule v2"
    assert updated["enabled"] is False

    # ── Run (dry-run, log action executes locally) ──────────────────────
    resp = client.post(
        f"/automations/{rule_id}/run",
        json={"dry_run": True},
        headers=auth(operator_token),
    )
    assert resp.status_code == 200, resp.data
    assert json.loads(resp.data)["ok"] is True

    # ── Executions list ─────────────────────────────────────────────────
    resp = client.get("/automations/executions", headers=auth(operator_token))
    assert resp.status_code == 200
    executions = json.loads(resp.data)["executions"]
    assert isinstance(executions, list)

    # ── Delete ──────────────────────────────────────────────────────────
    resp = client.delete(f"/automations/{rule_id}", headers=auth(operator_token))
    assert resp.status_code == 200
    resp = client.get(f"/automations/{rule_id}", headers=auth(operator_token))
    assert resp.status_code == 404


def test_local_automations_export_import(client, operator_token):
    resp = client.post(
        "/automations",
        json={
            "name": "Exportable",
            "event_type": "inbound_webhook",
            "actions": [{"type": "delay", "config": {"seconds": 1}}],
        },
        headers=auth(operator_token),
    )
    assert resp.status_code == 201

    resp = client.get("/automations/export", headers=auth(operator_token))
    assert resp.status_code == 200
    payload = json.loads(resp.data)
    assert payload["count"] >= 1
    assert payload["rules"]

    # Import into a fresh workspace (a second operator has its own workspace)
    other_token = None
    email = f"auto-import-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Auto Import"},
    )
    other_token = json.loads(resp.data)["token"]

    resp = client.post(
        "/automations/import",
        json={"rules": payload["rules"]},
        headers=auth(other_token),
    )
    assert resp.status_code == 200
    imported = json.loads(resp.data)
    assert imported["imported"] == payload["count"]
    assert imported["ok"] is True


def test_local_automations_requires_auth(client):
    resp = client.get("/automations")
    assert resp.status_code == 401
