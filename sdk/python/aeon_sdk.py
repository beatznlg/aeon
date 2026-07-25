"""
AEON OS — Python SDK
====================
A lightweight Python client for the AEON OS Flask backend.

Install locally:
    pip install -e sdk/python

Basic usage:
    from aeon_sdk import AeonClient

    client = AeonClient("https://your-aeon-backend.up.railway.app", api_key="aeon_...")
    print(client.health())
    print(client.chat("What is the integral of x^2?"))
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests


class AeonError(Exception):
    """Base exception for AEON SDK errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response

    def __str__(self) -> str:
        if self.status_code:
            return f"AeonError {self.status_code}: {self.message}"
        return f"AeonError: {self.message}"


class AeonClient:
    """Python client for the AEON OS API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """
        Args:
            base_url: AEON backend URL. Defaults to the AEON_PYTHON_URL env var or http://localhost:5000.
            api_key: API key for authentication (used in X-API-Key header).
            token: JWT access token for authentication (used in Authorization header).
            timeout: Default request timeout in seconds.
        """
        self.base_url = (base_url or os.environ.get("AEON_PYTHON_URL", "http://localhost:5000")).rstrip("/")
        self.api_key = api_key or os.environ.get("AEON_API_KEY")
        self.token = token
        self.timeout = timeout
        self._session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _url(self, path: str) -> str:
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self._url(path)
        try:
            response = self._session.request(
                method,
                url,
                headers=self._headers(),
                timeout=kwargs.pop("timeout", self.timeout),
                **kwargs,
            )
        except requests.RequestException as exc:
            raise AeonError(f"request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = {"message": response.text}

        if not response.ok:
            message = data.get("error") if isinstance(data, dict) else str(data)
            raise AeonError(message or response.reason, status_code=response.status_code, response=data)

        return data

    def _get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs: Any) -> Any:
        return self._request("POST", path, **kwargs)

    def _delete(self, path: str, **kwargs: Any) -> Any:
        return self._request("DELETE", path, **kwargs)

    def _patch(self, path: str, **kwargs: Any) -> Any:
        return self._request("PATCH", path, **kwargs)

    # ── Health ───────────────────────────────────────────────────────────────
    def health(self) -> Dict[str, Any]:
        """Basic health check."""
        return self._get("/health")

    def live(self) -> Dict[str, Any]:
        """Liveness probe."""
        return self._get("/live")

    def ready(self) -> Dict[str, Any]:
        """Readiness probe."""
        return self._get("/ready")

    def detailed_health(self) -> Dict[str, Any]:
        """Detailed health snapshot."""
        return self._get("/health/detailed")

    # ── Auth ─────────────────────────────────────────────────────────────────
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Log in and store the returned token on this client."""
        data = self._post("/auth/login", json={"email": email, "password": password})
        if data.get("ok") and "token" in data:
            self.token = data["token"]
        return data

    def register(self, email: str, password: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Register a new user account."""
        payload = {"email": email, "password": password}
        if name:
            payload["name"] = name
        return self._post("/auth/register", json=payload)

    def me(self) -> Dict[str, Any]:
        """Get the current authenticated user's profile."""
        return self._get("/auth/me")

    # ── Workspaces & Chat ──────────────────────────────────────────────────
    def list_workspaces(self) -> Dict[str, Any]:
        """List workspaces for the authenticated user."""
        return self._get("/workspaces")

    def chat(self, query: str, workspace_id: Optional[str] = None, provider: Optional[str] = None) -> Dict[str, Any]:
        """Send a chat message. If workspace_id is provided, uses the workspace-scoped endpoint."""
        if workspace_id:
            return self._post(f"/workspaces/{workspace_id}/chat", json={"query": query, "provider": provider})
        return self._post("/chat", json={"query": query, "provider": provider})

    def workspace_history(self, workspace_id: str, limit: int = 50) -> Dict[str, Any]:
        """Get chat history for a workspace."""
        return self._get(f"/workspaces/{workspace_id}/history", params={"limit": limit})

    # ── Apps ──────────────────────────────────────────────────────────────────
    def app_tick(self, app_id: str, query: str, *, async_mode: bool = False) -> Dict[str, Any]:
        """Run one tick for a domain app."""
        return self._post(f"/apps/{app_id}/tick", json={"query": query, "async": async_mode})

    def app_chat(self, app_id: str, query: str) -> Dict[str, Any]:
        """Module-aware chat for a domain app."""
        return self._post(f"/apps/{app_id}/chat", json={"query": query})

    # ── Workflows ────────────────────────────────────────────────────────────
    def list_workflows(self) -> Dict[str, Any]:
        return self._get("/workflows")

    def create_workflow(self, *, name: str, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], **kwargs: Any) -> Dict[str, Any]:
        payload = {"name": name, "nodes": nodes, "edges": edges, **kwargs}
        return self._post("/workflows", json=payload)

    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        return self._get(f"/workflows/{workflow_id}")

    def delete_workflow(self, workflow_id: str) -> Dict[str, Any]:
        return self._delete(f"/workflows/{workflow_id}")

    def run_workflow(self, workflow_id: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._post(f"/workflows/{workflow_id}/run", json={"inputs": inputs or {}})

    # ── Swarm ────────────────────────────────────────────────────────────────
    def run_swarm(self, *, task: str, app_ids: List[str]) -> Dict[str, Any]:
        """Run an agent swarm."""
        return self._post("/swarm/run", json={"task": task, "app_ids": app_ids})

    # ── API Keys ─────────────────────────────────────────────────────────────
    def list_api_keys(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"workspace_id": workspace_id} if workspace_id else None
        return self._get("/api-keys", params=params)

    def create_api_key(self, name: str, *, workspace_id: Optional[str] = None, role: str = "operator") -> Dict[str, Any]:
        payload = {"name": name, "role": role}
        if workspace_id:
            payload["workspace_id"] = workspace_id
        return self._post("/api-keys", json=payload)

    def revoke_api_key(self, key_id: str) -> Dict[str, Any]:
        return self._delete(f"/api-keys/{key_id}")

    # ── Integrations ─────────────────────────────────────────────────────────
    def list_integrations(self) -> Dict[str, Any]:
        return self._get("/integrations")

    def create_integration(self, *, type: str, name: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._post("/integrations", json={"type": type, "name": name, "config": config or {}})

    def run_integration(self, integration_id: str, *, endpoint: str = "", method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._post(f"/integrations/{integration_id}/run", json={"endpoint": endpoint, "method": method, "payload": payload})

    # ── Billing & Usage ──────────────────────────────────────────────────────
    def get_billing_status(self, workspace_id: str) -> Dict[str, Any]:
        return self._get(f"/billing/{workspace_id}")

    def record_usage(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._post("/usage", json=events)

    # ── LLM ────────────────────────────────────────────────────────────────────
    def list_llm_providers(self) -> Dict[str, Any]:
        return self._get("/llm/providers")

    def switch_llm_provider(self, provider: str) -> Dict[str, Any]:
        return self._post("/llm/switch", json={"provider": provider})

    # ── RAG / Knowledge Bases ───────────────────────────────────────────────
    def list_knowledge_bases(self) -> Dict[str, Any]:
        return self._get("/knowledge-bases")

    def create_knowledge_base(self, *, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        payload = {"name": name}
        if description:
            payload["description"] = description
        return self._post("/knowledge-bases", json=payload)

    def query_knowledge_base(self, kb_id: str, query: str, *, top_k: int = 5) -> Dict[str, Any]:
        return self._post(f"/knowledge-bases/{kb_id}/query", json={"query": query, "top_k": top_k})
