# AEON OS — Threat Model & Penetration Test Scope

**Status: engineering threat model. This is NOT a completed independent
penetration test or security assessment.** An independent engagement is
required before regulated or government production (see
`docs/COMPLIANCE_READINESS.md`).

## 1. Assets and trust boundaries

| Asset | Sensitivity | Location |
|---|---|---|
| Tenant data (workspaces, episodes, documents, approvals) | High | PostgreSQL, Supabase (optional), local agent memory |
| LLM provider credentials | Critical | Process env / Keys API (never returned by APIs) |
| JWT / API keys / SSO tokens | Critical | Authorization headers, `aeon_auth`, `aeon_sso` |
| Agent state, RAG vectors, audit chain | High | Local agent roots, vector store, `audit_logs` |
| Marketplace plugins / MCP tool definitions | Medium | `aeon_marketplace`, `aeon_mcp` |

Trust boundaries: external client to Flask kernel; kernel to LLM providers
(OpenAI-compatible endpoints); kernel to Postgres/Redis/Supabase;
workflow/automation engine to outbound webhooks and integrations.

## 2. STRIDE summary

| Component | Spoofing | Tampering | Repudiation | Info disclosure | DoS | Elevation |
|---|---|---|---|---|---|---|
| Auth (JWT, SSO, SCIM) | M | - | - | L | L | M |
| Chat / agent routes | - | - | L | M | L | - |
| LLM provider endpoints | L | M | - | M | M | L |
| Automations / webhooks | M | M | - | M | M | M |
| Audit / compliance | - | M | M | M | - | - |
| Marketplace / MCP | M | M | L | M | L | M |

L=Low, M=Medium risk; see sections below for the control mapping.

## 3. Top threats: scenario, controls, residual risk

### 3.1 Prompt injection

- **Scenario**: a tenant prompt (or RAG document, plugin description, or MCP
tool description) instructs the model to ignore system rules, exfiltrate
conversation history, or emit credentials.
- **Current controls**: workspace-scoped agents; capability registry gating
built-ins/plugins/MCP tools; audit redaction at the log boundary;
no autonomous tool-improvement (evolution suggestions require review).
- **Residual risk**: no dedicated input/output classifier for
instruction-override content; tool-use permissions are not per-prompt.
- **Required external verification**: adversarial prompt-injection testing
over chat, RAG retrieval, plugin tool descriptions, and MCP tool schemas;
consider an injection classifier or allow-list of tool invocations.

### 3.2 Tenant isolation

- **Scenario**: user A reads or writes user B's workspace data via crafted
workspace IDs, agent keys, cache keys, or object-store prefixes.
- **Current controls**: `require_auth` + workspace membership checks on
workspace routes (chat/history return 403); RBAC roles; workspace-scoped
agents (`ws-<id>`); workspace-scoped approval/sector/automation reads.
- **Regression coverage**: `tests/test_provider_isolation.py`,
`tests/test_security_hardening.py`, `tests/test_approval_isolation.py`,
`tests/test_sectors.py`.
- **Residual risk**: every route/query/worker/cache key must be audited;
Supabase/object-storage prefixes are per-tenant but rely on env
configuration in the deployment.
- **Required external verification**: full tenant-isolation review across
every route, query, worker, cache key, storage prefix, and export.

### 3.3 SSRF

- **Scenario**: a tenant supplies a custom LLM base URL, integration endpoint,
or webhook target pointing at internal metadata services
(169.254.169.254), internal APIs, or localhost services.
- **Current controls**: `_normalize_base_url` rejects non-http(s) schemes,
embedded credentials, query strings, and fragments; integration/webhook
endpoints are managed by workspace operators; CORS is configurable.
- **Residual risk**: private/link-local address ranges are NOT blocked for
custom LLM endpoints; the integration proxy path needs review.
- **Required external verification**: SSRF testing against internal IPs,
DNS rebinding, redirect following, and metadata endpoints.

### 3.4 Data exfiltration

- **Scenario**: secrets or PII inside prompts, audit metadata, or SDK logs
leave the tenant boundary or reach audit stores unredacted.
- **Current controls**: `SecurityScanner` PII/PHI redaction; `_secure_metadata`
sanitizes audit metadata; audit rows never return raw contents; SSO config
redaction; API keys never returned by provider metadata.
- **Residual risk**: prompt text is not persisted in audit by design, but
conversation history storage and model provider requests are out of band.
- **Required external verification**: exfiltration testing on chat, history,
automation payloads, webhooks, and logs; verify provider contracts
(e.g., no training on customer data) with the chosen LLM vendor.

### 3.5 Authentication / authorization abuse

- **Scenario**: token theft, JWT forgery, SSO assertion reuse, API key
sharing, privilege escalation to SUPER_ADMIN.
- **Current controls**: JWT with production-secret validation, rotation
endpoints, API key hashing/rotation, RBAC roles, SSO (OIDC/SAML) with
joserfc verification, SCIM.
- **Residual risk**: rate limiting, lockout, and MFA are deployment
concerns; weak admin seed credentials must be changed.
- **Required external verification**: auth abuse testing, SSO
interoperability (Entra ID, Okta, PIV/CAC), session handling, and
token-replay testing.

### 3.6 Supply chain and dependency risk

- **Controls**: Bandit + pip-audit in CI; pinned heavy deps
(transformers>=5.x clears prior RCE advisories); SBOM script
(`scripts/sbom_report.py`).
- **Residual risk**: no image signing/verification in CI today; SBOM must be
regenerated and retained per release.
- **Required external verification**: SBOM/vulnerability scan review,
signing/verification of container images, provenance.

## 4. Independent penetration test scope (procurement checklist)

When engaging a tester, the scope must cover at minimum:

1. Prompt injection over chat, RAG, plugin tool descriptions, MCP schemas,
   and automation templates (including indirect injection).
2. Tenant isolation: workspace ID traversal, agent key forgery, cache key
   collisions, storage prefix confusion, export leakage.
3. SSRF: custom LLM endpoints, integration proxy, webhook deliveries,
   redirects, DNS rebinding, cloud metadata endpoints.
4. Data exfiltration: history, audit, logs, SDK error output, outbound
   webhooks, provider request payloads.
5. Auth: JWT/API key/SSO token handling, replay, rotation, revocation,
   RBAC bypass, admin abuse.
6. Automations: approval bypass, dry-run escape, action chain injection,
   sub-automation recursion abuse.
7. DoS: rate limiting, payload size limits, queue exhaustion, LLM cost abuse.
8. Supply chain: dependency advisories, build provenance, secret scanning.

Each finding must map to a control in `docs/compliance/CONTROL_MATRIX.md`
and a fix, with re-test evidence retained in the assurance ledger.
