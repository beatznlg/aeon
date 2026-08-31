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


class _FakePeerResponse:
    """Minimal stand-in for a ``requests`` response from the remote peer."""

    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


_PEER_AGENT_CARD = {
    "name": "PeerBot",
    "description": "A mocked remote A2A peer",
    "protocolVersion": "0.3.0",
    "skills": [{"name": "translate"}, {"name": "summarize"}],
}


def _jsonrpc_ok(payload: dict, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": payload.get("id"), "result": result}


def _build_a2a_app_with_fake_auth():
    """Fresh Flask app with the A2A routes registered and auth bypassed.

    The fake decorators inject ``g.user`` / ``g.workspace_id`` exactly like
    the real ones, so the route handlers run unmodified.
    """
    flask = pytest.importorskip("flask")
    app = flask.Flask(__name__)
    app.config["TESTING"] = True

    from flask import g

    import aeon_auth

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
        aeon_a2a_routes.register_a2a_routes(app)
    return app


def test_routes_crud_and_delegation(tmp_path: Path):
    app = _build_a2a_app_with_fake_auth()
    reset_a2a_manager()

    with patch.dict("os.environ", {"AEON_ROOT": str(tmp_path)}), patch(
        "aeon_a2a.requests.post", return_value=_FakePeerResponse(500)
    ):
        client = app.test_client()

        resp = client.get("/a2a/agents")
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["ok"] is True

        resp = client.post("/a2a/agents", json={"name": "Bot", "url": "https://peer.example.com"})
        assert resp.status_code == HTTPStatus.CREATED
        agent_id = resp.get_json()["agent"]["id"]

        resp = client.post(f"/a2a/agents/{agent_id}/message", json={"message": {"content": "hola"}})
        # Delegation to a failing peer is a structured failure (502), not a crash.
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


def test_delegate_endpoint_with_mocked_peer(tmp_path: Path):
    """Full HTTP round-trip against a mocked A2A peer: register, discover,
    delegate via message/send and poll the task — verifying the outbound
    JSON-RPC wire format and Bearer auth on the wire."""
    pytest.importorskip("flask")
    app = _build_a2a_app_with_fake_auth()
    reset_a2a_manager()
    client = app.test_client()

    peer_url = "https://peer.example.com/a2a"

    def fake_post(url, headers=None, json=None, timeout=None):
        method = (json or {}).get("method")
        if method == "message/send":
            result = {"id": "task-777", "contextId": "ctx-1", "status": {"state": "completed"}}
        elif method == "tasks/get":
            result = {
                "id": "task-777",
                "status": {"state": "completed"},
                "artifacts": [{"parts": [{"text": "hola traducido"}]}],
            }
        else:
            result = {}
        return _FakePeerResponse(200, _jsonrpc_ok(json or {}, result))

    with patch.dict("os.environ", {"AEON_ROOT": str(tmp_path)}), patch(
        "aeon_a2a.requests.post", side_effect=fake_post
    ) as mock_post, patch(
        "aeon_a2a.requests.get",
        side_effect=lambda url, **kw: _FakePeerResponse(200, _PEER_AGENT_CARD),
    ):
        # Register the peer with an auth token.
        resp = client.post(
            "/a2a/agents",
            json={"name": "PeerBot", "url": peer_url, "token": "topsecret-token-4321"},
        )
        assert resp.status_code == HTTPStatus.CREATED
        agent_id = resp.get_json()["agent"]["id"]

        # The raw token must never appear in API responses.
        assert "topsecret-token-4321" not in json.dumps(client.get("/a2a/agents").get_json())

        # Discovery: refresh pulls the peer's agent card.
        resp = client.post(f"/a2a/agents/{agent_id}/refresh")
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["agent_card"]["name"] == "PeerBot"

        # The cached card feeds the agent-facing directory.
        entries = client.get("/a2a/agent-directory").get_json()["agents"]
        assert entries[0]["skills"] == ["translate", "summarize"]

        # Delegation over HTTP.
        resp = client.post(
            f"/a2a/agents/{agent_id}/message",
            json={"message": {"content": "translate: hola"}},
        )
        assert resp.status_code == HTTPStatus.OK
        body = resp.get_json()
        assert body["ok"] is True
        assert body["result"]["id"] == "task-777"
        assert body["result"]["status"]["state"] == "completed"

        # Task polling over HTTP.
        resp = client.get(f"/a2a/agents/{agent_id}/tasks/task-777")
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["task"]["status"]["state"] == "completed"

    # Outbound wire format: exactly one message/send, correct JSON-RPC shape,
    # Bearer token attached, sent to the registered peer URL.
    sends = [c for c in mock_post.call_args_list if c.kwargs["json"]["method"] == "message/send"]
    assert len(sends) == 1
    call = sends[0]
    assert call.args[0] == peer_url
    wire = call.kwargs["json"]
    assert wire["jsonrpc"] == "2.0"
    assert wire["method"] == "message/send"
    assert wire["params"]["message"]["content"] == "translate: hola"
    assert call.kwargs["headers"]["Authorization"] == "Bearer topsecret-token-4321"

    reset_a2a_manager()


def test_delegate_endpoint_breaker_trips_over_http(tmp_path: Path):
    """After the failure threshold the delegate endpoint fails fast (502 with
    a circuit-breaker error) without contacting the peer again."""
    pytest.importorskip("flask")
    app = _build_a2a_app_with_fake_auth()
    reset_a2a_manager()
    client = app.test_client()

    with patch.dict("os.environ", {"AEON_ROOT": str(tmp_path)}), patch(
        "aeon_a2a.requests.post", return_value=_FakePeerResponse(500)
    ) as mock_post:
        resp = client.post("/a2a/agents", json={"name": "FlakyBot", "url": "https://flaky.example.com"})
        assert resp.status_code == HTTPStatus.CREATED
        agent_id = resp.get_json()["agent"]["id"]

        for _ in range(aeon_a2a._BREAKER_THRESHOLD):
            resp = client.post(f"/a2a/agents/{agent_id}/message", json={"message": {"content": "hi"}})
            assert resp.status_code == HTTPStatus.BAD_GATEWAY
            assert resp.get_json()["ok"] is False

        calls_at_threshold = mock_post.call_count

        # Next call fails fast: the peer is not contacted again.
        resp = client.post(f"/a2a/agents/{agent_id}/message", json={"message": {"content": "hi"}})
        assert resp.status_code == HTTPStatus.BAD_GATEWAY
        assert "circuit breaker" in resp.get_json()["error"]
        assert mock_post.call_count == calls_at_threshold

    reset_a2a_manager()


def test_delegate_endpoint_validation_errors(tmp_path: Path):
    """Blank message content → 400; unknown agent → 404 (delegate + poll)."""
    pytest.importorskip("flask")
    app = _build_a2a_app_with_fake_auth()
    reset_a2a_manager()
    client = app.test_client()

    with patch.dict("os.environ", {"AEON_ROOT": str(tmp_path)}):
        # Blank message content is rejected before any peer contact.
        resp = client.post("/a2a/agents/whatever/message", json={"message": {"content": "   "}})
        assert resp.status_code == HTTPStatus.BAD_REQUEST

        # Unknown agent → 404 (delegation).
        resp = client.post("/a2a/agents/nope/message", json={"message": {"content": "hi"}})
        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.get_json()["error"] == "agent not found"

        # Unknown agent → 404 (task polling).
        resp = client.get("/a2a/agents/nope/tasks/task-1")
        assert resp.status_code == HTTPStatus.NOT_FOUND

    reset_a2a_manager()
