"""AEON OS capability registry.

The registry is the stable composition boundary for agents, automations, and
frontends. It presents built-in tools, installed marketplace entry points, and
enabled MCP tools through one metadata contract without leaking credentials or
allowing a caller to select another workspace.
"""

from __future__ import annotations

import os
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

_BUILTIN_DESCRIPTIONS: dict[str, str] = {
    "math": "Evaluate a mathematical expression.",
    "search": "Search the public web for relevant results.",
    "fetch": "Fetch and extract text from a public URL.",
    "read_skill": "Read a saved AEON skill.",
    "write_skill": "Write a saved AEON skill.",
    "github_search": "Search public GitHub code.",
    "api_catalog_search": "Search the public API catalog.",
    "api_fetch": "Safely fetch a public HTTP or HTTPS API.",
    "plugin_call": "Invoke an installed marketplace plugin entry point.",
    "list_plugins": "Discover installed marketplace plugin entry points.",
    "mcp_call": "Invoke a tool on an enabled MCP server.",
    "list_mcp": "Discover enabled MCP server tools.",
    "bounty_list": "List available work bounties.",
    "bounty_submit": "Submit work for a bounty.",
    "service_quote": "Get a quote for an AEON service.",
    "list_capabilities": "Discover every callable capability in this workspace.",
    "capability_call": "Invoke a capability through the unified registry.",
}


def _workspace_id(workspace_id: str | None) -> str:
    value = str(workspace_id or os.environ.get("AEON_WORKSPACE_ID") or "default").strip()
    return value or "default"


def _root(root: str | os.PathLike[str] | None) -> Path:
    return Path(root or os.environ.get("AEON_ROOT", "./aeon_state/server"))


def _validate_schema_value(value: Any, schema: dict[str, Any], path: str = "arguments") -> str | None:
    """Validate the small JSON Schema subset used by MCP tool definitions.

    MCP servers commonly describe tool inputs with ``type``, ``properties``,
    ``required``, ``additionalProperties``, ``items``, and ``enum``. Keeping
    this validator dependency-free lets the capability boundary enforce those
    contracts without importing the heavyweight agent kernel. Unknown schema
    keywords are intentionally ignored for forward compatibility.
    """
    if not isinstance(schema, dict):
        return None

    if "enum" in schema and value not in schema["enum"]:
        return f"{path} must be one of the declared values"

    expected = schema.get("type")
    type_matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if expected in type_matches and not type_matches[expected]:
        return f"{path} must be a {expected}"

    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        if not isinstance(properties, dict):
            return f"{path} has an invalid properties schema"
        required = schema.get("required") or []
        if isinstance(required, list):
            missing = [name for name in required if name not in value]
            if missing:
                return f"{path} is missing required fields: {', '.join(map(str, missing))}"
        if schema.get("additionalProperties") is False:
            unknown = [name for name in value if name not in properties]
            if unknown:
                return f"{path} contains unknown fields: {', '.join(map(str, unknown))}"
        for name, child_schema in properties.items():
            if name in value:
                error = _validate_schema_value(value[name], child_schema, f"{path}.{name}")
                if error:
                    return error

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            error = _validate_schema_value(item, schema["items"], f"{path}[{index}]")
            if error:
                return error

    return None


def validate_capability_arguments(capability: dict[str, Any], arguments: Any) -> str | None:
    """Return a user-safe validation error for a capability invocation."""
    if not isinstance(arguments, dict):
        return "arguments must be an object"
    schema = capability.get("input_schema") or {}
    if not isinstance(schema, dict) or not schema:
        return None
    return _validate_schema_value(arguments, schema)


def required_capability_role(capability: dict[str, Any]) -> str:
    """Return the minimum workspace role required to invoke a capability."""
    permissions = {str(permission).lower() for permission in capability.get("permissions", [])}
    if "admin" in permissions:
        return "ADMIN"
    if permissions & {"execute", "external", "network", "write", "notify"}:
        return "OPERATOR"
    return "VIEWER"


def evaluate_capability_policy(workspace_id: str, capability_id: str) -> dict[str, Any]:
    """Evaluate durable workspace capability rules before execution.

    Capability policy rules live in the existing ``automation_policies`` table
    so they are workspace-scoped and survive process restarts. A policy may
    provide ``blocked_capabilities`` or an ``allowed_capabilities`` allowlist;
    both accept exact ids and shell-style wildcards (for example,
    ``plugin:vendor:*``). Missing policy tables are treated as no configured
    policy for backwards-compatible local bootstrap. A configured database
    failure fails closed rather than allowing an ungoverned invocation.
    """
    try:
        from sqlalchemy import inspect

        from aeon_db import get_db, list_automation_policies

        db = get_db()
        if "automation_policies" not in inspect(db.engine).get_table_names():
            return {"allowed": True, "effect": "allow", "violations": []}
        policies = list_automation_policies(workspace_id, enabled_only=True)
    except Exception:
        return {
            "allowed": False,
            "effect": "block",
            "violations": [
                {
                    "policy_id": None,
                    "policy_name": None,
                    "effect": "block",
                    "rule": "policy_store",
                    "message": "workspace capability policy is unavailable",
                }
            ],
        }

    violations: list[dict[str, Any]] = []
    for policy in policies:
        rules = policy.rules if isinstance(policy.rules, dict) else {}
        blocked = rules.get("blocked_capabilities") or rules.get("capability_denylist") or []
        allowed = rules.get("allowed_capabilities") or rules.get("capability_allowlist") or []
        if isinstance(blocked, str):
            blocked = [blocked]
        if isinstance(allowed, str):
            allowed = [allowed]
        blocked = [str(pattern).strip() for pattern in blocked if str(pattern).strip()]
        allowed = [str(pattern).strip() for pattern in allowed if str(pattern).strip()]

        if any(fnmatchcase(capability_id, pattern) for pattern in blocked):
            violations.append(
                {
                    "policy_id": policy.id,
                    "policy_name": policy.name,
                    "effect": policy.effect,
                    "rule": "blocked_capabilities",
                    "message": f"Capability '{capability_id}' is blocked by policy",
                }
            )
        if allowed and not any(fnmatchcase(capability_id, pattern) for pattern in allowed):
            violations.append(
                {
                    "policy_id": policy.id,
                    "policy_name": policy.name,
                    "effect": policy.effect,
                    "rule": "allowed_capabilities",
                    "message": f"Capability '{capability_id}' is not in the policy allowlist",
                }
            )

    if not violations:
        return {"allowed": True, "effect": "allow", "violations": []}

    blocking = [violation for violation in violations if violation["effect"] == "block"]
    effect = "block" if blocking else "require_approval"
    return {"allowed": False, "effect": effect, "violations": violations}


class CapabilityRegistry:
    """Discover and invoke capabilities within one workspace boundary."""

    def __init__(self, root: str | os.PathLike[str] | None = None):
        self.root = _root(root)

    def discover(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        """Return stable, credential-free capability metadata."""
        workspace = _workspace_id(workspace_id)
        capabilities: list[dict[str, Any]] = []

        # Import lazily: aeon has an intentionally heavyweight local-model
        # bootstrap and should not be loaded by metadata-only callers.
        try:
            from aeon import TOOLS
        except (ImportError, AttributeError):
            # Lightweight route tests and metadata workers may intentionally
            # stub the heavyweight kernel. Keep the built-in contract visible.
            TOOLS = _BUILTIN_DESCRIPTIONS

        for name in sorted(TOOLS):
            capabilities.append(
                {
                    "id": f"builtin:{name}",
                    "name": name,
                    "description": _BUILTIN_DESCRIPTIONS.get(name, "Built-in AEON tool."),
                    "source": "builtin",
                    "available": True,
                    "input_schema": {"type": "object", "additionalProperties": True},
                    "permissions": ["execute"],
                }
            )

        from aeon_marketplace import get_marketplace_manager

        marketplace = get_marketplace_manager(self.root)
        for plugin in marketplace.agent_tools(workspace):
            manifest = marketplace.get_plugin(plugin["plugin_id"])
            plugin_permissions = list(manifest.permissions) if manifest is not None else ["execute"]
            for entry, description in sorted(plugin.get("entry_points", {}).items()):
                capabilities.append(
                    {
                        "id": f"plugin:{plugin['plugin_id']}:{entry}",
                        "name": f"{plugin['name']} · {entry}",
                        "description": description or plugin.get("description", ""),
                        "source": "marketplace",
                        "available": True,
                        "plugin_id": plugin["plugin_id"],
                        "entry": entry,
                        "verified": bool(plugin.get("verified", False)),
                        "category": plugin.get("category"),
                        "input_schema": {"type": "object", "additionalProperties": True},
                        "permissions": plugin_permissions,
                    }
                )

        from aeon_mcp import McpManager

        for tool in McpManager(self.root).agent_tools(workspace):
            capabilities.append(
                {
                    "id": f"mcp:{tool['server_id']}:{tool['tool']}",
                    "name": f"{tool['server_name']} · {tool['tool']}",
                    "description": tool.get("description", ""),
                    "source": "mcp",
                    "available": True,
                    "server_id": tool["server_id"],
                    "server_name": tool["server_name"],
                    "tool": tool["tool"],
                    "input_schema": tool.get("input_schema") or {},
                    "permissions": ["execute", "external"],
                }
            )

        return sorted(capabilities, key=lambda item: (item["source"], item["id"]))

    def prompt_block(self, workspace_id: str | None = None) -> str:
        """Render compact discovery text suitable for an agent system prompt."""
        capabilities = self.discover(workspace_id)
        if not capabilities:
            return ""
        lines = ["Unified capabilities (invoke with capability_call and the capability id):"]
        for capability in capabilities:
            lines.append(f"  - {capability['id']}: {capability['description']}")
        return "\n".join(lines)

    def get(
        self, workspace_id: str | None, capability_id: str
    ) -> dict[str, Any] | None:
        """Resolve a capability from the current workspace only."""
        return next((item for item in self.discover(workspace_id) if item["id"] == capability_id), None)

    def invoke(
        self,
        workspace_id: str | None,
        capability_id: str,
        arguments: dict[str, Any] | None = None,
        user_role: str | None = "OPERATOR",
        *,
        approval_granted: bool = False,
    ) -> dict[str, Any]:
        """Invoke a capability, optionally honoring a persisted approval.

        ``approval_granted`` is only used by the approval resolver after it has
        loaded a workspace-scoped approval. It never bypasses role checks or a
        blocking policy; it only allows a still-active ``require_approval``
        policy to proceed after human approval.
        """
        workspace = _workspace_id(workspace_id)
        args = arguments if arguments is not None else {}

        capability = self.get(workspace, capability_id)
        if capability is None:
            return {"ok": False, "error": "capability not found in workspace"}

        required_role = required_capability_role(capability)
        from aeon_auth import has_role

        if not has_role(user_role, required_role):
            return {"ok": False, "error": f"capability requires {required_role} role"}

        policy_result = evaluate_capability_policy(workspace, capability_id)
        if not policy_result["allowed"]:
            if policy_result["effect"] == "require_approval" and approval_granted:
                pass
            else:
                if policy_result["effect"] == "require_approval":
                    error = "capability requires approval by workspace policy"
                else:
                    error = "capability blocked by workspace policy"
                return {"ok": False, "error": error, "policy": policy_result["violations"]}

        validation_error = validate_capability_arguments(capability, args)
        if validation_error:
            return {"ok": False, "error": validation_error}

        source = capability["source"]
        try:
            if source == "builtin":
                from aeon import _safe_run

                return _safe_run(capability["name"], args, str(self.root))
            if source == "marketplace":
                from aeon_marketplace import get_marketplace_manager

                return get_marketplace_manager(self.root).run_entry(
                    workspace, capability["plugin_id"], capability["entry"], args
                )
            if source == "mcp":
                from aeon_mcp import McpManager

                return McpManager(self.root).call_tool(
                    workspace, capability["server_id"], capability["tool"], args
                )
        except Exception as exc:  # capability boundaries must not crash callers
            return {"ok": False, "error": f"capability invocation failed: {type(exc).__name__}: {exc}"}
        return {"ok": False, "error": "unsupported capability source"}


def get_capability_registry(root: str | os.PathLike[str] | None = None) -> CapabilityRegistry:
    """Create a registry bound to the configured AEON state root."""
    return CapabilityRegistry(root)
