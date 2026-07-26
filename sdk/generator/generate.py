#!/usr/bin/env python3
"""
AEON OS — Multi-Language SDK Generator
========================================
Reads ``docs/openapi.json`` and generates idiomatic SDK clients for
Python, TypeScript, and Go.

Usage:
    python sdk/generator/generate.py
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OPENAPI_PATH = REPO_ROOT / "docs" / "openapi.json"
OUTPUTS = {
    "python": REPO_ROOT / "sdk" / "python" / "aeon_sdk.py",
    "typescript": REPO_ROOT / "sdk" / "typescript" / "src" / "index.ts",
    "go": REPO_ROOT / "sdk" / "go" / "aeon" / "aeon.go",
}

# ── Helpers ───────────────────────────────────────────────────────────────

def camel(s: str) -> str:
    """Convert snake_case to camelCase."""
    parts = s.lstrip("/").replace("{", "").replace("}", "").replace("-", "_").split("/")
    out = parts[0]
    for p in parts[1:]:
        out += p.capitalize() if p else ""
    return out


def pascal(s: str) -> str:
    """Convert snake_case to PascalCase."""
    c = camel(s)
    return c[0].upper() + c[1:] if c else c


def snake(s: str) -> str:
    """Convert any identifier to snake_case."""
    s = s.replace("-", "_").replace(".", "_")
    s = re.sub(r"([A-Z])", r"_\1", s).lower()
    return s.strip("_")


def safe_py_name(s: str) -> str:
    """Make a valid Python identifier."""
    n = snake(s)
    if n in ("from", "import", "class", "def", "type", "global", "lambda"):
        n += "_"
    return n


def safe_ts_name(s: str) -> str:
    """Make a valid TS identifier."""
    n = camel(s)
    if n in ("import", "export", "class", "new", "delete", "void", "typeof"):
        n += "_"
    return n


def safe_go_name(s: str) -> str:
    """Make a valid Go identifier."""
    n = pascal(s)
    if n == "":
        n = "Unknown"
    return n


def parse_path(path: str) -> list[str]:
    """Extract path parameters from a Swagger/OpenAPI path."""
    return re.findall(r"\{(.+?)\}", path)


def path_to_fn_suffix(path: str, method: str) -> str:
    """Generate a unique function suffix from path + method."""
    cleaned = path.replace("{", "").replace("}", "").strip("/")
    if cleaned == "":
        return "Root"
    parts = cleaned.split("/")
    return "".join(p.capitalize() for p in parts)


# ── Load OpenAPI Spec ────────────────────────────────────────────────────

def load_spec() -> dict[str, Any]:
    with open(OPENAPI_PATH) as f:
        return json.load(f)


# ── Python Generator ──────────────────────────────────────────────────────

PY_HEADER = '''"""
AEON OS — Python SDK (auto-generated from OpenAPI spec)
=========================================================
Install:
    cd sdk/python && pip install -e .

Usage:
    from aeon_sdk import AeonClient

    client = AeonClient("https://your-backend.com", api_key="aeon_...")
    print(client.health())
    print(client.chat("Hello!"))
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import requests


class AeonError(Exception):
    """Base exception for AEON SDK errors."""

    def __init__(self, message: str, status_code: int | None = None, response: Any | None = None):
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
        base_url: str | None = None,
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or os.environ.get("AEON_PYTHON_URL", "http://localhost:5000")).rstrip("/")
        self.api_key = api_key or os.environ.get("AEON_API_KEY")
        self.token = token
        self.timeout = timeout
        self._session = requests.Session()

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
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
            response = self._session.request(method, url, headers=self._headers(), timeout=kwargs.pop("timeout", self.timeout), **kwargs)
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

    def _patch(self, path: str, **kwargs: Any) -> Any:
        return self._request("PATCH", path, **kwargs)

    def _delete(self, path: str, **kwargs: Any) -> Any:
        return self._request("DELETE", path, **kwargs)

'''

PY_TAIL = """
# ── Additional methods beyond OpenAPI spec ────────────────────────────────

    def app_chat(self, app_id: str, query: str) -> dict[str, Any]:
        \"\"\"Module-aware chat for a domain app.\"\"\"
        return self._post(f"/apps/{app_id}/chat", json={"query": query})

    def run_integration(
        self, integration_id: str, *, endpoint: str = "", method: str = "GET", payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        \"\"\"Run an integration action.\"\"\"
        return self._post(
            f"/integrations/{integration_id}/run",
            json={"endpoint": endpoint, "method": method, "payload": payload},
        )

    def get_integration_catalog(self) -> dict[str, Any]:
        \"\"\"Get the integration catalog.\"\"\"
        return self._get("/integrations/catalog")

    def record_usage(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        \"\"\"Record usage events.\"\"\"
        return self._post("/usage", json=events)

    def switch_llm_provider(self, provider: str) -> dict[str, Any]:
        \"\"\"Switch the active LLM provider.\"\"\"
        return self._post("/llm/switch", json={"provider": provider})

    def test_llm_provider(self, provider: str) -> dict[str, Any]:
        \"\"\"Test an LLM provider connection.\"\"\"
        return self._post("/llm/test", json={"provider": provider})

    def run_swarm(self, *, app_ids: list[str], prompt: str, roles: dict[str, str] | None = None) -> dict[str, Any]:
        \"\"\"Run an agent swarm.\"\"\"
        return self._post("/swarm/run", json={"app_ids": app_ids, "prompt": prompt, "roles": roles or {}})

    def swarm_status(self, swarm_id: str) -> dict[str, Any]:
        \"\"\"Get swarm execution status.\"\"\"
        return self._get(f"/swarm/{swarm_id}")

    def swarm_messages(self, swarm_id: str) -> dict[str, Any]:
        \"\"\"Get swarm messages.\"\"\"
        return self._get(f"/swarm/{swarm_id}/messages")

    def create_knowledge_base(self, *, name: str, description: str | None = None) -> dict[str, Any]:
        \"\"\"Create a knowledge base.\"\"\"
        return self._post("/knowledge-bases", json={"name": name, "description": description})

    def list_knowledge_bases(self) -> dict[str, Any]:
        \"\"\"List knowledge bases.\"\"\"
        return self._get("/knowledge-bases")

    def query_knowledge_base(self, kb_id: str, query: str, *, top_k: int = 5) -> dict[str, Any]:
        \"\"\"Query a knowledge base.\"\"\"
        return self._post(f"/knowledge-bases/{kb_id}/query", json={"query": query, "top_k": top_k})

    def list_governance_audit(self) -> dict[str, Any]:
        \"\"\"List governance audit logs.\"\"\"
        return self._get("/governance/audit")

    def list_governance_compliance(self) -> dict[str, Any]:
        \"\"\"List compliance reports.\"\"\"
        return self._get("/governance/compliance")

    def get_governance_retention(self) -> dict[str, Any]:
        \"\"\"Get data retention policy.\"\"\"
        return self._get("/governance/retention")
"""


def generate_python(spec: dict[str, Any]) -> str:
    lines = [PY_HEADER]

    paths = spec.get("paths", {})
    # Collect unique path->method pairs
    entries: list[tuple[str, str, dict[str, Any]]] = []
    for path, methods in sorted(paths.items()):
        for method in ("get", "post", "patch", "delete"):
            if method in methods:
                entries.append((path, method, methods[method]))

    for path, method, op in entries:
        op_id = op.get("operationId", f"{method}_{camel(path)}")
        summary = op.get("summary", op_id)
        fn_name = safe_py_name(op_id)
        params = []
        call_params = []

        # Path parameters
        for p in op.get("parameters", []):
            p_name = safe_py_name(p["name"])
            if p["in"] == "path":
                params.append(f"{p_name}: str")
                call_params.append(p_name)
            elif p["in"] == "query":
                ptype = {"integer": "int", "boolean": "bool"}.get(p.get("schema", {}).get("type", "string"), "str")
                default = p.get("schema", {}).get("default")
                if default is not None:
                    params.append(f"{p_name}: {ptype} = {default}")
                else:
                    params.append(f"{p_name}: {ptype} | None = None")

        # Request body
        req_body = op.get("requestBody", {})
        body_props = None
        if "content" in req_body:
            schema_ref = req_body["content"].get("application/json", {}).get("schema", {})
            if "$ref" in schema_ref:
                ref_name = schema_ref["$ref"].split("/")[-1]
                body_props = spec.get("components", {}).get("schemas", {}).get(ref_name, {}).get("properties", {})

        # Build HTTP calls
        if method == "get":
            http = f'self._get("{path}"'
        elif method == "post":
            http = f'self._post("{path}"'
        elif method == "patch":
            http = f'self._patch("{path}"'
        else:
            http = f'self._delete("{path}"'

        # Format path with parameters
        formatted_path = path
        path_params = parse_path(path)
        for pp in path_params:
            formatted_path = formatted_path.replace(f"{{{pp}}}", f"{{{safe_py_name(pp)}}}")

        http = f'self._{method}("{formatted_path}"'

        # URL params (query)
        query_params = [p for p in op.get("parameters", []) if p["in"] == "query"]
        if query_params:
            query_dict = ", ".join(f'"{p["name"]}": {safe_py_name(p["name"])}' for p in query_params)
            http += f", params={{{query_dict}}}"

        # Body
        if body_props:
            body_keys = []
            for k in body_props:
                body_keys.append(f'"{k}": {safe_py_name(k)}')
            if body_keys:
                http += f", json={{{', '.join(body_keys)}}}"
        elif method == "post" and not path_params:
            # For post endpoints without body schema, pass generic json
            pass

        http += ")"

        # Generate method
        header = f'\n    def {fn_name}(self'
        if params:
            header += f", {', '.join(params)}"
        if ", *, " in header or "*," in header:
            pass  # already has keyword-only
        header += ") -> dict[str, Any]:"

        doc = f'        """{summary}."""'
        lines.append(header)
        lines.append(doc)
        lines.append(f"        return {http}")
        lines.append("")

    lines.append(PY_TAIL)

    return "".join(lines)


# ── TypeScript Generator ─────────────────────────────────────────────────

TS_HEADER = '''/**
 * AEON OS — TypeScript SDK (auto-generated from OpenAPI spec)
 * ==============================================================
 *
 * Install:
 *   npm install @aeon/sdk
 *
 * Usage:
 *   import { AeonClient } from "@aeon/sdk";
 *
 *   const client = new AeonClient({ baseUrl: "https://...", apiKey: "aeon_..." });
 *   const health = await client.health();
 */

export interface AeonClientOptions {
  baseUrl?: string;
  apiKey?: string;
  token?: string;
  timeout?: number;
}

export interface AeonRequestInit {
  method?: string;
  path: string;
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  timeout?: number;
}

export class AeonError extends Error {
  public statusCode?: number;
  public response?: unknown;
  constructor(message: string, statusCode?: number, response?: unknown) {
    super(message);
    this.name = "AeonError";
    this.statusCode = statusCode;
    this.response = response;
  }
}

function getEnvBaseUrl(): string {
  if (typeof process !== "undefined" && process.env?.AEON_PYTHON_URL) {
    return process.env.AEON_PYTHON_URL;
  }
  return "http://localhost:5000";
}

function buildUrl(baseUrl: string, path: string, query?: AeonRequestInit["query"]): string {
  const url = new URL(path, baseUrl);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

export class AeonClient {
  public readonly baseUrl: string;
  public apiKey?: string;
  public token?: string;
  public readonly timeout: number;

  constructor(options: AeonClientOptions = {}) {
    this.baseUrl = (options.baseUrl || getEnvBaseUrl()).replace(/\\/$/, "");
    this.apiKey = options.apiKey;
    this.token = options.token;
    this.timeout = options.timeout ?? 120_000;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { Accept: "application/json", "Content-Type": "application/json" };
    if (this.apiKey) h["X-API-Key"] = this.apiKey;
    if (this.token) h.Authorization = `Bearer ${this.token}`;
    return h;
  }

  public async request<T = unknown>(init: AeonRequestInit): Promise<T> {
    const url = buildUrl(this.baseUrl, init.path, init.query);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), init.timeout ?? this.timeout);
    let response: Response;
    try {
      response = await fetch(url, {
        method: init.method || "GET",
        headers: this.headers(),
        body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
        signal: controller.signal,
      });
    } catch (error) {
      clearTimeout(timer);
      throw new AeonError("request failed: " + (error instanceof Error ? error.message : String(error)));
    } finally {
      clearTimeout(timer);
    }
    const text = await response.text();
    let data: unknown;
    try { data = text ? JSON.parse(text) : null; } catch { data = { message: text }; }
    if (!response.ok) {
      const message = typeof data === "object" && data !== null && (data as Record<string, unknown>).error
        ? String((data as Record<string, unknown>).error) : response.statusText;
      throw new AeonError(message, response.status, data);
    }
    return data as T;
  }

'''


def generate_typescript(spec: dict[str, Any]) -> str:
    lines = [TS_HEADER]

    paths = spec.get("paths", {})
    for path, methods in sorted(paths.items()):
        for method in ("get", "post", "patch", "delete"):
            op = methods.get(method)
            if not op:
                continue
            op_id = op.get("operationId", f"{method}{pascal(path)}")
            summary = op.get("summary", op_id)
            fn_name = safe_ts_name(op_id)

            # Parameters
            ts_params: list[str] = []
            ts_call_body: dict[str, str] = {}
            path_params = parse_path(path)
            has_query = False

            for p in op.get("parameters", []):
                p_name = p["name"]
                if p["in"] == "path":
                    ts_params.append(f"{safe_ts_name(p_name)}: string")
                elif p["in"] == "query":
                    ts_params.append(f"{camel(p_name)}?: {p.get('schema', {}).get('type', 'string')}")
                    has_query = True

            # Request body
            req_body = op.get("requestBody", {})
            body_props: dict[str, Any] = {}
            if "content" in req_body:
                schema_ref = req_body["content"].get("application/json", {}).get("schema", {})
                if "$ref" in schema_ref:
                    ref_name = schema_ref["$ref"].split("/")[-1]
                    body_props = spec.get("components", {}).get("schemas", {}).get(ref_name, {}).get("properties", {})

            # Build request init
            path_str = path
            for pp in path_params:
                path_str = path_str.replace(f"{{{pp}}}", f"${{encodeURIComponent({safe_ts_name(pp)})}}")

            init_lines = ["{"]
            if method != "get":
                init_lines.append(f'    method: "{method.upper()}",')
            init_lines.append(f"    path: `{path_str}`,")
            if has_query:
                q_entries = []
                for p in op.get("parameters", []):
                    if p["in"] == "query":
                        en = camel(p["name"])
                        q_entries.append(f"{p['name']}: {en}")
                init_lines.append(f"    query: {{ {', '.join(q_entries)} }},")
            if body_props:
                body_kvs = []
                for k in body_props:
                    n = safe_ts_name(k)
                    ts_params.append(f"{n}: unknown")
                    body_kvs.append(f"{k}: {n}")
                init_lines.append(f"    body: {{ {', '.join(body_kvs)} }},")
            init_lines.append("  }")

            doc = f"  /** {summary}. */"
            fn_sig = f"  public {fn_name}("
            if ts_params:
                fn_sig += ", ".join(ts_params)
            fn_sig += "): Promise<Record<string, unknown>> {"
            lines.append(doc)
            lines.append(fn_sig)
            lines.append(f"    return this.request({''.join(init_lines)});")
            lines.append("  }")
            lines.append("")

    lines.append("""  // ── Additional methods ──────────────────────────────────────────────

  public appChat(appId: string, query: string): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: `/apps/${encodeURIComponent(appId)}/chat`, body: { query } });
  }

  public runIntegration(
    integrationId: string, endpoint = "", method = "GET", payload?: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    return this.request({
      method: "POST", path: `/integrations/${encodeURIComponent(integrationId)}/run`,
      body: { endpoint, method, payload },
    });
  }

  public getIntegrationCatalog(): Promise<Record<string, unknown>> {
    return this.request({ path: "/integrations/catalog" });
  }

  public recordUsage(events: unknown[]): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: "/usage", body: events });
  }

  public switchLlmProvider(provider: string): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: "/llm/switch", body: { provider } });
  }

  public testLlmProvider(provider: string): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: "/llm/test", body: { provider } });
  }

  public runSwarm(appIds: string[], prompt: string, roles?: Record<string, string>): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: "/swarm/run", body: { app_ids: appIds, prompt, roles } });
  }

  public swarmStatus(swarmId: string): Promise<Record<string, unknown>> {
    return this.request({ path: `/swarm/${encodeURIComponent(swarmId)}` });
  }

  public swarmMessages(swarmId: string): Promise<Record<string, unknown>> {
    return this.request({ path: `/swarm/${encodeURIComponent(swarmId)}/messages` });
  }

  public createKnowledgeBase(name: string, description?: string): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: "/knowledge-bases", body: { name, description } });
  }

  public queryKnowledgeBase(kbId: string, query: string, topK = 5): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: `/knowledge-bases/${encodeURIComponent(kbId)}/query`, body: { query, top_k: topK } });
  }

  public listGovernanceAudit(): Promise<Record<string, unknown>> {
    return this.request({ path: "/governance/audit" });
  }

  public listGovernanceCompliance(): Promise<Record<string, unknown>> {
    return this.request({ path: "/governance/compliance" });
  }

  public getGovernanceRetention(): Promise<Record<string, unknown>> {
    return this.request({ path: "/governance/retention" });
  }
""")

    lines.append("}\n\nexport default AeonClient;\n")
    return "".join(lines)


# ── Go Generator ──────────────────────────────────────────────────────────

GO_HEADER = '''// Package aeon provides a Go client for the AEON OS API.
//
// Auto-generated from docs/openapi.json.
//
// Usage:
//
//    client := aeon.NewClient("https://your-backend.com", aeon.WithAPIKey("aeon_..."))
//    health, err := client.Health()
//    reply, err := client.Chat("Hello!")
//
package aeon

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"time"
)

// Error represents an AEON API error.
type Error struct {
	Message    string
	StatusCode int
	Response   interface{}
}

func (e *Error) Error() string {
	if e.StatusCode > 0 {
		return fmt.Sprintf("AeonError %d: %s", e.StatusCode, e.Message)
	}
	return fmt.Sprintf("AeonError: %s", e.Message)
}

// ClientOption configures an AeonClient.
type ClientOption func(*Client)

// WithAPIKey sets the API key for authentication.
func WithAPIKey(key string) ClientOption {
	return func(c *Client) { c.apiKey = key }
}

// WithToken sets the JWT token for authentication.
func WithToken(token string) ClientOption {
	return func(c *Client) { c.token = token }
}

// WithTimeout sets the default request timeout.
func WithTimeout(timeout time.Duration) ClientOption {
	return func(c *Client) { c.timeout = timeout }
}

// Client is the AEON OS API client.
type Client struct {
	baseURL string
	apiKey  string
	token   string
	timeout time.Duration
	http    *http.Client
}

// NewClient creates a new AEON API client.
func NewClient(baseURL string, opts ...ClientOption) *Client {
	if baseURL == "" {
		baseURL = os.Getenv("AEON_PYTHON_URL")
		if baseURL == "" {
			baseURL = "http://localhost:5000"
		}
	}
	c := &Client{
		baseURL: baseURL,
		timeout: 120 * time.Second,
		http:    &http.Client{Timeout: 120 * time.Second},
	}
	for _, opt := range opts {
		opt(c)
	}
	return c
}

func (c *Client) request(method, path string, query map[string]string, body interface{}) (map[string]interface{}, error) {
	u, err := url.Parse(c.baseURL + path)
	if err != nil {
		return nil, fmt.Errorf("aeon: invalid url: %w", err)
	}
	for k, v := range query {
		q := u.Query()
		q.Set(k, v)
		u.RawQuery = q.Encode()
	}
	var reqBody io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("aeon: marshal body: %w", err)
		}
		reqBody = bytes.NewReader(b)
	}
	req, err := http.NewRequest(method, u.String(), reqBody)
	if err != nil {
		return nil, fmt.Errorf("aeon: create request: %w", err)
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("X-API-Key", c.apiKey)
	}
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("aeon: request failed: %w", err)
	}
	defer resp.Body.Close()
	var data map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, fmt.Errorf("aeon: decode response: %w", err)
	}
	if resp.StatusCode >= 400 {
		errMsg, _ := data["error"].(string)
		if errMsg == "" {
			errMsg = resp.Status
		}
		return nil, &Error{Message: errMsg, StatusCode: resp.StatusCode, Response: data}
	}
	return data, nil
}

func (c *Client) get(path string, query map[string]string) (map[string]interface{}, error) {
	return c.request(http.MethodGet, path, query, nil)
}

func (c *Client) post(path string, body interface{}) (map[string]interface{}, error) {
	return c.request(http.MethodPost, path, nil, body)
}

func (c *Client) patch(path string, body interface{}) (map[string]interface{}, error) {
	return c.request(http.MethodPatch, path, nil, body)
}

func (c *Client) delete(path string) (map[string]interface{}, error) {
	return c.request(http.MethodDelete, path, nil, nil)
}

'''


def generate_go(spec: dict[str, Any]) -> str:
    lines = [GO_HEADER]

    paths = spec.get("paths", {})
    for path, methods in sorted(paths.items()):
        for method in ("get", "post", "patch", "delete"):
            op = methods.get(method)
            if not op:
                continue
            op_id = op.get("operationId", f"{method}{pascal(path)}")
            summary = op.get("summary", op_id)
            fn_name = safe_go_name(op_id)

            path_params = parse_path(path)
            go_params: list[str] = []
            go_query_params: list[str] = []
            go_body_fields: list[str] = []

            for p in op.get("parameters", []):
                p_name = p["name"]
                if p["in"] == "path":
                    go_params.append(f"{safe_go_name(p_name)} string")
                elif p["in"] == "query":
                    go_params.append(f"{camel(p_name)}...string")
                    go_query_params.append(camel(p_name))

            req_body = op.get("requestBody", {})
            body_props: dict[str, Any] = {}
            if "content" in req_body:
                schema_ref = req_body["content"].get("application/json", {}).get("schema", {})
                if "$ref" in schema_ref:
                    ref_name = schema_ref["$ref"].split("/")[-1]
                    body_props = spec.get("components", {}).get("schemas", {}).get(ref_name, {}).get("properties", {})

            # Build method
            doc_str = f"// {fn_name} {summary}."
            func_sig = f"func (c *Client) {fn_name}("
            if go_params:
                func_sig += ", ".join(go_params)
            if go_params and body_props:
                func_sig += ", "
            if body_props:
                body_fields_go = []
                for k in body_props:
                    go_params.append(f"{camel(k)} interface{{}}")
                    body_fields_go.append(f'"{k}": {camel(k)}')
                func_sig += ", ".join([f"{camel(k)} interface{{}}" for k in body_props])
            func_sig += ") (map[string]interface{}, error) {"

            lines.append("")
            lines.append(doc_str)
            lines.append(func_sig)
            if method == "get":
                if go_query_params:
                    q_entries = "\n".join(f'        "{qp}": {camel(qp)}[0],' for qp in go_query_params)
                    lines.append(f'    q := map[string]string{{\n{q_entries}\n    }}')
                    lines.append(f'    return c.get("{path}", q)')
                else:
                    lines.append(f'    return c.get("{path}", nil)')
            else:
                if body_props:
                    body_map_str = "map[string]interface{}{" + ", ".join(body_fields_go) + "}"
                    lines.append(f'    return c.{method}("{path}", {body_map_str})')
                else:
                    lines.append(f'    return c.{method}("{path}", nil)')
            lines.append("}")

    # Add extra methods
    lines.append("""

// ── Additional methods beyond OpenAPI spec ──────────────────────────────

func (c *Client) AppChat(appID, query string) (map[string]interface{}, error) {
    return c.post("/apps/" + appID + "/chat", map[string]interface{}{"query": query})
}

func (c *Client) RunIntegration(integrationID, endpoint, method string, payload interface{}) (map[string]interface{}, error) {
    return c.post("/integrations/" + integrationID + "/run", map[string]interface{}{
        "endpoint": endpoint, "method": method, "payload": payload,
    })
}

func (c *Client) GetIntegrationCatalog() (map[string]interface{}, error) {
    return c.get("/integrations/catalog", nil)
}

func (c *Client) RecordUsage(events []interface{}) (map[string]interface{}, error) {
    return c.post("/usage", events)
}

func (c *Client) SwitchLlmProvider(provider string) (map[string]interface{}, error) {
    return c.post("/llm/switch", map[string]interface{}{"provider": provider})
}

func (c *Client) TestLlmProvider(provider string) (map[string]interface{}, error) {
    return c.post("/llm/test", map[string]interface{}{"provider": provider})
}

func (c *Client) RunSwarm(appIDs []string, prompt string, roles map[string]string) (map[string]interface{}, error) {
    return c.post("/swarm/run", map[string]interface{}{"app_ids": appIDs, "prompt": prompt, "roles": roles})
}

func (c *Client) SwarmStatus(swarmID string) (map[string]interface{}, error) {
    return c.get("/swarm/"+swarmID, nil)
}

func (c *Client) SwarmMessages(swarmID string) (map[string]interface{}, error) {
    return c.get("/swarm/"+swarmID+"/messages", nil)
}

func (c *Client) CreateKnowledgeBase(name, description string) (map[string]interface{}, error) {
    return c.post("/knowledge-bases", map[string]interface{}{"name": name, "description": description})
}

func (c *Client) ListKnowledgeBases() (map[string]interface{}, error) {
    return c.get("/knowledge-bases", nil)
}

func (c *Client) QueryKnowledgeBase(kbID, query string, topK int) (map[string]interface{}, error) {
    return c.post("/knowledge-bases/"+kbID+"/query", map[string]interface{}{"query": query, "top_k": topK})
}

func (c *Client) ListGovernanceAudit() (map[string]interface{}, error) {
    return c.get("/governance/audit", nil)
}

func (c *Client) ListGovernanceCompliance() (map[string]interface{}, error) {
    return c.get("/governance/compliance", nil)
}

func (c *Client) GetGovernanceRetention() (map[string]interface{}, error) {
    return c.get("/governance/retention", nil)
}
""")

    return "".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    spec = load_spec()
    os.makedirs(OUTPUTS["python"].parent, exist_ok=True)
    os.makedirs(OUTPUTS["typescript"].parent, exist_ok=True)
    os.makedirs(OUTPUTS["go"].parent, exist_ok=True)

    # Python
    py_code = generate_python(spec)
    OUTPUTS["python"].write_text(py_code)
    print(f"✓ Generated Python SDK: {OUTPUTS['python']}")

    # TypeScript
    ts_code = generate_typescript(spec)
    OUTPUTS["typescript"].write_text(ts_code)
    print(f"✓ Generated TypeScript SDK: {OUTPUTS['typescript']}")

    # Go
    go_code = generate_go(spec)
    OUTPUTS["go"].write_text(go_code)
    print(f"✓ Generated Go SDK: {OUTPUTS['go']}")

    print("\nDone! Run validation:\n")
    print("  ruff check sdk/python/aeon_sdk.py")
    print("  cd sdk/typescript && npx tsc --noEmit")
    print("  cd sdk/go && go build ./...")


if __name__ == "__main__":
    main()
