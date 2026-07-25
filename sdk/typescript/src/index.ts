/**
 * AEON OS — TypeScript SDK
 * ==========================
 * A lightweight, dependency-free client for the AEON OS Flask backend.
 *
 * Install locally:
 *   npm install @aeon/sdk
 *
 * Basic usage:
 *   import { AeonClient } from "@aeon/sdk";
 *
 *   const client = new AeonClient({
 *     baseUrl: "https://your-aeon-backend.up.railway.app",
 *     apiKey: "aeon_...",
 *   });
 *   const health = await client.health();
 *   const reply = await client.chat("What is the integral of x^2?");
 */

export interface AeonClientOptions {
  /** AEON backend base URL. Defaults to AEON_PYTHON_URL env var or http://localhost:5000 */
  baseUrl?: string;
  /** API key sent in the X-API-Key header. */
  apiKey?: string;
  /** JWT access token sent in the Authorization header. */
  token?: string;
  /** Default request timeout in milliseconds. */
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

  public toString(): string {
    if (this.statusCode) {
      return `AeonError ${this.statusCode}: ${this.message}`;
    }
    return `AeonError: ${this.message}`;
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
    this.baseUrl = (options.baseUrl || getEnvBaseUrl()).replace(/\/$/, "");
    this.apiKey = options.apiKey;
    this.token = options.token;
    this.timeout = options.timeout ?? 120_000;
  }

  private headers(): Record<string, string> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      "Content-Type": "application/json",
    };
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }
    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }
    return headers;
  }

  public async request<T = unknown>(init: AeonRequestInit): Promise<T> {
    const url = buildUrl(this.baseUrl, init.path, init.query);
    const controller = new AbortController();
    const timeout = init.timeout ?? this.timeout;
    const timer = setTimeout(() => controller.abort(), timeout);

    let response: Response;
    try {
      response = await fetch(url, {
        method: init.method || "GET",
        headers: this.headers(),
        body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
        signal: controller.signal as AbortSignal,
      });
    } catch (error) {
      clearTimeout(timer);
      throw new AeonError(`request failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      clearTimeout(timer);
    }

    let data: unknown;
    const text = await response.text();
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { message: text };
    }

    if (!response.ok) {
      const message =
        typeof data === "object" && data !== null && (data as Record<string, unknown>).error
          ? String((data as Record<string, unknown>).error)
          : response.statusText;
      throw new AeonError(message, response.status, data);
    }

    return data as T;
  }

  // ── Health ───────────────────────────────────────────────────────────────
  public health(): Promise<Record<string, unknown>> {
    return this.request({ path: "/health" });
  }

  public live(): Promise<Record<string, unknown>> {
    return this.request({ path: "/live" });
  }

  public ready(): Promise<Record<string, unknown>> {
    return this.request({ path: "/ready" });
  }

  public detailedHealth(): Promise<Record<string, unknown>> {
    return this.request({ path: "/health/detailed" });
  }

  // ── Auth ─────────────────────────────────────────────────────────────────
  public async login(email: string, password: string): Promise<Record<string, unknown>> {
    const data = await this.request<Record<string, unknown>>({
      method: "POST",
      path: "/auth/login",
      body: { email, password },
    });
    if (data.token && typeof data.token === "string") {
      this.token = data.token;
    }
    return data;
  }

  public register(email: string, password: string, name?: string): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: "/auth/register", body: { email, password, name } });
  }

  public me(): Promise<Record<string, unknown>> {
    return this.request({ path: "/auth/me" });
  }

  // ── Workspaces & Chat ──────────────────────────────────────────────────
  public listWorkspaces(): Promise<Record<string, unknown>> {
    return this.request({ path: "/workspaces" });
  }

  public chat(
    query: string,
    workspaceId?: string,
    provider?: string
  ): Promise<Record<string, unknown>> {
    if (workspaceId) {
      return this.request({
        method: "POST",
        path: `/workspaces/${encodeURIComponent(workspaceId)}/chat`,
        body: { query, provider },
      });
    }
    return this.request({ method: "POST", path: "/chat", body: { query, provider } });
  }

  public workspaceHistory(workspaceId: string, limit = 50): Promise<Record<string, unknown>> {
    return this.request({
      path: `/workspaces/${encodeURIComponent(workspaceId)}/history`,
      query: { limit },
    });
  }

  // ── Apps ──────────────────────────────────────────────────────────────────
  public appChat(appId: string, query: string, system?: string): Promise<Record<string, unknown>> {
    return this.request({
      method: "POST",
      path: `/apps/${encodeURIComponent(appId)}/chat`,
      body: { query, system },
    });
  }

  public appTick(appId: string, query: string, asyncMode = false): Promise<Record<string, unknown>> {
    return this.request({
      method: "POST",
      path: `/apps/${encodeURIComponent(appId)}/tick`,
      body: { query, async: asyncMode },
    });
  }

  // ── Workflows ────────────────────────────────────────────────────────────
  public listWorkflows(): Promise<Record<string, unknown>> {
    return this.request({ path: "/workflows" });
  }

  public createWorkflow(workflow: {
    name: string;
    nodes: unknown[];
    edges: unknown[];
    [key: string]: unknown;
  }): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: "/workflows", body: workflow });
  }

  public getWorkflow(workflowId: string): Promise<Record<string, unknown>> {
    return this.request({ path: `/workflows/${encodeURIComponent(workflowId)}` });
  }

  public deleteWorkflow(workflowId: string): Promise<Record<string, unknown>> {
    return this.request({ method: "DELETE", path: `/workflows/${encodeURIComponent(workflowId)}` });
  }

  public runWorkflow(workflowId: string, inputs?: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request({
      method: "POST",
      path: `/workflows/${encodeURIComponent(workflowId)}/run`,
      body: { initial_input: "", ...inputs },
    });
  }

  // ── Swarm ────────────────────────────────────────────────────────────────
  public runSwarm(appIds: string[], prompt: string): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: "/swarm/run", body: { app_ids: appIds, prompt } });
  }

  // ── API Keys ─────────────────────────────────────────────────────────────
  public listApiKeys(workspaceId?: string): Promise<Record<string, unknown>> {
    return this.request({ path: "/api-keys", query: workspaceId ? { workspace_id: workspaceId } : undefined });
  }

  public createApiKey(name: string, workspaceId?: string, role = "operator"): Promise<Record<string, unknown>> {
    return this.request({
      method: "POST",
      path: "/api-keys",
      body: { name, workspace_id: workspaceId, role },
    });
  }

  public revokeApiKey(keyId: string): Promise<Record<string, unknown>> {
    return this.request({ method: "DELETE", path: `/api-keys/${encodeURIComponent(keyId)}` });
  }

  // ── Integrations ─────────────────────────────────────────────────────────
  public listIntegrations(): Promise<Record<string, unknown>> {
    return this.request({ path: "/integrations" });
  }

  public createIntegration(
    type: string,
    name: string,
    config?: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    return this.request({
      method: "POST",
      path: "/integrations",
      body: { type, name, config: config ?? {} },
    });
  }

  public runIntegration(
    integrationId: string,
    endpoint = "",
    method = "GET",
    payload?: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    return this.request({
      method: "POST",
      path: `/integrations/${encodeURIComponent(integrationId)}/run`,
      body: { endpoint, method, payload },
    });
  }

  public getIntegrationCatalog(): Promise<Record<string, unknown>> {
    return this.request({ path: "/integrations/catalog" });
  }

  // ── Billing & Usage ──────────────────────────────────────────────────────
  public getBillingStatus(workspaceId: string): Promise<Record<string, unknown>> {
    return this.request({ path: `/billing/${encodeURIComponent(workspaceId)}` });
  }

  public recordUsage(events: unknown[]): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: "/usage", body: events });
  }

  // ── LLM ────────────────────────────────────────────────────────────────────
  public listLlmProviders(): Promise<Record<string, unknown>> {
    return this.request({ path: "/llm/providers" });
  }

  public switchLlmProvider(provider: string): Promise<Record<string, unknown>> {
    return this.request({ method: "POST", path: "/llm/switch", body: { provider } });
  }

  // ── RAG / Knowledge Bases ───────────────────────────────────────────────
  public listKnowledgeBases(): Promise<Record<string, unknown>> {
    return this.request({ path: "/knowledge-bases" });
  }

  public createKnowledgeBase(name: string, description?: string): Promise<Record<string, unknown>> {
    return this.request({
      method: "POST",
      path: "/knowledge-bases",
      body: { name, description },
    });
  }

  public queryKnowledgeBase(kbId: string, query: string, topK = 5): Promise<Record<string, unknown>> {
    return this.request({
      method: "POST",
      path: `/knowledge-bases/${encodeURIComponent(kbId)}/query`,
      body: { query, top_k: topK },
    });
  }
}

export default AeonClient;
