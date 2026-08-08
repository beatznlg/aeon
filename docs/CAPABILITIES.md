# AEON OS — Unified Capability Registry

The capability registry is AEON's common composition boundary for built-in
kernel tools, installed marketplace plugin entry points, and enabled MCP tools.
It gives agents, automations, workflows, and the frontend one stable metadata
contract for discovering what can be called in the current workspace.

## What is discoverable

Every capability has a stable identifier, source, description, input schema,
and permissions metadata:

| Source | Identifier | Description |
| --- | --- | --- |
| Built-in | `builtin:<tool>` | Core AEON kernel tools such as `math`, `search`, and `fetch` |
| Marketplace | `plugin:<plugin_id>:<entry>` | Entry points from installed and enabled plugins |
| MCP | `mcp:<server_id>:<tool>` | Tools synced from enabled MCP servers |

Discovery metadata is credential-free. Marketplace configuration and MCP bearer
tokens are never returned in capability responses.

## HTTP API

All routes are workspace-scoped using the authenticated caller's workspace.
Reads require `VIEWER`; invocation requires `OPERATOR`.

| Method | Route | Role | Purpose |
| --- | --- | --- | --- |
| GET | `/capabilities` | VIEWER | List every capability visible in the workspace |
| GET | `/capabilities/<capability_id>` | VIEWER | Resolve one capability's metadata |
| POST | `/capabilities/invoke` | OPERATOR | Invoke a capability with JSON arguments |

Example discovery request:

```http
GET /capabilities
Authorization: Bearer <token>
```

Example invocation:

```http
POST /capabilities/invoke
Authorization: Bearer <token>
Content-Type: application/json

{
  "capability_id": "builtin:math",
  "arguments": { "expr": "2 + 2" }
}
```

The response preserves the underlying capability result under `result`. Unknown
or unavailable identifiers fail closed and cannot be used to cross workspace
boundaries.

## Frontend

Authenticated users can inspect the live registry at
`/os/capabilities` (also available as **Capabilities** in the sidebar). The
page provides:

- Source counts for core, marketplace, and MCP capabilities.
- Search and source filters.
- Per-capability descriptions, permissions, and input schema.
- A reviewed JSON argument editor and invocation result panel.
- Direct links to the Marketplace and MCP server management pages.

The Next.js proxy at `/api/os/capabilities` forwards only the caller's
`Authorization` header to the Flask API and keeps responses dynamic.

## Extension flow

1. Install and enable a plugin in the Marketplace, or register and sync an MCP
   server under Integrations.
2. The registry discovers the enabled entry points/tools for the current
   workspace.
3. Agents and UI clients use the returned capability id to invoke the same
   workspace-scoped operation.
4. Disable or uninstall the source to remove it from discovery immediately.

The registry is a composition layer, not a certification or trust boundary for
arbitrary third-party code. Marketplace execution continues to follow the
marketplace security model and MCP calls remain external, authenticated
operations with bounded failures.

## Tests

`tests/test_capabilities.py` covers:

- Built-in and plugin discovery with workspace isolation.
- Enabled/disabled MCP tool visibility.
- Built-in and plugin invocation.
- Fail-closed unknown capability ids.
- Authenticated route behavior and credential-free responses.
