/**
 * AEON Enterprise Connector Framework
 *
 * Connectors let AEON OS securely query external enterprise systems
 * (databases, APIs, document stores) and surface that data to the AI kernel.
 *
 * New connectors register themselves in the CONNECTORS map and are exposed
 * through `/api/connectors` and the settings UI.
 */

export type ConnectorType = "mock" | "http" | "postgres" | "snowflake" | "sharepoint";

export interface ConnectorConfig {
  name: string;
  type: ConnectorType;
  enabled: boolean;
  secrets: Record<string, string>;
  options?: Record<string, unknown>;
}

export interface ConnectorResult<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
  latency_ms?: number;
}

export interface ConnectorDefinition {
  id: string;
  name: string;
  type: ConnectorType;
  description: string;
  requiredSecrets: string[];
  optionalSecrets: string[];
  connect: (config: ConnectorConfig) => Promise<ConnectorResult>;
  query: (config: ConnectorConfig, sql: string) => Promise<ConnectorResult>;
}

// ── Mock connector (safe, no external deps) ──────────────────────────────────
const mockConnector: ConnectorDefinition = {
  id: "mock",
  name: "Mock Enterprise Data Store",
  type: "mock",
  description: "Simulated enterprise connector for demos and testing. No real credentials needed.",
  requiredSecrets: [],
  optionalSecrets: ["MOCK_API_KEY"],
  async connect(config) {
    const start = Date.now();
    if (!config.enabled) {
      return { ok: false, error: "connector disabled" };
    }
    return { ok: true, data: { status: "connected", rows: 0 }, latency_ms: Date.now() - start };
  },
  async query(config, sql) {
    const start = Date.now();
    if (!config.enabled) {
      return { ok: false, error: "connector disabled" };
    }
    // Simulate a tiny result set for any SELECT
    const rows = [
      { id: 1, value: "sample-row-1" },
      { id: 2, value: "sample-row-2" },
    ];
    return { ok: true, data: { sql, rows }, latency_ms: Date.now() - start };
  },
};

const httpConnector: ConnectorDefinition = {
  id: "http",
  name: "Generic HTTP/REST",
  type: "http",
  description: "Connect to any REST API with a bearer token.",
  requiredSecrets: ["HTTP_BASE_URL", "HTTP_TOKEN"],
  optionalSecrets: ["HTTP_HEADERS"],
  async connect(config) {
    const start = Date.now();
    const url = config.secrets.HTTP_BASE_URL;
    const token = config.secrets.HTTP_TOKEN;
    if (!url || !token) {
      return { ok: false, error: "missing HTTP_BASE_URL or HTTP_TOKEN" };
    }
    try {
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
        method: "HEAD",
      });
      return {
        ok: res.ok,
        data: { status: res.status },
        latency_ms: Date.now() - start,
      };
    } catch (err: any) {
      return { ok: false, error: err?.message || "connection failed" };
    }
  },
  async query(config, sql) {
    return {
      ok: false,
      error: "HTTP connector query not implemented; use the API directly.",
    };
  },
};

const postgresConnector: ConnectorDefinition = {
  id: "postgres",
  name: "PostgreSQL",
  type: "postgres",
  description: "Query a PostgreSQL database via a secure proxy.",
  requiredSecrets: ["POSTGRES_PROXY_URL"],
  optionalSecrets: ["POSTGRES_SSL_CA"],
  async connect(config) {
    const start = Date.now();
    const url = config.secrets.POSTGRES_PROXY_URL;
    if (!url) return { ok: false, error: "missing POSTGRES_PROXY_URL" };
    // In production this would reach a Python/Node proxy; here we just verify the URL is present.
    return { ok: true, data: { status: "configured" }, latency_ms: Date.now() - start };
  },
  async query(config, sql) {
    return {
      ok: false,
      error: "PostgreSQL connector requires the proxy service to be running.",
    };
  },
};

const snowflakeConnector: ConnectorDefinition = {
  id: "snowflake",
  name: "Snowflake",
  type: "snowflake",
  description: "Connect to Snowflake for enterprise analytics (placeholder).",
  requiredSecrets: ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PRIVATE_KEY"],
  optionalSecrets: [],
  async connect(config) {
    return { ok: false, error: "Snowflake connector not yet implemented" };
  },
  async query(config, sql) {
    return { ok: false, error: "Snowflake connector not yet implemented" };
  },
};

const sharepointConnector: ConnectorDefinition = {
  id: "sharepoint",
  name: "Microsoft SharePoint",
  type: "sharepoint",
  description: "Index SharePoint documents for RAG (placeholder).",
  requiredSecrets: ["SHAREPOINT_TENANT", "SHAREPOINT_CLIENT_ID", "SHAREPOINT_CLIENT_SECRET"],
  optionalSecrets: [],
  async connect(config) {
    return { ok: false, error: "SharePoint connector not yet implemented" };
  },
  async query(config, sql) {
    return { ok: false, error: "SharePoint connector not yet implemented" };
  },
};

export const CONNECTORS: Record<ConnectorType, ConnectorDefinition> = {
  mock: mockConnector,
  http: httpConnector,
  postgres: postgresConnector,
  snowflake: snowflakeConnector,
  sharepoint: sharepointConnector,
};

export async function testConnector(config: ConnectorConfig): Promise<ConnectorResult> {
  const def = CONNECTORS[config.type];
  if (!def) return { ok: false, error: "unknown connector type" };
  return def.connect(config);
}

export async function queryConnector(
  config: ConnectorConfig,
  sql: string
): Promise<ConnectorResult> {
  const def = CONNECTORS[config.type];
  if (!def) return { ok: false, error: "unknown connector type" };
  return def.query(config, sql);
}
