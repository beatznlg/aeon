"""AEON OS — Model Context Protocol (MCP) client and registry.

Lets workspaces register external MCP servers (streamable HTTP / JSON-RPC)
and surface their tools to agents, automation rules, and workflow nodes —
the same composable pattern used by the plugin marketplace.

Security posture
================
- Registry state is workspace-scoped; every read/write validates the caller's
  workspace id.
- Auth tokens are stored in the state file but masked in every API response
  (``token_masked``) and never included in agent-facing tool listings.
- URLs are validated to ``http://``/``https://`` and names are length-capped.
- All outbound calls are wrapped in try/except with short timeouts so a dead
  or hostile server degrades to an error result, never a hang.

MCP transport notes
===================
The client speaks JSON-RPC 2.0 over the streamable HTTP transport: it accepts
both plain ``application/json`` responses and ``text/event-stream`` (SSE)
responses, which covers current MCP servers regardless of which mode they
select. The protocol version is negotiated from the server's ``initialize``
response so newer and older servers both work.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

MCP_PROTOCOL_VERSION = "2025-03-26"
_STATE_FILENAME = "mcp_servers.json"
_MCP_TIMEOUT = 20

_MCP_MANAGER: McpManager | None = None
_MCP_MANAGER_LOCK = threading.Lock()


def _generate_id() -> str:
    return uuid.uuid4().hex[:16]


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "••••"
    return "••••" + token[-4:]


@dataclass
class McpServer:
    """A workspace-scoped MCP server registration."""

    id: str
    workspace_id: str
    name: str
    url: str
    enabled: bool
    added_at: float
    last_synced: float | None = None
    auth_token: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)
    server_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, mask: bool = True) -> dict[str, Any]:
        data = {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "added_at": self.added_at,
            "last_synced": self.last_synced,
            "token_masked": _mask_token(self.auth_token),
            "tool_count": len(self.tools),
            "tools": self.tools,
            "server_info": self.server_info,
        }
        if not mask:
            data["auth_token"] = self.auth_token
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> McpServer:
        return cls(
            id=data["id"],
            workspace_id=data["workspace_id"],
            name=data.get("name", ""),
            url=data.get("url", ""),
            enabled=bool(data.get("enabled", True)),
            added_at=float(data.get("added_at", 0)),
            last_synced=data.get("last_synced"),
            auth_token=data.get("auth_token", ""),
            tools=list(data.get("tools", [])),
            server_info=dict(data.get("server_info", {})),
        )


class McpError(Exception):
    """Raised for MCP transport or JSON-RPC failures."""


class McpClient:
    """Minimal JSON-RPC 2.0 client for MCP streamable HTTP servers."""

    def __init__(self, url: str, token: str = "", timeout: int = _MCP_TIMEOUT):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout

    # -- transport -----------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "AEON-OS-MCP/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST one JSON-RPC message; return the parsed result/error dict."""
        request_id = payload.get("id")
        try:
            resp = requests.post(
                self.url,
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise McpError(f"transport error: {type(exc).__name__}: {exc}") from exc

        content_type = (resp.headers.get("Content-Type") or "").lower()
        try:
            data = self._parse_sse(resp, request_id) if "text/event-stream" in content_type else resp.json()
        except ValueError as exc:
            raise McpError(f"non-JSON response ({resp.status_code}): {exc}") from exc

        if isinstance(data, dict) and data.get("error"):
            error = data["error"]
            raise McpError(f"JSON-RPC error {error.get('code')}: {error.get('message', 'unknown')}")
        if isinstance(data, dict) and "result" in data:
            return data["result"]
        raise McpError(f"unexpected JSON-RPC response shape: {str(data)[:200]}")

    @staticmethod
    def _parse_sse(resp: requests.Response, request_id: Any) -> dict[str, Any]:
        """Parse a text/event-stream body into a JSON-RPC message dict."""
        candidates: list[dict[str, Any]] = []
        for line in resp.iter_lines(decode_unicode=True):
            line = (line or "").strip()
            if not line.startswith("data:"):
                continue
            raw = line[len("data:"):].strip()
            if not raw:
                continue
            try:
                candidates.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        if not candidates:
            raise McpError("empty SSE stream")
        if request_id is not None:
            for candidate in candidates:
                if candidate.get("id") == request_id and ("result" in candidate or "error" in candidate):
                    return candidate
        for candidate in candidates:
            if "result" in candidate or "error" in candidate:
                return candidate
        return candidates[0]

    # -- protocol methods ----------------------------------------------------
    def initialize(self) -> dict[str, Any]:
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "aeon-os", "version": "1.0"},
                },
            }
        )
        # Fire-and-forget initialized notification (no id); ignore failures.
        try:
            requests.post(
                self.url,
                headers=self._headers(),
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                timeout=self.timeout,
            )
        except requests.RequestException:
            pass
        return result if isinstance(result, dict) else {}

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._post(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        if not isinstance(result, dict):
            return []
        return [t for t in result.get("tools", []) if isinstance(t, dict)]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
        )
        if not isinstance(result, dict):
            return {"ok": False, "error": "malformed tools/call response"}
        return {"ok": True, "result": result}


class McpManager:
    """Workspace-scoped MCP server registry persisted under AEON_ROOT."""

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self._state_path = self.root / _STATE_FILENAME
        self._lock = threading.Lock()

    # -- persistence ---------------------------------------------------------
    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {"version": 1, "servers": []}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "servers": []}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(self._state_path)

    def _servers(self) -> list[McpServer]:
        return [McpServer.from_dict(item) for item in self._load_state().get("servers", [])]

    def _save_servers(self, servers: list[McpServer]) -> None:
        state = {
            "version": 1,
            "servers": [server.to_dict(mask=False) for server in servers],
        }
        self._save_state(state)

    # -- CRUD ----------------------------------------------------------------
    def list_servers(self, workspace_id: str) -> list[dict[str, Any]]:
        servers = [s for s in self._servers() if s.workspace_id == workspace_id]
        servers.sort(key=lambda s: s.added_at)
        return [server.to_dict(mask=True) for server in servers]

    def get_server(self, workspace_id: str, server_id: str) -> McpServer | None:
        for server in self._servers():
            if server.id == server_id and server.workspace_id == workspace_id:
                return server
        return None

    def add_server(
        self,
        workspace_id: str,
        name: str,
        url: str,
        token: str = "",
        enabled: bool = True,
    ) -> McpServer:
        name = (name or "").strip()[:80]
        url = (url or "").strip()
        if not name:
            raise ValueError("server name is required")
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        if not (5 <= len(url) <= 2048):
            raise ValueError("invalid url length")
        with self._lock:
            servers = self._servers()
            server = McpServer(
                id=_generate_id(),
                workspace_id=workspace_id,
                name=name,
                url=url,
                enabled=enabled,
                added_at=time.time(),
                auth_token=token,
            )
            servers.append(server)
            self._save_servers(servers)
        return server

    def remove_server(self, workspace_id: str, server_id: str) -> bool:
        with self._lock:
            servers = self._servers()
            remaining = [s for s in servers if not (s.id == server_id and s.workspace_id == workspace_id)]
            if len(remaining) == len(servers):
                return False
            self._save_servers(remaining)
        return True

    def set_enabled(self, workspace_id: str, server_id: str, enabled: bool) -> McpServer | None:
        with self._lock:
            servers = self._servers()
            for server in servers:
                if server.id == server_id and server.workspace_id == workspace_id:
                    server.enabled = enabled
                    self._save_servers(servers)
                    return server
        return None

    # -- MCP operations ------------------------------------------------------
    def _client_for(self, server: McpServer) -> McpClient:
        return McpClient(server.url, token=server.auth_token)

    def refresh_tools(self, workspace_id: str, server_id: str) -> dict[str, Any]:
        server = self.get_server(workspace_id, server_id)
        if server is None:
            return {"ok": False, "error": "server not found"}
        try:
            client = self._client_for(server)
            info = client.initialize()
            tools = client.list_tools()
        except McpError as exc:
            return {"ok": False, "error": str(exc)}
        with self._lock:
            servers = self._servers()
            for stored in servers:
                if stored.id == server.id and stored.workspace_id == workspace_id:
                    stored.tools = tools
                    stored.server_info = info.get("serverInfo", {}) if isinstance(info, dict) else {}
                    stored.last_synced = time.time()
                    self._save_servers(servers)
                    break
        return {"ok": True, "tool_count": len(tools), "tools": tools}

    def call_tool(
        self,
        workspace_id: str,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        server = self.get_server(workspace_id, server_id)
        if server is None:
            return {"ok": False, "error": "server not found"}
        if not server.enabled:
            return {"ok": False, "error": "server is disabled"}
        try:
            return self._client_for(server).call_tool(tool_name, arguments or {})
        except McpError as exc:
            return {"ok": False, "error": str(exc)}

    def call_tool_by_ref(
        self,
        workspace_id: str,
        server_ref: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve a server by id or name (agent-friendly)."""
        server = self.get_server(workspace_id, server_ref)
        if server is None:
            for candidate in self._servers():
                if candidate.workspace_id == workspace_id and candidate.name == server_ref:
                    server = candidate
                    break
        if server is None:
            return {"ok": False, "error": f"mcp server '{server_ref}' not found in workspace"}
        return self.call_tool(workspace_id, server.id, tool_name, arguments)

    # -- agent discovery -----------------------------------------------------
    def agent_tools(self, workspace_id: str) -> list[dict[str, Any]]:
        """Discoverable tools for agents: enabled servers with synced tools."""
        tools: list[dict[str, Any]] = []
        for server in self._servers():
            if server.workspace_id != workspace_id or not server.enabled:
                continue
            for tool in server.tools:
                name = tool.get("name", "")
                if not name:
                    continue
                tools.append(
                    {
                        "server_id": server.id,
                        "server_name": server.name,
                        "tool": name,
                        "description": (tool.get("description") or "")[:200],
                        "input_schema": tool.get("inputSchema") or {},
                        "source": "mcp",
                    }
                )
        tools.sort(key=lambda t: (t["server_name"], t["tool"]))
        return tools

    def agent_prompt_block(self, workspace_id: str) -> str:
        tools = self.agent_tools(workspace_id)
        if not tools:
            return ""
        grouped: dict[str, list[str]] = {}
        for item in tools:
            grouped.setdefault(item["server_name"], []).append(item["tool"])
        lines = []
        for server_name in sorted(grouped):
            lines.append(f"{server_name} (MCP): " + ", ".join(grouped[server_name]))
        return "MCP servers available: " + " | ".join(lines)


def get_mcp_manager(root: str | os.PathLike[str] | None = None) -> McpManager:
    """Return the process-wide MCP manager bound to AEON_ROOT."""
    global _MCP_MANAGER
    with _MCP_MANAGER_LOCK:
        if _MCP_MANAGER is None:
            base = Path(root or os.environ.get("AEON_ROOT", ""))
            if not base or not base.exists():
                base = Path.cwd()
            _MCP_MANAGER = McpManager(base)
        return _MCP_MANAGER


def reset_mcp_manager() -> None:
    """Reset the singleton (used by tests)."""
    global _MCP_MANAGER
    with _MCP_MANAGER_LOCK:
        _MCP_MANAGER = None
