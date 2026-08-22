/**
 * AEON OS — Demo data fallback layer.
 *
 * When the Flask backend is unreachable (e.g. a frontend-only preview or a
 * fresh Vercel deployment before Railway is configured), these handlers
 * return realistic demo data so every OS module renders a working, populated
 * dashboard instead of empty/error states.
 */

function iso(daysAgo = 0, hoursAgo = 0): string {
  const d = new Date(Date.now() - daysAgo * 86400000 - hoursAgo * 3600000);
  return d.toISOString();
}

export const demoCounts = {
  anomalies: 7,
  incidents: 3,
  open_incidents: 2,
  automations: 14,
  backup_policies: 4,
  dr_plans: 2,
  siem_integrations: 5,
  automation_executions_30d: 1284,
};

export const demoDashboard = {
  ok: true,
  demo: true,
  counts: demoCounts,
  stats: {
    uptime: "99.97%",
    agents: 12,
    tasks: 14832,
    requests_24h: 4821,
    error_rate_24h: "0.42%",
    p95_latency_ms: 812,
    active_workspaces: 1,
    llm_spend_30d: 128.45,
    llm_tokens_30d: 1842000,
  },
  recent_events: [
    { id: "evt-1", type: "automation.completed", title: "Nightly SIEM log aggregation completed", ts: iso(0, 2), status: "success" },
    { id: "evt-2", type: "incident.created", title: "High CPU on production agent worker", ts: iso(0, 5), status: "warning" },
    { id: "evt-3", type: "backup.completed", title: "PostgreSQL backup verified (2.4 GB)", ts: iso(0, 8), status: "success" },
    { id: "evt-4", type: "swarm.completed", title: "Risk assessment swarm finished in 4m 12s", ts: iso(1, 0), status: "success" },
    { id: "evt-5", type: "security.alert", title: "3 new login attempts from unknown region blocked", ts: iso(1, 3), status: "info" },
  ],
};

export const demoAutomations = {
  ok: true,
  demo: true,
  rules: [
    {
      id: "rule-1",
      name: "Escalate critical incidents to on-call",
      event_type: "incident.critical",
      schedule_type: "event",
      enabled: true,
      approval_required: false,
      cooldown_minutes: 5,
      created_at: iso(12),
      last_run_at: iso(0, 3),
      status: "enabled",
      actions: [{ type: "webhook", config: { url: "https://hooks.example.com/oncall", method: "POST" } }],
    },
    {
      id: "rule-2",
      name: "Nightly SIEM log aggregation",
      event_type: "schedule",
      schedule_type: "cron",
      cron_expression: "0 2 * * *",
      enabled: true,
      approval_required: false,
      created_at: iso(10),
      last_run_at: iso(0, 6),
      status: "enabled",
      actions: [{ type: "workflow", config: { workflow: "siem-export", params: { batch: 500 } } }],
    },
    {
      id: "rule-3",
      name: "Flag unusual API usage spikes",
      event_type: "usage.spike",
      schedule_type: "event",
      enabled: true,
      approval_required: true,
      created_at: iso(8),
      last_run_at: iso(1, 0),
      status: "enabled",
      actions: [{ type: "notification", config: { channel: "security-team" } }],
    },
    {
      id: "rule-4",
      name: "Daily workspace health digest",
      event_type: "schedule",
      schedule_type: "cron",
      cron_expression: "0 8 * * 1-5",
      enabled: true,
      approval_required: false,
      created_at: iso(6),
      last_run_at: iso(0, 1),
      status: "enabled",
      actions: [{ type: "email", config: { to: "admin@demo.local", template: "health-digest" } }],
    },
    {
      id: "rule-5",
      name: "Auto-tag knowledge base documents",
      event_type: "document.uploaded",
      schedule_type: "event",
      enabled: true,
      approval_required: false,
      created_at: iso(5),
      last_run_at: iso(0, 4),
      status: "enabled",
      actions: [{ type: "workflow", config: { workflow: "auto-tag" } }],
    },
    {
      id: "rule-6",
      name: "Weekly threat intel enrichment",
      event_type: "schedule",
      schedule_type: "cron",
      cron_expression: "0 3 * * 1",
      enabled: false,
      approval_required: false,
      created_at: iso(4),
      last_run_at: iso(4, 0),
      status: "disabled",
      actions: [{ type: "workflow", config: { workflow: "threat-intel" } }],
    },
  ],
  executions: [
    { id: "exec-1", rule_id: "rule-1", status: "completed", started_at: iso(0, 3), finished_at: iso(0, 3), result: { ok: true } },
    { id: "exec-2", rule_id: "rule-2", status: "completed", started_at: iso(0, 6), finished_at: iso(0, 6), result: { ok: true } },
    { id: "exec-3", rule_id: "rule-3", status: "pending_approval", started_at: iso(0, 7), finished_at: null, result: { status: "pending_approval" } },
    { id: "exec-4", rule_id: "rule-4", status: "completed", started_at: iso(0, 1), finished_at: iso(0, 1), result: { ok: true } },
    { id: "exec-5", rule_id: "rule-1", status: "failed", started_at: iso(1, 0), finished_at: iso(1, 0), result: { ok: false, error: "Webhook timeout after 10s" } },
  ],
  metrics: {
    total: 14,
    enabled: 13,
    executions_30d: 1284,
    success_rate_30d: 96.4,
    total_executions: 1284,
    successful: 1238,
    failed: 46,
    pending_approvals: 2,
    daily: [
      { date: iso(6), executions: 38, success_rate: 97.1 },
      { date: iso(5), executions: 42, success_rate: 95.2 },
      { date: iso(4), executions: 51, success_rate: 96.1 },
      { date: iso(3), executions: 47, success_rate: 97.9 },
      { date: iso(2), executions: 44, success_rate: 95.5 },
      { date: iso(1), executions: 49, success_rate: 96.9 },
      { date: iso(0), executions: 53, success_rate: 94.3 },
    ],
  },
};

export const demoAnomalies = {
  ok: true,
  demo: true,
  anomalies: [
    {
      id: "anom-1",
      title: "Unusual API key usage pattern",
      description: "API key aeon_live_8f2c made 1,240 requests in 15 minutes — 12x the normal rate.",
      severity: "high",
      status: "open",
      detected_at: iso(0, 2),
      source: "usage_analytics",
      workspace_id: "demo",
    },
    {
      id: "anom-2",
      title: "Failed login burst from single IP",
      description: "14 failed login attempts from 203.0.113.42 in 10 minutes.",
      severity: "critical",
      status: "open",
      detected_at: iso(0, 5),
      source: "security",
      workspace_id: "demo",
    },
    {
      id: "anom-3",
      title: "Automation execution latency spike",
      description: "P95 latency for the SIEM aggregation workflow rose from 340ms to 2.1s.",
      severity: "medium",
      status: "investigating",
      detected_at: iso(1, 0),
      source: "observability",
      workspace_id: "demo",
    },
    {
      id: "anom-4",
      title: "Unusual outbound webhook volume",
      description: "Outbound webhook deliveries to external endpoint increased 340% overnight.",
      severity: "medium",
      status: "resolved",
      detected_at: iso(2, 0),
      resolved_at: iso(1, 2),
      source: "integrations",
      workspace_id: "demo",
    },
    {
      id: "anom-5",
      title: "LLM token usage anomaly",
      description: "Workspace consumed 480K tokens in 6 hours — double the daily budget.",
      severity: "low",
      status: "resolved",
      detected_at: iso(3, 0),
      resolved_at: iso(2, 4),
      source: "llm_usage",
      workspace_id: "demo",
    },
  ],
  summary: { open: 2, investigating: 1, resolved: 4, critical: 1, high: 1, medium: 2, low: 1 },
};

export const demoIncidents = {
  ok: true,
  demo: true,
  incidents: [
    {
      id: "inc-1",
      title: "Elevated error rate on agent worker",
      severity: "high",
      status: "open",
      assignee: "SRE On-Call",
      created_at: iso(0, 3),
      updated_at: iso(0, 2),
      summary: "5xx responses on /api/chat rose to 2.8%. Worker pool saturation suspected.",
      runbook: "worker-saturation",
    },
    {
      id: "inc-2",
      title: "Stripe webhook processing delay",
      severity: "medium",
      status: "investigating",
      assignee: "Billing Team",
      created_at: iso(0, 8),
      updated_at: iso(0, 7),
      summary: "Webhook queue backlog of 23 events. Signature verification is healthy.",
      runbook: "stripe-webhook-backlog",
    },
    {
      id: "inc-3",
      title: "Knowledge base index drift",
      severity: "low",
      status: "resolved",
      assignee: "AI Platform",
      created_at: iso(2, 0),
      updated_at: iso(1, 6),
      resolved_at: iso(1, 6),
      summary: "Vector index was 4.2% stale. Rebuilt successfully.",
      runbook: null,
    },
  ],
  metrics: { open: 1, investigating: 1, resolved: 1, mt_ta: "8m 12s", mt_tr: "1h 04m" },
};

export const demoApiKeys = {
  ok: true,
  demo: true,
  keys: [
    { id: "key-1", name: "Production Frontend", key_prefix: "aeon_live_8f2c", created_at: iso(30), last_used_at: iso(0, 1), scopes: ["chat", "automations"], status: "active" },
    { id: "key-2", name: "CI Pipeline", key_prefix: "aeon_live_91ab", created_at: iso(21), last_used_at: iso(0, 4), scopes: ["automations", "sectors"], status: "active" },
    { id: "key-3", name: "Analytics Export", key_prefix: "aeon_live_44de", created_at: iso(14), last_used_at: iso(2, 0), scopes: ["usage"], status: "active" },
    { id: "key-4", name: "Legacy Batch Job", key_prefix: "aeon_live_77cc", created_at: iso(60), last_used_at: iso(12, 0), scopes: ["chat"], status: "revoked" },
  ],
  usage: { total_requests_30d: 148320, total_tokens_30d: 1842000, rate_limited_30d: 312 },
};

export const demoIntegrations = {
  ok: true,
  demo: true,
  integrations: [
    { id: "int-1", name: "Slack", type: "messaging", status: "connected", config_summary: "Team channel #aeon-alerts", installed_at: iso(20) },
    { id: "int-2", name: "GitHub", type: "devops", status: "connected", config_summary: "beatznlg/aeon · issues+PRs", installed_at: iso(18) },
    { id: "int-3", name: "Stripe", type: "billing", status: "connected", config_summary: "Production · team+enterprise plans", installed_at: iso(15) },
    { id: "int-4", name: "Sentry", type: "monitoring", status: "connected", config_summary: "aeon-web · aeon-backend", installed_at: iso(10) },
    { id: "int-5", name: "Webhook Relay", type: "webhooks", status: "connected", config_summary: "8 outbound endpoints", installed_at: iso(8) },
    { id: "int-6", name: "PagerDuty", type: "oncall", status: "error", config_summary: "Routing key requires rotation", installed_at: iso(6) },
  ],
  catalog: [
    { id: "slack", name: "Slack", description: "Alerts, approvals, and notifications", category: "messaging" },
    { id: "github", name: "GitHub", description: "Repo events and PR automation", category: "devops" },
    { id: "stripe", name: "Stripe", description: "Billing and subscription sync", category: "billing" },
    { id: "sentry", name: "Sentry", description: "Error tracking integration", category: "monitoring" },
    { id: "pagerduty", name: "PagerDuty", description: "Incident response on-call", category: "oncall" },
    { id: "webhook", name: "Outbound Webhooks", description: "Deliver events to any endpoint", category: "webhooks" },
  ],
};

export const demoObservability = {
  ok: true,
  demo: true,
  metrics: {
    requests_per_min: 84,
    error_rate_pct: 0.42,
    p95_latency_ms: 812,
    p50_latency_ms: 146,
    llm_spend_30d: 128.45,
    llm_tokens_30d: 1842000,
    active_workspaces: 1,
    failed_automations_30d: 46,
    webhook_failures_30d: 12,
    five_xx_30d: 87,
    health_score: 98.2,
    series: [
      { t: iso(6), requests: 61, errors: 0.3, latency: 720 },
      { t: iso(5), requests: 74, errors: 0.5, latency: 801 },
      { t: iso(4), requests: 68, errors: 0.2, latency: 690 },
      { t: iso(3), requests: 92, errors: 0.8, latency: 940 },
      { t: iso(2), requests: 79, errors: 0.4, latency: 760 },
      { t: iso(1), requests: 88, errors: 0.3, latency: 745 },
      { t: iso(0), requests: 84, errors: 0.4, latency: 812 },
    ],
  },
  usage: {
    total_requests_30d: 148320,
    total_tokens_30d: 1842000,
    total_cost_30d: 128.45,
    requests_by_provider: [
      { provider: "openai", requests: 82100, tokens: 980000, cost: 61.2 },
      { provider: "anthropic", requests: 38400, tokens: 520000, cost: 44.1 },
      { provider: "google", requests: 27820, tokens: 342000, cost: 23.15 },
    ],
  },
};

export const demoKnowledgeBases = {
  ok: true,
  demo: true,
  knowledge_bases: [
    { id: "kb-1", name: "Company Policies", document_count: 24, chunk_count: 342, status: "ready", updated_at: iso(2) },
    { id: "kb-2", name: "Product Documentation", document_count: 58, chunk_count: 812, status: "ready", updated_at: iso(1) },
    { id: "kb-3", name: "Support Knowledge Base", document_count: 132, chunk_count: 1940, status: "ready", updated_at: iso(0, 6) },
    { id: "kb-4", name: "Technical Runbooks", document_count: 16, chunk_count: 205, status: "indexing", updated_at: iso(0, 2) },
  ],
};

export const demoPrompts = {
  ok: true,
  demo: true,
  prompts: [
    { id: "pr-1", name: "Executive Summary", content: "Summarize the provided data into a concise executive briefing...", category: "summarization", updated_at: iso(3) },
    { id: "pr-2", name: "Threat Triage", content: "Classify this security alert by severity, impact, and recommended action...", category: "security", updated_at: iso(2) },
    { id: "pr-3", name: "Code Review Assistant", content: "Review this diff for bugs, security issues, and style problems...", category: "engineering", updated_at: iso(1) },
    { id: "pr-4", name: "Customer Response Draft", content: "Draft a professional, empathetic response to this customer message...", category: "support", updated_at: iso(0, 5) },
  ],
};

export const demoActivity = {
  ok: true,
  demo: true,
  events: [
    { id: "act-1", type: "automation.completed", title: "Nightly SIEM log aggregation completed", actor: "system", ts: iso(0, 1) },
    { id: "act-2", type: "user.login", title: "Demo Admin signed in", actor: "admin@demo.local", ts: iso(0, 2) },
    { id: "act-3", type: "automation.failed", title: "Webhook timeout on escalation rule", actor: "system", ts: iso(0, 3) },
    { id: "act-4", type: "api_key.created", title: "API key 'CI Pipeline' created", actor: "admin@demo.local", ts: iso(0, 5) },
    { id: "act-5", type: "incident.created", title: "Elevated error rate on agent worker", actor: "system", ts: iso(0, 6) },
    { id: "act-6", type: "backup.completed", title: "Database backup verified", actor: "system", ts: iso(0, 8) },
    { id: "act-7", type: "swarm.completed", title: "Risk assessment swarm finished", actor: "system", ts: iso(1, 0) },
    { id: "act-8", type: "knowledge.document_uploaded", title: "12 documents added to Product Documentation", actor: "admin@demo.local", ts: iso(1, 2) },
  ],
};

export const demoNotifications = {
  ok: true,
  demo: true,
  notifications: [
    { id: "not-1", type: "incident", title: "Elevated error rate on agent worker", body: "5xx responses rose to 2.8%", read: false, ts: iso(0, 3), icon: "🚨" },
    { id: "not-2", type: "automation", title: "Nightly SIEM aggregation completed", body: "48,120 log lines processed", read: false, ts: iso(0, 1), icon: "🤖" },
    { id: "not-3", type: "security", title: "New API key created", body: "CI Pipeline (aeon_live_91ab)", read: true, ts: iso(0, 5), icon: "🔑" },
    { id: "not-4", type: "system", title: "Backup verified", body: "PostgreSQL backup (2.4 GB) integrity OK", read: true, ts: iso(0, 8), icon: "💾" },
  ],
};

export const demoGovernance = {
  ok: true,
  demo: true,
  frameworks: [
    { id: "soc2", name: "SOC 2", kind: "audit", total: 6, verified: 4, pending: 2, failed: 0, coverage_pct: 66.7 },
    { id: "iso27001", name: "ISO/IEC 27001", kind: "audit", total: 6, verified: 4, pending: 2, failed: 0, coverage_pct: 66.7 },
    { id: "hipaa", name: "HIPAA (HITECH)", kind: "regulated", total: 6, verified: 3, pending: 3, failed: 0, coverage_pct: 50 },
    { id: "gdpr", name: "GDPR (EU)", kind: "regulated", total: 8, verified: 5, pending: 3, failed: 0, coverage_pct: 62.5 },
  ],
  audit_events: [
    { id: "aud-1", action: "evidence.verified", control_id: "audit_integrity", profile: "baseline", status: "verified", ts: iso(0, 4), actor: "system" },
    { id: "aud-2", action: "evidence.verified", control_id: "kms_validation", profile: "baseline", status: "verified", ts: iso(0, 5), actor: "system" },
    { id: "aud-3", action: "evidence.pending", control_id: "backup_restore", profile: "baseline", status: "pending", ts: iso(0, 6), actor: "system" },
    { id: "aud-4", action: "evidence.verified", control_id: "incident_response_exercise", profile: "baseline", status: "verified", ts: iso(1, 0), actor: "system" },
  ],
};

export const demoWorkspaces = {
  ok: true,
  demo: true,
  workspaces: [
    { id: "ws-1", name: "Demo Workspace", slug: "demo", plan: "team", role: "ADMIN", member_count: 1, created_at: iso(30) },
  ],
};

export const demoOperatingProfiles = {
  ok: true,
  demo: true,
  profiles: [
    { id: "profile-1", name: "Security Operations", description: "Hardened profile for SOC teams", kind: "security", color: "#ef4444", icon: "🛡️", enabled: true, created_at: iso(20) },
    { id: "profile-2", name: "Standard Operations", description: "Balanced defaults for daily operations", kind: "general", color: "#6366f1", icon: "⚙️", enabled: true, created_at: iso(18) },
    { id: "profile-3", name: "Finance & Compliance", description: "Regulatory-focused profile", kind: "finance", color: "#f59e0b", icon: "💰", enabled: false, created_at: iso(15) },
  ],
  active_profile: "profile-2",
  current: {
    profile_id: "profile-2",
    name: "Standard Operations",
    effective: { plugins: [], tools: [], settings: {} },
  },
  packs: [
    { id: "pack-1", name: "Security", description: "Governance and risk controls", kind: "security", enabled: true },
    { id: "pack-2", name: "Compliance", description: "Regulatory mapping and audits", kind: "compliance", enabled: true },
  ],
};

export const demoSectorPacks = {
  ok: true,
  demo: true,
  packs: [
    { id: "cybersecurity", name: "Cybersecurity", icon: "🛡️", color: "#ef4444", description: "Threat intel, SIEM, vulnerability management", risk: "high", tasks: ["threat_intel", "vuln_scan", "compliance", "incident_response"] },
    { id: "healthcare", name: "Healthcare", icon: "🏥", color: "#10b981", description: "HIPAA-aware diagnostics and triage", risk: "high", tasks: ["diagnostics", "triage", "records", "compliance"] },
    { id: "finance", name: "Finance", icon: "💰", color: "#f59e0b", description: "Risk, fraud, and regulatory analysis", risk: "high", tasks: ["risk", "fraud", "forecast", "regulatory"] },
    { id: "retail", name: "Retail", icon: "📦", color: "#6366f1", description: "Demand, inventory, and pricing", risk: "medium", tasks: ["demand", "inventory", "pricing", "analytics"] },
    { id: "manufacturing", name: "Manufacturing", icon: "🏭", color: "#0ea5e9", description: "Factory floor analytics and QA", risk: "medium", tasks: ["quality", "maintenance", "supply", "analytics"] },
    { id: "government", name: "Government", icon: "🏛️", color: "#8b5cf6", description: "Public sector compliance and services", risk: "critical", tasks: ["compliance", "audit", "reporting"] },
  ],
  summary: { total: 6, high_risk: 3, critical: 1 },
};

export const demoCapabilities = {
  ok: true,
  demo: true,
  capabilities: [
    { id: "cap-1", name: "Threat Intelligence", source: "builtin", category: "security", description: "Enrich indicators and correlate threats", requires_auth: true, risk: "medium" },
    { id: "cap-2", name: "Vulnerability Scan", source: "builtin", category: "security", description: "Identify CVEs in deployed packages", requires_auth: true, risk: "high" },
    { id: "cap-3", name: "Compliance Audit", source: "builtin", category: "governance", description: "Map evidence to frameworks", requires_auth: true, risk: "low" },
    { id: "cap-4", name: "Document Summarizer", source: "builtin", category: "ai", description: "Summarize long documents", requires_auth: true, risk: "low" },
    { id: "cap-5", name: "Slack Alert", source: "plugin:slack", category: "integrations", description: "Send alerts to a channel", requires_auth: true, risk: "low" },
    { id: "cap-6", name: "GitHub PR Review", source: "plugin:github", category: "integrations", description: "Review pull requests", requires_auth: true, risk: "medium" },
  ],
  count: 6,
  source_counts: { builtin: 4, "plugin:slack": 1, "plugin:github": 1 },
};

export const demoSwarm = {
  ok: true,
  demo: true,
  swarms: [
    { id: "swarm-1", name: "Security Risk Assessment", status: "completed", agents: 4, started_at: iso(1, 0), finished_at: iso(1, 0), tasks: 12 },
    { id: "swarm-2", name: "Quarterly Market Analysis", status: "running", agents: 3, started_at: iso(0, 2), finished_at: null, tasks: 8 },
    { id: "swarm-3", name: "Knowledge Base Audit", status: "completed", agents: 2, started_at: iso(3, 0), finished_at: iso(3, 0), tasks: 5 },
  ],
};

export const demoMarketplace = {
  ok: true,
  demo: true,
  plugins: [
    { id: "slack", name: "Slack", description: "Alerts, approvals, and notifications", category: "communication", verified: true, installed: true, version: "2.1.0", icon: "💬" },
    { id: "github", name: "GitHub", description: "Repo events and PR automation", category: "devops", verified: true, installed: true, version: "1.8.2", icon: "🐙" },
    { id: "stripe", name: "Stripe", description: "Billing and subscription sync", category: "billing", verified: true, installed: true, version: "3.0.1", icon: "💳" },
    { id: "sentry", name: "Sentry", description: "Error tracking integration", category: "monitoring", verified: true, installed: false, version: "1.2.0", icon: "📈" },
    { id: "pagerduty", name: "PagerDuty", description: "Incident response on-call", category: "oncall", verified: true, installed: false, version: "2.0.0", icon: "🚨" },
    { id: "webhook", name: "Outbound Webhooks", description: "Deliver events to any endpoint", category: "webhooks", verified: true, installed: true, version: "1.5.0", icon: "🔗" },
    { id: "tensorflow", name: "TensorFlow", description: "Run ML models in automations", category: "ai", verified: false, installed: false, version: "0.9.0", icon: "🧠" },
  ],
  summary: { plugins: 7, verified: 6, installed: 4 },
};

export const demoMcp = {
  ok: true,
  demo: true,
  servers: [
    { id: "mcp-1", name: "Filesystem Server", transport: "streamable-http", url: "http://localhost:3001/mcp", enabled: true, tools: ["read_file", "write_file", "list_dir"], status: "connected", last_sync_at: iso(0, 2) },
    { id: "mcp-2", name: "GitHub MCP", transport: "streamable-http", url: "https://api.github.com/mcp", enabled: true, tools: ["list_repos", "create_issue", "get_pr"], status: "connected", last_sync_at: iso(0, 5) },
    { id: "mcp-3", name: "Database MCP", transport: "streamable-http", url: "http://localhost:3002/mcp", enabled: false, tools: ["query", "schema"], status: "disconnected", last_sync_at: iso(5, 0) },
  ],
  agent_tools: [
    { id: "tool-1", server: "mcp-1", name: "read_file", description: "Read a file from disk" },
    { id: "tool-2", server: "mcp-2", name: "create_issue", description: "Create a GitHub issue" },
  ],
};

export const demoWorkflows = {
  ok: true,
  demo: true,
  workflows: [
    { id: "wf-1", name: "Incident Triage Pipeline", description: "Classify and route incoming incidents", status: "active", steps: 5, last_run_at: iso(0, 3), created_at: iso(12) },
    { id: "wf-2", name: "Nightly Data Sync", description: "Synchronize data between systems", status: "active", steps: 3, last_run_at: iso(0, 6), created_at: iso(10) },
    { id: "wf-3", name: "Report Generation", description: "Generate weekly executive reports", status: "draft", steps: 4, last_run_at: null, created_at: iso(4) },
    { id: "wf-4", name: "Onboarding Sequence", description: "Automate new workspace setup", status: "paused", steps: 8, last_run_at: iso(2, 0), created_at: iso(20) },
  ],
};

export const demoAgents = {
  ok: true,
  demo: true,
  agents: [
    { id: "agent-1", name: "Researcher", role: "researcher", status: "idle", tasks_completed: 482, last_active_at: iso(0, 2), model: "gpt-5.6" },
    { id: "agent-2", name: "Security Analyst", role: "analyst", status: "running", tasks_completed: 213, last_active_at: iso(0, 1), model: "claude-sonnet-4" },
    { id: "agent-3", name: "Writer", role: "writer", status: "idle", tasks_completed: 156, last_active_at: iso(1, 0), model: "gemini-3.7-flash" },
    { id: "agent-4", name: "Reviewer", role: "reviewer", status: "error", tasks_completed: 98, last_active_at: iso(0, 4), model: "gpt-5-mini" },
  ],
};

export const demoSiemIntegrations = {
  ok: true,
  demo: true,
  integrations: [
    { id: "siem-1", name: "Splunk", type: "siem", status: "connected", config_summary: "prod-index · 48 events/min", last_sync_at: iso(0, 1) },
    { id: "siem-2", name: "Elastic SIEM", type: "siem", status: "connected", config_summary: "security-events-* · 120 events/min", last_sync_at: iso(0, 2) },
    { id: "siem-3", name: "CrowdStrike", type: "edr", status: "error", config_summary: "API token expiring in 3 days", last_sync_at: iso(1, 0) },
    { id: "siem-4", name: "Datadog", type: "observability", status: "connected", config_summary: "all-host metrics", last_sync_at: iso(0, 4) },
    { id: "siem-5", name: "Palo Alto XSOAR", type: "soar", status: "disconnected", config_summary: "needs re-auth", last_sync_at: iso(8, 0) },
  ],
  providers: [
    { id: "splunk", name: "Splunk", description: "Enterprise SIEM platform" },
    { id: "elastic", name: "Elastic", description: "Open search and SIEM" },
    { id: "crowdstrike", name: "CrowdStrike", description: "Endpoint detection and response" },
    { id: "datadog", name: "Datadog", description: "Cloud monitoring and observability" },
  ],
};

export const demoBilling = {
  ok: true,
  demo: true,
  billing: {
    workspace_id: "demo",
    plan: {
      id: "team",
      name: "Team",
      limits: { requests: 100000, tokens: 5000000, workflows: 50, integrations: 25 },
    },
    credits: 8420,
    usage: { requests: 48210, tokens: 1842000, workflows: 14, integrations: 6 },
    estimated_cost: 49.0,
    remaining_credits: 8420,
    quota_usage_pct: { requests: 48.2, tokens: 36.8, workflows: 28, integrations: 24 },
  },
};

export const demoRetentionPolicy = {
  ok: true,
  demo: true,
  policy: {
    workspace_id: "demo",
    retention_days: 365,
    action: "archive",
    created_at: iso(30),
    updated_at: iso(2),
  },
};

export const demoAdminStats = {
  ok: true,
  demo: true,
  stats: {
    total_users: 3,
    total_workspaces: 1,
    total_memberships: 3,
    role_distribution: { ADMIN: 1, OPERATOR: 1, VIEWER: 1 },
    plan_distribution: { free: 0, team: 1, enterprise: 0 },
    total_audit_entries: 1284,
  },
};

export const demoApiKeyUsage = {
  ok: true,
  demo: true,
  usage: {
    total_calls: 148320,
    errors: 623,
    error_rate: 0.42,
    total_keys: 4,
    active_keys: 3,
    by_key: [
      { name: "Production Frontend", calls: 82100, errors: 210 },
      { name: "CI Pipeline", calls: 38400, errors: 190 },
      { name: "Analytics Export", calls: 27820, errors: 223 },
    ],
    by_endpoint: {
      "/api/chat": { calls: 62100, errors: 210 },
      "/api/automations/run": { calls: 38400, errors: 190 },
      "/api/sector/data": { calls: 27820, errors: 223 },
    },
  },
};

export const demoExecutionsList = {
  ok: true,
  demo: true,
  executions: demoAutomations.executions,
};

export const demoAuditRows = {
  ok: true,
  demo: true,
  rows: demoGovernance.audit_events,
  count: demoGovernance.audit_events.length,
};

export const demoMcpAgentTools = {
  ok: true,
  demo: true,
  tools: demoMcp.agent_tools,
};

export const demoWebhookDeliveries = {
  ok: true,
  demo: true,
  deliveries: [
    { id: "del-1", integration_id: "webhook", timestamp: Date.now() - 3600_000, payload: { event: "automation.completed", rule: "siem-aggregation" }, response_status: 200 },
    { id: "del-2", integration_id: "webhook", timestamp: Date.now() - 4 * 3600_000, payload: { event: "incident.created", incident_id: "inc-1" }, response_status: 200 },
    { id: "del-3", integration_id: "webhook", timestamp: Date.now() - 8 * 3600_000, payload: { event: "usage.spike" }, response_status: 502, error_message: "upstream timeout" },
    { id: "del-4", integration_id: "webhook", timestamp: Date.now() - 26 * 3600_000, payload: { event: "backup.completed" }, response_status: 200 },
  ],
};

export const demoHealthDetailed = {
  ok: true,
  demo: true,
  kernel: { status: "ok", backend: "demo (stub)" },
  agents: [
    { name: "aeon-core", status: "idle" },
    { name: "security-analyst", status: "running" },
    { name: "researcher", status: "idle" },
  ],
  queue: { size: 3, status: "healthy" },
  integrations: [
    { name: "slack", status: "connected" },
    { name: "stripe", status: "connected" },
    { name: "github", status: "connected" },
  ],
  storage: { usage_events_bytes: 1842000, usage_events_mb: 1.76 },
};

export const demoUsageSummary = {
  ok: true,
  demo: true,
  summary: {
    period_days: 30,
    workspace_id: "demo",
    total_events: 148320,
    total_quantity: 1842000,
    total_cost: 128.45,
    by_action: {
      "chat.completion": { count: 48210, cost: 61.2 },
      "automation.run": { count: 42100, cost: 38.4 },
      "knowledge.search": { count: 31110, cost: 14.2 },
      "sector.tool": { count: 26900, cost: 14.65 },
    },
    by_module: {
      chat: { count: 48210 },
      automations: { count: 42100 },
      knowledge: { count: 31110 },
      sectors: { count: 26900 },
    },
    by_day: {
      [iso(6).slice(0, 10)]: { count: 6100 },
      [iso(5).slice(0, 10)]: { count: 7400 },
      [iso(4).slice(0, 10)]: { count: 6800 },
      [iso(3).slice(0, 10)]: { count: 9200 },
      [iso(2).slice(0, 10)]: { count: 7900 },
      [iso(1).slice(0, 10)]: { count: 8800 },
      [iso(0).slice(0, 10)]: { count: 8400 },
    },
  },
};

export const demoMetricsSummary = {
  ok: true,
  demo: true,
  metrics: {
    period_days: 30,
    total_events: 148320,
    total_cost: 128.45,
    by_action: {
      "chat.completion": { count: 48210, cost: 61.2 },
      "automation.run": { count: 42100, cost: 38.4 },
      "knowledge.search": { count: 31110, cost: 14.2 },
      "sector.tool": { count: 26900, cost: 14.65 },
    },
    by_day: {
      [iso(6).slice(0, 10)]: { count: 6100 },
      [iso(5).slice(0, 10)]: { count: 7400 },
      [iso(4).slice(0, 10)]: { count: 6800 },
      [iso(3).slice(0, 10)]: { count: 9200 },
      [iso(2).slice(0, 10)]: { count: 7900 },
      [iso(1).slice(0, 10)]: { count: 8800 },
      [iso(0).slice(0, 10)]: { count: 8400 },
    },
  },
};

/**
 * Look up a demo response for a backend path. Returns null if the path has no
 * demo data (the caller should return the backend-down error instead).
 */
export function demoResponseForPath(path: string): { body: unknown; status: number } | null {
  // Normalize: strip query string, trailing slash
  const clean = path.split("?")[0].replace(/\/+$/, "");
  const segments = clean.split("/").filter(Boolean);

  const key = segments.join("/");

  const demoMap: Record<string, unknown> = {
    "dashboard/stats": demoDashboard,
    "automations": demoAutomations,
    "automations/metrics": demoAutomations.metrics,
    "automations/executions": demoExecutionsList,
    "anomalies": demoAnomalies,
    "incidents": demoIncidents,
    "api-keys": demoApiKeys,
    "api-keys/usage/summary": demoApiKeyUsage,
    "os/integrations": demoIntegrations,
    "os/integrations/catalog": demoIntegrations.catalog,
    "os/observability/metrics": demoMetricsSummary,
    "metrics": demoMetricsSummary,
    "os/observability/usage": demoUsageSummary,
    "usage/summary": demoUsageSummary,
    "os/observability/health": demoHealthDetailed,
    "health/detailed": demoHealthDetailed,
    "os/observability/snapshot": { ok: true, demo: true, workers: 4, memory_mb: 186, queue_depth: 3, uptime_s: 86400 * 12 },
    "os/ai/knowledge-bases": demoKnowledgeBases,
    "os/ai/prompts": demoPrompts,
    "activity": demoActivity,
    "notifications": demoNotifications,
    "governance/compliance": demoGovernance.frameworks,
    "governance/audit": demoAuditRows,
    "os/swarm": demoSwarm,
    "os/apps": {
      ok: true,
      demo: true,
      apps: [
        { id: "cybersecurity", name: "Security Command", icon: "🛡️", color: "#ef4444", status: "active", allowed_tools: ["threat_intel", "vuln_scan", "compliance", "siem", "audit", "incident_response", "malware_analysis", "phishing_detect", "access_review", "risk_assess", "policy_check", "forensics"] },
        { id: "health", name: "Health Command", icon: "🏥", color: "#10b981", status: "active", allowed_tools: ["diagnostics", "monitoring", "drug_check", "triage", "records", "compliance", "analytics", "telehealth"] },
        { id: "finance", name: "Finance Command", icon: "💰", color: "#f59e0b", status: "active", allowed_tools: ["risk", "forecast", "fraud", "trading", "reporting", "compliance", "portfolio", "credit", "audit", "regulatory"] },
        { id: "retail", name: "Commerce Command", icon: "📦", color: "#6366f1", status: "active", allowed_tools: ["demand", "inventory", "pricing", "catalog", "reviews", "loyalty", "supply", "analytics", "marketing"] },
      ],
    },
    "os/agent-plugins": { ok: true, demo: true, plugins: [] },
    "os/operating-profiles": demoOperatingProfiles,
    "operating-profiles": demoOperatingProfiles,
    "workspace/operating-profile": { ok: true, demo: true, ...demoOperatingProfiles.current },
    "os/sector-packs": demoSectorPacks,
    "sector-packs": demoSectorPacks,
    "os/capabilities": demoCapabilities,
    "capabilities": demoCapabilities,
    "os/marketplace": demoMarketplace,
    "marketplace/plugins": demoMarketplace,
    "os/mcp": demoMcp,
    "mcp/servers": demoMcp,
    "os/mcp/agent-tools": demoMcpAgentTools,
    "mcp/agent-tools": demoMcpAgentTools,
    "os/workflows": demoWorkflows,
    "workflows": demoWorkflows,
    "agents": demoAgents,
    "siem/integrations": demoSiemIntegrations,
    "siem/providers": demoSiemIntegrations.providers,
    "governance/retention": demoRetentionPolicy,
    "os/webhooks/deliveries": demoWebhookDeliveries,
    "webhooks/deliveries": demoWebhookDeliveries,
    "runbooks": { ok: true, demo: true, runbooks: [] },
    "approvals": { ok: true, demo: true, approvals: [{ id: "appr-1", event_type: "usage.spike", status: "pending", created_at: iso(0, 7), requested_by: "automation" }] },
    "inbound-webhooks": { ok: true, demo: true, webhooks: [] },
    "stripe/config": { ok: true, demo: true, configured: false },
    "events/broadcast": { ok: true },
    "workspaces": demoWorkspaces,
    "admin/stats": demoAdminStats,
  };

  // Workspace-scoped paths that vary by id still get a demo response.
  if (key.startsWith("billing/")) {
    return { body: demoBilling, status: 200 };
  }

  const hit = demoMap[key];
  if (hit === undefined) return null;

  // If the entry is already a full { ok: true } payload, use it directly.
  if (hit && typeof hit === "object" && "ok" in (hit as Record<string, unknown>)) {
    return { body: hit, status: 200 };
  }
  // Otherwise wrap it as a bare response for endpoints that return arrays.
  return { body: { ok: true, demo: true, data: hit }, status: 200 };
}
