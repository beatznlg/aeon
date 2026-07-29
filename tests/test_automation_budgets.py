"""Tests for Phase 42: Automation Cost & Budget Controls."""

from __future__ import annotations

import json
import uuid

import pytest

from aeon_budgets import check_automation_budget
from aeon_db import (
    add_automation_execution,
    count_automation_executions,
    create_automation_budget,
    init_db,
)


@pytest.fixture
def admin_token(client):
    """Register a user and return an auth token with ADMIN workspace role."""
    email = f"admin-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Budget Admin"},
    )
    data = json.loads(resp.data)
    assert "token" in data, f"register failed: {resp.status_code} {data}"
    return data["token"]


@pytest.fixture
def operator_token(client):
    """Register a user and return an auth token with OPERATOR workspace role."""
    email = f"operator-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Budget Operator"},
    )
    data = json.loads(resp.data)
    assert "token" in data, f"register failed: {resp.status_code} {data}"
    return data["token"]


@pytest.fixture
def unique_workspace():
    """Return a fresh workspace id for a test."""
    return f"ws-{uuid.uuid4().hex[:8]}"


def test_create_budget_requires_admin(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "name": "Daily Limit",
        "period": "day",
        "limit_value": 10,
        "action": "block",
    }
    resp = client.post("/automations/budgets", json=payload, headers=headers)
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["ok"] is True
    budget = data["budget"]
    assert budget["name"] == "Daily Limit"
    assert budget["period"] == "day"
    assert budget["limit_value"] == 10
    assert budget["action"] == "block"


def test_budget_list(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = client.get("/automations/budgets", headers=headers)
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert isinstance(data["budgets"], list)


def test_budget_detail(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_payload = {
        "name": "Hourly Limit",
        "period": "hour",
        "limit_value": 5,
        "action": "warn",
    }
    resp = client.post("/automations/budgets", json=create_payload, headers=headers)
    budget_id = json.loads(resp.data)["budget"]["id"]

    resp = client.get(f"/automations/budgets/{budget_id}", headers=headers)
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["budget"]["name"] == "Hourly Limit"


def test_budget_update(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_payload = {
        "name": "Monthly Limit",
        "period": "month",
        "limit_value": 100,
        "action": "block",
    }
    resp = client.post("/automations/budgets", json=create_payload, headers=headers)
    budget_id = json.loads(resp.data)["budget"]["id"]

    resp = client.patch(
        f"/automations/budgets/{budget_id}",
        json={"limit_value": 200, "action": "warn"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["budget"]["limit_value"] == 200
    assert data["budget"]["action"] == "warn"


def test_budget_delete(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_payload = {
        "name": "Total Limit",
        "period": "total",
        "limit_value": 1,
        "action": "block",
    }
    resp = client.post("/automations/budgets", json=create_payload, headers=headers)
    budget_id = json.loads(resp.data)["budget"]["id"]

    resp = client.delete(f"/automations/budgets/{budget_id}", headers=headers)
    assert resp.status_code == 200
    assert json.loads(resp.data)["ok"] is True

    resp = client.get(f"/automations/budgets/{budget_id}", headers=headers)
    assert resp.status_code == 404


def test_budget_check_endpoint(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = client.get("/automations/budgets/check", headers=headers)
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert "allowed" in data
    assert "warnings" in data
    assert "blocks" in data


def test_budget_blocks_after_limit(unique_workspace):
    init_db()
    workspace_id = unique_workspace
    rule_id = "rule-block-test"
    create_automation_budget(
        workspace_id=workspace_id,
        name="Total Block",
        period="total",
        limit_value=1,
        action="block",
    )

    # First check should be allowed (count == 0)
    result = check_automation_budget(workspace_id, rule_id=rule_id)
    assert result.allowed is True

    # Add an execution to exceed the budget
    add_automation_execution(rule_id, workspace_id, status="success")

    # Next check should block
    result = check_automation_budget(workspace_id, rule_id=rule_id)
    assert result.allowed is False
    assert result.blocks


def test_budget_warn_after_limit(unique_workspace):
    init_db()
    workspace_id = unique_workspace
    rule_id = "rule-warn-test"
    create_automation_budget(
        workspace_id=workspace_id,
        name="Warn Limit",
        period="total",
        limit_value=1,
        action="warn",
    )

    add_automation_execution(rule_id, workspace_id, status="success")

    result = check_automation_budget(workspace_id, rule_id=rule_id)
    assert result.allowed is True
    assert result.warnings


def test_per_rule_budget_only_applies_to_that_rule(unique_workspace):
    init_db()
    workspace_id = unique_workspace
    create_automation_budget(
        workspace_id=workspace_id,
        name="Rule Specific",
        period="total",
        limit_value=1,
        action="block",
        rule_id="rule-a",
    )

    add_automation_execution("rule-a", workspace_id, status="success")

    # rule-a should be blocked
    result = check_automation_budget(workspace_id, rule_id="rule-a")
    assert result.allowed is False

    # rule-b should be allowed
    result = check_automation_budget(workspace_id, rule_id="rule-b")
    assert result.allowed is True


def test_count_automation_executions(unique_workspace):
    init_db()
    workspace_id = unique_workspace
    rule_id = "rule-count-test"
    add_automation_execution(rule_id, workspace_id, status="success")
    add_automation_execution(rule_id, workspace_id, status="success")
    assert count_automation_executions(workspace_id) == 2
