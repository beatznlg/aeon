"""Tests for the multi-agent swarm orchestration endpoints and core logic."""

import json

import pytest


@pytest.fixture
def operator_token(client):
    """Register a user and return an auth token for swarm tests."""
    import uuid
    email = f"swarm-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Swarm Tester"},
    )
    data = json.loads(resp.data)
    if "token" not in data:
        raise RuntimeError(f"register failed: {resp.status_code} {data}")
    return data["token"]


# ── API tests ───────────────────────────────────────────────────────────────

def test_swarm_run_requires_app_ids(client, operator_token):
    resp = client.post(
        "/swarm/run",
        json={"prompt": "assess risk"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data["ok"] is False


def test_swarm_run_requires_prompt(client, operator_token):
    resp = client.post(
        "/swarm/run",
        json={"app_ids": ["cybersecurity", "finance"]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data["ok"] is False


def test_swarm_run_returns_ok(client, operator_token):
    resp = client.post(
        "/swarm/run",
        json={"app_ids": ["cybersecurity", "finance"], "prompt": "assess risk"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True


def test_swarm_run_with_roles(client, operator_token):
    resp = client.post(
        "/swarm/run",
        json={
            "app_ids": ["planner-app", "exec-app", "review-app", "sum-app"],
            "prompt": "build a plan",
            "roles": {
                "planner-app": "planner",
                "exec-app": "executor",
                "review-app": "reviewer",
                "sum-app": "summarizer",
            },
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True


def test_swarm_status_endpoint(client, operator_token):
    resp = client.get(
        "/swarm/fake-id",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True


def test_swarm_messages_endpoint(client, operator_token):
    resp = client.get(
        "/swarm/fake-id/messages",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["messages"] == []


# ── Core SwarmManager tests ─────────────────────────────────────────────────

class FakeReflectiveAgent:
    """Minimal stand-in for aeon.ReflectiveAgent."""

    def __init__(self):
        self.calls: list[str] = []

    def act(self, query: str):
        self.calls.append(query)
        return {"answer": f"echo: {query[:40]}"}


class FakeOS:
    def __init__(self):
        self.agents: dict[str, FakeReflectiveAgent] = {}

    def _agent_for(self, workspace_id: str):
        if workspace_id not in self.agents:
            self.agents[workspace_id] = FakeReflectiveAgent()
        return self.agents[workspace_id]


def test_swarm_manager_plan_and_execute():
    from aeon_swarm import SwarmManager

    manager = SwarmManager(root="/tmp/aeon_swarm_test")
    os = FakeOS()
    result = manager.coordinate(
        app_ids=["planner", "executor", "reviewer", "summarizer"],
        prompt="write a poem",
        os_orchestrator=os,
    )
    assert result["ok"] is True
    assert "swarm_id" in result
    assert result["prompt"] == "write a poem"
    assert set(result["roles"].values()).issubset(
        {"planner", "executor", "reviewer", "summarizer"}
    )
    assert len(result["tasks"]) > 0
    assert result["summary"]


def test_swarm_manager_role_override():
    from aeon_swarm import SwarmManager

    manager = SwarmManager(root="/tmp/aeon_swarm_test")
    os = FakeOS()
    result = manager.coordinate(
        app_ids=["a", "b"],
        prompt="test",
        os_orchestrator=os,
        roles={"a": "planner", "b": "executor"},
    )
    assert result["ok"] is True
    assert result["roles"] == {"a": "planner", "b": "executor"}


def test_swarm_manager_status_and_messages():
    from aeon_swarm import SwarmManager

    manager = SwarmManager(root="/tmp/aeon_swarm_test")
    os = FakeOS()
    result = manager.coordinate(
        app_ids=["x", "y"],
        prompt="test",
        os_orchestrator=os,
    )
    swarm_id = result["swarm_id"]
    status = manager.status(swarm_id)
    assert status["ok"] is True
    assert status["swarm_id"] == swarm_id
    messages = manager.messages(swarm_id)
    assert any(m["msg_type"] == "task" for m in messages)


def test_swarm_manager_rejects_empty_app_ids():
    from aeon_swarm import SwarmManager

    manager = SwarmManager()
    result = manager.coordinate(app_ids=[], prompt="test", os_orchestrator=FakeOS())
    assert result["ok"] is False


def test_swarm_manager_rejects_empty_prompt():
    from aeon_swarm import SwarmManager

    manager = SwarmManager()
    result = manager.coordinate(app_ids=["a"], prompt="", os_orchestrator=FakeOS())
    assert result["ok"] is False


def test_extract_evolution_suggestions():
    from aeon_swarm import SwarmManager

    text = '```json\n{"tool_improvement": {"name": "math_v2", "reason": "more robust"}}\n```'
    suggestions = SwarmManager._extract_evolution_suggestions(text)
    assert any(s.get("name") == "math_v2" for s in suggestions)
