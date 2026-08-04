# AEON OS — Model Context Protocol (MCP) Support

AEON OS can connect to external MCP servers (streamable HTTP / JSON-RPC 2.0)
and expose their tools to agents, automation rules, and workflow nodes — the
same composable pattern used by the plugin marketplace.

## Register a server

```http
POST /mcp/servers
Authorization: Bearer <token>

{
  "name": "Internal Tools",
  "url": "https://mcp.example.com/mcp",
  "token": "optional-bearer-token",
  "enabled": true
}
```

The URL must be `http://` or `https://`. Auth tokens are stored per-workspace,
masked in every API response (`token_masked`), and never sent to agents.

## Sync tools

```http
POST /mcp/servers/<server_id>/refresh
```

Runs the MCP handshake (`initialize` → `tools/list`) and stores the discovered
tool schemas. The client accepts both plain JSON and `text/event-stream`
(SSE) responses, so it works with current MCP servers in either mode. The
protocol version is negotiated from the server's `initialize` response.

## Call a tool

```http
POST /mcp/tools/call
{ "server_id": "<id>", "tool": "weather", "arguments": { "city": "Paris" } }
```

## Agent integration

Agents in the workspace automatically discover enabled servers with synced
tools. Two kernel tools are registered:

- `list_mcp` — enumerate the workspace's MCP servers and their tools.
- `mcp_call` — call `{server: id-or-name, tool: ..., arguments: {...}}`;
  the server is resolved by id or name within the workspace.

The `act()` system prompt also includes a compact "MCP servers available:"
block, so the model knows what external capabilities exist before it calls a
tool. The chat "Plugin tools" drawer surfaces the same discovery via
`GET /mcp/agent-tools`.

## Security posture

- Workspace-scoped registry: every read/write validates the caller's workspace.
- Tokens masked in listings; tool schemas carry no credentials.
- Short timeouts and fail-closed errors: a dead or hostile server degrades to
  an error result, never a hang.
- Reads require VIEWER, mutations require OPERATOR.

## Routes

| Method | Path | Role |
| --- | --- | --- |
| GET | `/mcp/servers` | VIEWER |
| POST | `/mcp/servers` | OPERATOR |
| DELETE | `/mcp/servers/<id>` | OPERATOR |
| POST | `/mcp/servers/<id>/enable` / `/disable` | OPERATOR |
| POST | `/mcp/servers/<id>/refresh` | OPERATOR |
| POST | `/mcp/tools/call` | OPERATOR |
| GET | `/mcp/agent-tools` | VIEWER |
