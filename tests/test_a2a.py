"""Tests for the A2A (Agent-to-Agent) interoperability layer."""

from __future__ import annotations

import importlib
import json
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest

import aeon_a2a
from aeon_a2a import A2aManager, reset_a2a_manager


@pytest.fixture()
def manager(tmp_path: Path) -> A2aManager:
    reset_a2a_manager()
    return A2aManager(tmp_path)


def test_add_and_list_agents(manager: A2aManager):
    agent = manager.add_agent("ws-1", "ResearchBot", "https://peer.example.com")
    assert agent.enabled is True
    listed = manager.list_agents("ws-1")
    assert len(listed) == 1
    assert listed[0]["name"] == "ResearchBot"
    assert listed[0]["auth_token" if False else "token_masked"] == ""
    assert manager.list_agents("ws-2") == []


def test_add_agent_validation(manager: A2aManager):
    with pytest.raises(ValueError):
        manager.add_agent("ws-1", "", "https://peer.example.com")
    with pytest.raises(ValueError):
        manager.add_agent("ws-1", "Bot", "ftp://bad.example.com")
    with pytest.raises(ValueError):
        manager.add_agent("ws-1", "Bot", "x" * 3000)


def test_persistence_roundtrip(tmp_path: Path):
    mgr = A2aManager(tmp_path)
    mgr.add_agent("ws-1", "Bot A", "https://a.example.com", token="secret-token-123")
    # New instance reads the same state file.
    mgr2 = A2aManager(tmp_path)
    listed = mgr2.list_agents("ws-1")
    assert listed[0]["token_masked"].endswith("123")
    assert "secret-token-123" not in json.dumps(listed)


def test_enable_disable_and_delete(manager: A2aManager):
    agent = manager.add_agent("ws-1", "Bot", "https://peer.example.com")
    assert manager.set_enabled("ws-1", agent.id, False).enabled is False
    assert manager.remove_agent("ws-1", agent.id) is True
    assert manager.remove_agent("ws-1", agent.id) is False
    assert manager.list_agents("ws-1") == []


def test_circuit_breaker(manager: A2aManager):
    agent = manager.add_agent("ws-1", "Bot", "https://peer.example.com")
    assert agent.breaker_open is False
    for _ in range(aeon_a2a._BREAKER_THRESHOLD):
        agent.record_failure()
    assert agent.breaker_open is True
    agent.record_success()
    assert agent.breaker_open is False


def test_delegate_failure_trips_breaker(manager: A2aManager):
    agent = manager.add_agent("ws-1", "Bot", "https://peer.example.com")
    with patch.object(aeon_a2a.A2aClient, "send_message", side_effect=aeon_a2a.A2aError("transport error: boom")):
        for _ in range(aeon_a2a._BREAKER_THRESHOLD):
            result = manager.delegate("ws-1", agent.id, {"content": "hi"})
            assert result["ok"] is False
    listed = manager.list_agents("ws-1")
    assert listed[0]["breaker_open"] is True
    # While the breaker is open, delegation fails fast without touching the peer.
    result = manager.delegate("ws-1", agent.id, {"content": "hi"})
    assert "circuit breaker" in result["error"]


def test_delegate_to_missing_agent(manager: A2aManager):
    result = manager.delegate("ws-1", "nonexistent", {"content": "hi"})
    assert result["ok"] is False
    assert result["error"] == "agent not found"


def test_delegate_disabled_agent(manager: A2aManager):
    agent = manager.add_agent("ws-1", "Bot", "https://peer.example.com", enabled=False)
    result = manager.delegate("ws-1", agent.id, {"content": "hi"})
    assert result["ok"] is False
    assert result["error"] == "agent is disabled"


def test_agent_directory_and_prompt_block(manager: A2aManager):
    agent = manager.add_agent("ws-1", "Bot B", "https://b.example.com")
    manager.add_agent("ws-1", "Bot A", "https://a.example.com", enabled=False)
    # Disabled agents are filtered out; enabled ones appear even before a refresh.
    entries = manager.agent_directory("ws-1")
    assert len(entries) == 1
    assert entries[0]["name"] == "Bot B"
    assert entries[0]["skills"] == []
    with patch.object(
        aeon_a2a.A2aClient,
        "fetch_agent_card",
        return_value={"description": "Does research", "skills": [{"name": "search"}, {"name": "summarize"}]},
    ):
        refresh = manager.refresh_agent("ws-1", agent.id)
    assert refresh["ok"] is True
    entries = manager.agent_directory("ws-1")
    assert len(entries) == 1
    assert entries[0]["skills"] == ["search", "summarize"]
    block = manager.agent_prompt_block("ws-1")
    assert "Bot B (A2A): search, summarize" in block


def test_routes_crud_and_delegation():
    flask = pytest.importorskip("flask")
    app = flask.Flask(__name__)
    app.config["TESTING"] = True

    import aeon_auth
    from aeon_a2a_routes import register_a2a_routes

    reset_a2a_manager()
    with patch.dict("sys.modules", {}):
        pass

    # Bypass real auth: fake decorators that set g.workspace_id.
    from flask import g

    def fake_require_auth(fn):
        def wrapper(*args, **kwargs):
            g.user = {"user_id": "u-1", "email": "t@example.com"}
            g.workspace_id = "ws-test"
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper

    def fake_require_role(role):
        def deco(fn):
            def wrapper(*args, **kwargs):
                return fn(*args, **kwargs)
            wrapper.__name__ = fn.__name__
            return wrapper
        return deco

    with patch.object(aeon_auth, "require_auth", fake_require_auth), patch.object(
        aeon_auth, "require_workspace_role", fake_require_role
    ):
        import aeon_a2a_routes
        importlib.reload(aeon_a2a_routes)
        register_a2a_routes(app)

    reset_a2a_manager()
    import tempfile
    with patch.object(aeon_a2a, "get_a2a_manager", lambda root=None: A2aManager(Path(tempfile.mkdtemp()))):
        client = app.test_client()

        resp = client.get("/a2a/agents")
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["ok"] is True

        resp = client.post("/a2a/agents", json={"name": "Bot", "url": "https://peer.example.com"})
        assert resp.status_code == HTTPStatus.CREATED
        agent_id = resp.get_json()["agent"]["id"]

        resp = client.post(f"/a2a/agents/{agent_id}/message", json={"message": {"content": "hola"}})
        # Delegation to an unreachable peer is a structured failure (502), not a crash.
        assert resp.status_code == HTTPStatus.BAD_GATEWAY
        assert resp.get_json()["ok"] is False

        resp = client.delete(f"/a2a/agents/{agent_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["ok"] is True

    reset_a2a_manager()


def test_well_known_agent_card():
    flask = pytest.importorskip("flask")
    app = flask.Flask(__name__)
    app.config["TESTING"] = True

    from aeon_a2a_routes import register_a2a_routes

    register_a2a_routes(app)
    resp = app.test_client().get("/.well-known/agent.json")
    assert resp.status_code == HTTPStatus.OK
    card = resp.get_json()
    assert card["name"] == "AEON OS"
    assert "skills" in card
