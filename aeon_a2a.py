"""AEON OS — A2A (Agent-to-Agent) interoperability layer.

Implements the Agent2Agent (A2A) interoperability surface alongside the
existing MCP tool layer (docs/MCP.md). MCP and A2A solve different problems
and coexist here: MCP brings *tools* into the workspace; A2A discovers and
delegates work to *remote agents*.

Security posture
================
- Registry state is workspace-scoped; every read/write validates the caller's
  workspace id (same pattern as aeon_mcp.McpManager).
- Auth tokens are stored in the state file but masked in every API response
  and never included in agent-facing agent-card listings.
- URLs are validated to ``http://``/``https://`` with a length cap; names are
  length-capped.
- Every outbound delegation is wrapped in a hard timeout, bounded retries
  (idempotent methods only), and a per-endpoint circuit breaker so a dead or
  hostile peer degrades to a structured error, never a hang.

A2A protocol notes
==================
The client speaks JSON-RPC 2.0 over HTTP, mirroring the A2A "message/send"
method shape. Discovery follows the ``/.well-known/agent.json`` agent-card
convention. Both are abstracted behind :class:`A2aClient` so AEON does not
depend on any single wire version.
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

_STATE_FILENAME = "a2a_agents.json"
_A2A_TIMEOUT = 20
_MAX_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 0.5
# Circuit breaker: after this many consecutive failures an endpoint is
# tripped for the cooldown window; calls fail fast without touching it.
_BREAKER_THRESHOLD = 3
_BREAKER_COOLDOWN_SECONDS = 60

_A2A_MANAGER: A2aManager | None = None
_A2A_MANAGER_LOCK = threading.Lock()


def _generate_id() -> str:
    return uuid.uuid4().hex[:16]


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "••••"
    return "••••" + token[-4:]


@dataclass
class A2aAgent:
    """A workspace-scoped remote agent registration."""

    id: str
    workspace_id: str
    name: str
    url: str
    enabled: bool
    added_at: float
    auth_token: str = ""
    last_synced: float | None = None
    # Cached agent card (skills, capabilities, provider info).
    agent_card: dict[str, Any] = field(default_factory=dict)
    # Resilience bookkeeping (round-trips through to_dict/from_dict).
    consecutive_failures: int = 0
    breaker_opened_at: float | None = None

    def to_dict(self, mask: bool = True) -> dict[str, Any]:
        data = {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "added_at": self.added_at,
            "token_masked": _mask_token(self.auth_token),
            "last_synced": self.last_synced,
            "agent_card": self.agent_card,
            "breaker_open": self.breaker_open,
            # Resilience bookkeeping must round-trip through storage or the
            # circuit breaker would reset on every save/load cycle.
            "consecutive_failures": self.consecutive_failures,
            "breaker_opened_at": self.breaker_opened_at,
        }
        if not mask:
            data["auth_token"] = self.auth_token
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> A2aAgent:
        return cls(
            id=data["id"],
            workspace_id=data["workspace_id"],
            name=data.get("name", ""),
            url=data.get("url", ""),
            enabled=bool(data.get("enabled", True)),
            added_at=float(data.get("added_at", 0)),
            auth_token=data.get("auth_token", ""),
            last_synced=data.get("last_synced"),
            agent_card=dict(data.get("agent_card", {})),
            consecutive_failures=int(data.get("consecutive_failures", 0)),
            breaker_opened_at=data.get("breaker_opened_at"),
        )

    # -- circuit breaker ------------------------------------------------------

    @property
    def breaker_open(self) -> bool:
        if self.breaker_opened_at is None:
            return False
        # Cooldown elapsed: half-open (allow one probe through).
        return (time.time() - self.breaker_opened_at) < _BREAKER_COOLDOWN_SECONDS

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.breaker_opened_at = None

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= _BREAKER_THRESHOLD:
            self.breaker_opened_at = time.time()
            self.consecutive_failures = 0


class A2aError(Exception):
    """Raised for A2A transport or JSON-RPC failures."""


class A2aClient:
    """JSON-RPC 2.0 client for remote A2A agents with resilience gates."""

    def __init__(
        self,
        url: str,
        token: str = "",
        timeout: int = _A2A_TIMEOUT,
        max_retries: int = _MAX_RETRIES,
        retry_backoff_seconds: float = _RETRY_BACKOFF_SECONDS,
    ):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    # -- transport ------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AEON-OS-A2A/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _post_once(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = payload.get("id")
        try:
            resp = requests.post(
                self.url,
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise A2aError(f"transport error: {type(exc).__name__}: {exc}") from exc

        if resp.status_code >= 500:
            raise A2aError(f"remote agent error: HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise A2aError(f"non-JSON response ({resp.status_code})") from exc

        if isinstance(data, dict) and data.get("error"):
            error = data["error"]
            raise A2aError(
                f"JSON-RPC error {error.get('code')}: {error.get('message', 'unknown')}"
            )
        if isinstance(data, dict) and "result" in data:
            return data["result"]
        raise A2aError(f"unexpected JSON-RPC response shape: {str(data)[:200]}")

    def _post(self, payload: dict[str, Any], *, retryable: bool) -> dict[str, Any]:
        """POST with bounded retries for transient transport/5xx failures.

        Retries are only applied when the caller marks the operation safe to
        repeat (discovery, queries). One-way task mutations are sent once.
        """
        attempts = (self.max_retries + 1) if retryable else 1
        last_exc: A2aError | None = None
        for attempt in range(attempts):
            try:
                return self._post_once(payload)
            except A2aError as exc:
                last_exc = exc
                transient = (
                    str(exc).startswith("transport error:")
                    or str(exc).startswith("remote agent error: HTTP 5")
                )
                if not retryable or not transient or attempt == attempts - 1:
                    raise
                time.sleep(self.retry_backoff_seconds * (2**attempt))
        raise last_exc or A2aError("unreachable")

    # -- protocol methods -----------------------------------------------------

    def fetch_agent_card(self, base_url: str | None = None) -> dict[str, Any]:
        """GET ``/.well-known/agent.json`` discovery document."""
        base = (base_url or self.url).rstrip("/")
        url = f"{base}/.well-known/agent.json"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise A2aError(f"transport error: {type(exc).__name__}: {exc}") from exc
        if resp.status_code >= 500:
            raise A2aError(f"remote agent error: HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise A2aError(f"non-JSON agent card ({resp.status_code})") from exc
        if not isinstance(data, dict):
            raise A2aError("agent card is not an object")
        return data

    def send_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Delegate work via ``message/send`` (sent exactly once — not retried)."""
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "message/send",
                "params": {"message": message},
            },
            retryable=False,
        )
        if not isinstance(result, dict):
            return {"ok": False, "error": "malformed message/send response"}
        return {"ok": True, "result": result}

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Query task state via ``tasks/get`` (idempotent — retryable)."""
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tasks/get",
                "params": {"id": task_id},
            },
            retryable=True,
        )
        if not isinstance(result, dict):
            return {"ok": False, "error": "malformed tasks/get response"}
        return {"ok": True, "result": result}


class A2aManager:
    """Workspace-scoped A2A agent registry persisted under AEON_ROOT."""

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self._state_path = self.root / _STATE_FILENAME
        self._lock = threading.Lock()

    # -- persistence ----------------------------------------------------------

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {"version": 1, "agents": []}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "agents": []}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(self._state_path)

    def _agents(self) -> list[A2aAgent]:
        return [A2aAgent.from_dict(item) for item in self._load_state().get("agents", [])]

    def _save_agents(self, agents: list[A2aAgent]) -> None:
        state = {
            "version": 1,
            "agents": [agent.to_dict(mask=False) for agent in agents],
        }
        self._save_state(state)

    # -- CRUD -----------------------------------------------------------------

    def list_agents(self, workspace_id: str) -> list[dict[str, Any]]:
        agents = [a for a in self._agents() if a.workspace_id == workspace_id]
        agents.sort(key=lambda a: a.added_at)
        return [agent.to_dict(mask=True) for agent in agents]

    def get_agent(self, workspace_id: str, agent_id: str) -> A2aAgent | None:
        for agent in self._agents():
            if agent.id == agent_id and agent.workspace_id == workspace_id:
                return agent
        return None

    def add_agent(
        self,
        workspace_id: str,
        name: str,
        url: str,
        token: str = "",
        enabled: bool = True,
    ) -> A2aAgent:
        name = (name or "").strip()[:80]
        url = (url or "").strip()
        if not name:
            raise ValueError("agent name is required")
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        if not (5 <= len(url) <= 2048):
            raise ValueError("invalid url length")
        with self._lock:
            agents = self._agents()
            agent = A2aAgent(
                id=_generate_id(),
                workspace_id=workspace_id,
                name=name,
                url=url,
                enabled=enabled,
                added_at=time.time(),
                auth_token=token,
            )
            agents.append(agent)
            self._save_agents(agents)
        return agent

    def remove_agent(self, workspace_id: str, agent_id: str) -> bool:
        with self._lock:
            agents = self._agents()
            remaining = [a for a in agents if not (a.id == agent_id and a.workspace_id == workspace_id)]
            if len(remaining) == len(agents):
                return False
            self._save_agents(remaining)
        return True

    def set_enabled(self, workspace_id: str, agent_id: str, enabled: bool) -> A2aAgent | None:
        with self._lock:
            agents = self._agents()
            for agent in agents:
                if agent.id == agent_id and agent.workspace_id == workspace_id:
                    agent.enabled = enabled
                    self._save_agents(agents)
                    return agent
        return None

    # -- A2A operations -------------------------------------------------------

    def _client_for(self, agent: A2aAgent) -> A2aClient:
        return A2aClient(agent.url, token=agent.auth_token)

    def refresh_agent(self, workspace_id: str, agent_id: str) -> dict[str, Any]:
        """Fetch and cache the remote agent card for discovery."""
        agent = self.get_agent(workspace_id, agent_id)
        if agent is None:
            return {"ok": False, "error": "agent not found"}
        try:
            card = self._client_for(agent).fetch_agent_card()
        except A2aError as exc:
            self._record_failure(workspace_id, agent.id)
            return {"ok": False, "error": str(exc)}
        self._record_success(workspace_id, agent.id)
        with self._lock:
            agents = self._agents()
            for stored in agents:
                if stored.id == agent.id and stored.workspace_id == workspace_id:
                    stored.agent_card = card
                    stored.last_synced = time.time()
                    self._save_agents(agents)
                    break
        return {"ok": True, "agent_card": card}

    def _mutate_breaker(self, workspace_id: str, agent_id: str, success: bool) -> None:
        with self._lock:
            agents = self._agents()
            for stored in agents:
                if stored.id == agent_id and stored.workspace_id == workspace_id:
                    if success:
                        stored.record_success()
                    else:
                        stored.record_failure()
                    self._save_agents(agents)
                    break

    def _record_success(self, workspace_id: str, agent_id: str) -> None:
        self._mutate_breaker(workspace_id, agent_id, True)

    def _record_failure(self, workspace_id: str, agent_id: str) -> None:
        self._mutate_breaker(workspace_id, agent_id, False)

    def delegate(
        self,
        workspace_id: str,
        agent_id: str,
        message: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a task message to a remote agent (A2A ``message/send``)."""
        agent = self.get_agent(workspace_id, agent_id)
        if agent is None:
            return {"ok": False, "error": "agent not found"}
        if not agent.enabled:
            return {"ok": False, "error": "agent is disabled"}
        if agent.breaker_open:
            return {
                "ok": False,
                "error": "circuit breaker open for this agent; retry after cooldown",
            }
        try:
            result = self._client_for(agent).send_message(message)
        except A2aError as exc:
            self._record_failure(workspace_id, agent.id)
            return {"ok": False, "error": str(exc)}
        self._record_success(workspace_id, agent.id)
        return result

    def task_status(self, workspace_id: str, agent_id: str, task_id: str) -> dict[str, Any]:
        """Query remote task state (A2A ``tasks/get``)."""
        agent = self.get_agent(workspace_id, agent_id)
        if agent is None:
            return {"ok": False, "error": "agent not found"}
        if agent.breaker_open:
            return {
                "ok": False,
                "error": "circuit breaker open for this agent; retry after cooldown",
            }
        try:
            result = self._client_for(agent).get_task(task_id)
        except A2aError as exc:
            self._record_failure(workspace_id, agent.id)
            return {"ok": False, "error": str(exc)}
        self._record_success(workspace_id, agent.id)
        return result

    # -- agent discovery ------------------------------------------------------

    def agent_directory(self, workspace_id: str) -> list[dict[str, Any]]:
        """Discoverable remote agents for the delegation prompt block."""
        entries: list[dict[str, Any]] = []
        for agent in self._agents():
            if agent.workspace_id != workspace_id or not agent.enabled:
                continue
            card = agent.agent_card or {}
            skills = card.get("skills") or []
            skill_names = []
            for skill in skills if isinstance(skills, list) else []:
                if isinstance(skill, dict) and skill.get("name"):
                    skill_names.append(str(skill["name"])[:80])
            entries.append(
                {
                    "agent_id": agent.id,
                    "name": agent.name,
                    "url": agent.url,
                    "description": str(card.get("description") or "")[:200],
                    "skills": skill_names,
                    "breaker_open": agent.breaker_open,
                    "source": "a2a",
                }
            )
        entries.sort(key=lambda e: e["name"])
        return entries

    def agent_prompt_block(self, workspace_id: str) -> str:
        entries = self.agent_directory(workspace_id)
        if not entries:
            return ""
        lines = []
        for entry in entries:
            skills = ", ".join(entry["skills"]) if entry["skills"] else "no listed skills"
            lines.append(f"{entry['name']} (A2A): {skills}")
        return "Remote agents available (A2A): " + " | ".join(lines)


def get_a2a_manager(root: str | os.PathLike[str] | None = None) -> A2aManager:
    """Return the process-wide A2A manager bound to AEON_ROOT."""
    global _A2A_MANAGER
    with _A2A_MANAGER_LOCK:
        if _A2A_MANAGER is None:
            base = Path(root or os.environ.get("AEON_ROOT", ""))
            if not base or not base.exists():
                base = Path.cwd()
            _A2A_MANAGER = A2aManager(base)
        return _A2A_MANAGER


def reset_a2a_manager() -> None:
    """Reset the singleton (used by tests)."""
    global _A2A_MANAGER
    with _A2A_MANAGER_LOCK:
        _A2A_MANAGER = None


__all__ = [
    "A2aAgent",
    "A2aClient",
    "A2aError",
    "A2aManager",
    "get_a2a_manager",
    "reset_a2a_manager",
]
