"""Regression coverage for AEON OS MCP (Model Context Protocol) support.

Covers the workspace-scoped registry, token masking, the JSON-RPC/SSE client
transport (monkeypatched), agent tool discovery, and the /mcp routes.
"""

from __future__ import annotations

import json
import uuid

from aeon_mcp import McpClient, McpError, McpManager, reset_mcp_manager


class _FakeResponse:
    def __init__(self, payload: dict, content_type: str = "application/json", status: int = 200):
        self._payload = payload
        self._content_type = content_type
        self.status = status

    @property
    def headers(self) -> dict[str, str]:
        return {"Content-Type": self._content_type}

    def json(self) -> dict:
        return self._payload

    def iter_lines(self, decode_unicode: bool = False):
        data = json.dumps(self._payload)
        yield f"data: {data}"


def _register(client, label: str) -> tuple[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": f"mcp-{label}-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": f"MCP {label}",
        },
    )
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── registry ────────────────────────────────────────────────────────────────


def test_manager_crud_and_masking(tmp_path) -> None:
    manager = McpManager(tmp_path)
    server = manager.add_server("ws-a", "Local Tools", "https://mcp.example.com/mcp", token="secret-token-1234")
    assert server.id
    assert server.enabled is True

    listed = manager.list_servers("ws-a")
    assert len(listed) == 1
    assert listed[0]["token_masked"] == "••••1234"
    assert "auth_token" not in listed[0]
    assert listed[0]["tool_count"] == 0

    # Isolation: another workspace sees nothing and cannot mutate.
    assert manager.list_servers("ws-b") == []
    assert manager.get_server("ws-b", server.id) is None
    assert manager.remove_server("ws-b", server.id) is False
    assert manager.set_enabled("ws-b", server.id, False) is None

    # Enable/disable + remove in owning workspace.
    updated = manager.set_enabled("ws-a", server.id, False)
    assert updated is not None and updated.enabled is False
    assert manager.remove_server("ws-a", server.id) is True
    assert manager.list_servers("ws-a") == []


def test_manager_validates_url_and_name(tmp_path) -> None:
    manager = McpManager(tmp_path)
    import pytest

    with pytest.raises(ValueError):
        manager.add_server("ws-a", "", "https://x.example/mcp")
    with pytest.raises(ValueError):
        manager.add_server("ws-a", "x", "ftp://nope")
    with pytest.raises(ValueError):
        manager.add_server("ws-a", "x", "not-a-url")


def test_refresh_and_call_via_transport(tmp_path, monkeypatch) -> None:
    manager = McpManager(tmp_path)
    server = manager.add_server("ws-a", "Hub", "https://hub.example/mcp", token="tok")

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json is not None
        method = json.get("method")
        if method == "initialize":
            return _FakeResponse({"jsonrpc": "2.0", "id": json.get("id"), "result": {"protocolVersion": "2025-03-26", "serverInfo": {"name": "hub", "version": "1"}}})
        if method == "tools/list":
            tools = [
                {"name": "weather", "description": "Get weather", "inputSchema": {"type": "object"}},
                {"name": "news", "description": "Get news"},
            ]
            return _FakeResponse({"jsonrpc": "2.0", "id": json.get("id"), "result": {"tools": tools}})
        if method == "tools/call":
            return _FakeResponse({"jsonrpc": "2.0", "id": json.get("id"), "result": {"content": [{"type": "text", "text": f"sunny {json['params']['arguments'].get('city', '')}"}]}})
        return _FakeResponse({"jsonrpc": "2.0", "id": json.get("id"), "error": {"code": -32601, "message": "method not found"}})

    monkeypatch.setattr("aeon_mcp.requests.post", fake_post)

    refreshed = manager.refresh_tools("ws-a", server.id)
    assert refreshed["ok"] is True
    assert refreshed["tool_count"] == 2

    agent_tools = manager.agent_tools("ws-a")
    assert len(agent_tools) == 2
    assert {tool["tool"] for tool in agent_tools} == {"weather", "news"}
    assert all(tool["source"] == "mcp" for tool in agent_tools)
    assert all("token" not in str(tool) for tool in agent_tools)

    prompt = manager.agent_prompt_block("ws-a")
    assert "Hub (MCP): news, weather" in prompt
    assert manager.agent_prompt_block("ws-b") == ""

    # Tool call through the manager by server id and by name.
    result = manager.call_tool("ws-a", server.id, "weather", {"city": "Paris"})
    assert result["ok"] is True
    result = manager.call_tool_by_ref("ws-a", "Hub", "weather", {"city": "Rome"})
    assert result["ok"] is True

    # Unknown server / disabled server fail closed.
    assert manager.call_tool("ws-a", "nope", "weather", {})["ok"] is False
    manager.set_enabled("ws-a", server.id, False)
    assert manager.call_tool("ws-a", server.id, "weather", {})["ok"] is False


def test_client_json_rpc_error_and_sse(tmp_path, monkeypatch) -> None:
    client = McpClient("https://x.example/mcp")

    def fake_post(url, headers=None, json=None, timeout=None):
        method = json.get("method")
        if method == "tools/list":
            return _FakeResponse({"jsonrpc": "2.0", "id": json.get("id"), "result": {"tools": [{"name": "a"}]}}, content_type="text/event-stream")
        return _FakeResponse({"jsonrpc": "2.0", "id": json.get("id"), "error": {"code": -32000, "message": "boom"}})

    monkeypatch.setattr("aeon_mcp.requests.post", fake_post)
    assert client.list_tools() == [{"name": "a"}]
    try:
        client.call_tool("a", {})
    except McpError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("expected McpError")


def test_client_transport_error(tmp_path, monkeypatch) -> None:
    client = McpClient("https://x.example/mcp")

    def fake_post(url, headers=None, json=None, timeout=None):
        import requests as real_requests

        raise real_requests.ConnectionError("refused")

    monkeypatch.setattr("aeon_mcp.requests.post", fake_post)
    try:
        client.initialize()
    except McpError as exc:
        assert "transport error" in str(exc)
    else:
        raise AssertionError("expected McpError")


# ── routes ──────────────────────────────────────────────────────────────────


def test_mcp_routes_require_auth(client) -> None:
    assert client.get("/mcp/servers").status_code == 401
    assert client.post("/mcp/servers", json={}).status_code == 401
    assert client.get("/mcp/agent-tools").status_code == 401


def test_mcp_routes_crud_and_isolation(client) -> None:
    token, workspace_id = _register(client, "crud")
    token_b, _ = _register(client, "other")

    response = client.post(
        "/mcp/servers",
        json={"name": "Hub", "url": "https://hub.example/mcp", "token": "super-secret"},
        headers=_headers(token),
    )
    assert response.status_code == 201, response.get_json()
    server = response.get_json()["server"]
    assert server["token_masked"] == "••••cret"

    listed = client.get("/mcp/servers", headers=_headers(token)).get_json()
    assert listed["count"] == 1

    # Other workspace cannot see or touch it.
    other_listed = client.get("/mcp/servers", headers=_headers(token_b)).get_json()
    assert other_listed["count"] == 0
    assert client.delete(f"/mcp/servers/{server['id']}", headers=_headers(token_b)).status_code == 404

    # Invalid URL rejected.
    bad = client.post("/mcp/servers", json={"name": "Bad", "url": "ftp://x"}, headers=_headers(token))
    assert bad.status_code == 400

    # Enable/disable.
    assert client.post(f"/mcp/servers/{server['id']}/disable", headers=_headers(token)).status_code == 200
    disabled = client.get("/mcp/servers", headers=_headers(token)).get_json()["servers"][0]
    assert disabled["enabled"] is False

    # Refresh against an unreachable host fails gracefully (502, no hang).
    response = client.post(f"/mcp/servers/{server['id']}/refresh", headers=_headers(token))
    assert response.status_code == 502
    assert response.get_json()["ok"] is False

    assert client.delete(f"/mcp/servers/{server['id']}", headers=_headers(token)).status_code == 200
    assert client.get("/mcp/servers", headers=_headers(token)).get_json()["count"] == 0


def test_mcp_agent_tools_route(client) -> None:
    token, workspace_id = _register(client, "agent")
    response = client.get("/mcp/agent-tools", headers=_headers(token))
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["workspace_id"] == workspace_id
    assert isinstance(data["tools"], list)


def test_reset_singleton(tmp_path) -> None:
    reset_mcp_manager()
    manager = McpManager(tmp_path)
    assert manager.list_servers("ws") == []
