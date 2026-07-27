# AEON OS v3.0

> **A**dvanced **E**volutionary **O**rchestrator **N**etwork — an open-source AI agent platform with multi-tenant workspaces, workflow builder, LLM provider switching, RAG knowledge bases, Stripe billing, and Prometheus monitoring.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/beatznlg/aeon/blob/main/aeon_colab.ipynb)

---

## 🚀 Quick Start — Self-Hosted

Run the full AEON OS stack (Postgres + Flask + Next.js) in one command:

```bash
# 1. Clone the repo
git clone https://github.com/beatznlg/aeon.git
cd aeon

# 2. Copy and configure environment
#    Required: NEXTAUTH_SECRET (generate with: openssl rand -base64 32)
#    Optional: LLM provider keys, Stripe keys, Supabase keys
cp .env.example .env
# Edit .env with your values

# 3. Launch everything
docker compose up --build
```

| Service | URL | Default Credentials |
|---|---|---|
| **Web Dashboard** | [http://localhost:3000](http://localhost:3000) | Admin login (if seeded) |
| **Flask API** | [http://localhost:5000](http://localhost:5000) | — |
| **Postgres** | `localhost:5432` | `aeon` / `aeon_dev_pass` |
| **Prometheus** | [http://localhost:9090](http://localhost:9090) *(with monitoring profile)* | — |
| **Grafana** | [http://localhost:3000](http://localhost:3000) *(with monitoring profile)* | `admin` / `admin` |

### With Monitoring Stack

```bash
docker compose -f docker-compose.yml -f monitoring/docker-compose.yml up --build
```

### Required Environment Variables

| Variable | Description | Example |
|---|---|---|
| `NEXTAUTH_SECRET` | Frontend auth secret | `openssl rand -base64 32` |
| `NEXTAUTH_URL` | Public frontend URL | `http://localhost:3000` |
| `AEON_DATABASE_URL` | Postgres connection string *(defaults to internal)* | `postgresql://aeon:...@postgres:5432/aeon` |
| `OPENAI_API_KEY` | OpenAI LLM provider | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic LLM provider | `sk-ant-...` |

### Admin Seed (First Run)

Set these in `.env` to auto-create an admin user on first startup:

```env
AEON_ADMIN_EMAIL=admin@aeon.local
AEON_ADMIN_PASSWORD=admin123
AEON_ADMIN_NAME=AEON Admin
```

---

## 📦 Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Next.js     │────▶│  Flask AI Kernel │────▶│  Postgres   │
│  Frontend    │     │  (aeon_server)   │     │  Database   │
│  :3000       │     │  :5000           │     │  :5432      │
└──────────────┘     └──────────────────┘     └─────────────┘
       │                      │
       │                      ├──▶ AeonKernel (agent loop)
       │                      ├──▶ Workflow Engine
       │                      ├──▶ RAG / Vector Store
       │                      ├──▶ Integration Gateway
       │                      └──▶ Usage Metering
       │
       └── Optional Monitoring Stack ───┐
                              ┌─────────▼──────────┐
                              │  Prometheus  Grafana │
                              │  Alertmanager        │
                              └─────────────────────┘
```

---

## 🧩 Features

| Phase | Area | Status |
|---|---|---|
| **0** | Auth, Multi-tenancy, Postgres Persistence | ✅ |
| **1** | Chat & API — LLM Provider Switching | ✅ |
| **2b** | Workflow Builder — Canvas, Execution | ✅ |
| **2c** | API Keys & Rate Limiting | ✅ |
| **3** | Integrations — Slack, GitHub, Webhooks, Marketplace | ✅ |
| **4** | Usage Metering & Billing Dashboards | ✅ |
| **5** | Stripe — Checkout, Portal, Webhooks | ✅ |
| **6** | Vector Store & RAG — KB, Documents, Hybrid Search | ✅ |
| **7** | Monitoring & Alerting — Prometheus, Grafana | ✅ |
| **10** | Developer Experience — OpenAPI, SDKs, Quickstarts | ✅ |
| **14** | Advanced Agent Orchestration — Multi-Agent Swarms | ✅ |
| **15** | Multi-Language SDKs — Python, TypeScript, Go + Generator | ✅ |
| **16** | Admin Panel, Notifications & Event System | ✅ |
| **17** | Real-time Activity Feed & Presence | ✅ |
| **18** | Event-Driven Automations — If-This-Then-That for AEON events | ✅ |
| **19** | Human-in-the-Loop (HITL) Approvals — approval checkpoints for automations | ✅ |
| **20** | Scheduled Automations (Cron Triggers) — time-based background execution | ✅ |
| **21** | Inbound Webhooks & Slack HITL — external triggers and interactive approvals | ✅ |
| **22** | Automation Execution History & Observability — dashboard for automation runs, statuses, errors, and retries | ✅ |
| **23** | Dynamic Context Mapping & Outbound Webhooks — `{{ event.payload }}` templating and bidirectional HTTP actions | ✅ |
| **24** | Advanced Condition Engine — MongoDB-style operators (`$gt`, `$in`, `$contains`, `$regex`, `$and`/`$or`/`$not`) and nested dot-path conditions | ✅ |
| **25** | Automation Rule Cooldown / Throttling — `cooldown_minutes` to prevent runaway rule executions | ✅ |
| **26** | Sequential Multi-Step Action Chains — ordered `actions` array with per-step context (`{{ steps.0.data.summary }}`) | ✅ |
| **27** | Conditional Branching in Action Chains — per-step `run_if` conditions using `event`, `steps`, and `rule` context | ✅ |
| **28** | Action Chain Iterators (For-Each Loops) — process arrays with `loop_over` and `{{ item }}` / `{{ loop.index }}` context | ✅ |
| **29** | Action Chain Error Handling & Fallbacks — per-step `on_error` fallback actions and `continue_on_error` resilience | ✅ |
| **30** | Automation Time Delays (Wait Steps & Async Resumption) — `delay` actions that sleep and resume via scheduled resumption | ✅ |
| **31** | Event-Based Async Resumption (Wait for Event) — `wait_for_event` actions that suspend workflows until a matching external event arrives | ✅ |
| **32** | Persistent Automation State (Key-Value Variables) — `set_variable`, `get_variable`, `delete_variable`, `increment_variable`, and `{{ state.KEY }}` templates | ✅ |
| **33** | Sub-Automations (Rule Chaining) — `call_rule` actions to compose reusable workflows with payload passing and circular-loop mitigation | ✅ |

---

## 🛠️ Developer Experience

AEON ships with first-class developer tooling and auto-generated multi-language SDKs:

- **OpenAPI Spec & Swagger UI**: Start the backend and visit [`http://localhost:5000/docs`](http://localhost:5000/docs) for interactive documentation.
- **OpenAPI JSON**: `GET /openapi.json` serves the latest spec.
- **Official SDKs** (hand-crafted, full API coverage):
  - [Python SDK](sdk/python) — `pip install aeon-os`
  - [TypeScript SDK](sdk/typescript) — `npm install aeon-os`
  - [Go SDK](sdk/go) — `import "github.com/beatznlg/aeon/sdk/go/aeon"`
- **SDK Generator** ([`sdk/generator`](sdk/generator)) — auto-generates idiomatic clients from the OpenAPI spec:
  ```bash
  python3 sdk/generator/generate.py
  # Produces sdk/python/aeon_sdk.py, sdk/typescript/src/index.ts, sdk/go/aeon/aeon.go
  ```
- **Quickstarts**: See [`examples`](examples) for runnable Python, TypeScript, and Go examples.

## 🔧 SDK Reference

### Python

```python
from aeon_sdk import AeonClient

client = AeonClient("http://localhost:5000", api_key="aeon_...")
health = client.health()
reply = client.chat("Hello!")
```

### TypeScript

```typescript
import { AeonClient } from "aeon-os";

const client = new AeonClient({ baseURL: "http://localhost:5000", apiKey: "aeon_..." });
const health = await client.health();
const reply = await client.chat("Hello!");
```

### Go

```go
import "github.com/beatznlg/aeon/sdk/go/aeon"

client := aeon.NewClient("http://localhost:5000", aeon.WithAPIKey("aeon_..."))
health, err := client.Health()
reply, err := client.Chat("Hello!", "", "")
```

---

## 🐳 Docker Services

### Backend (`Dockerfile`)
- Python 3.11 slim runtime
- Healthcheck on `/health`
- Auto-waits for Postgres, runs DB schema bootstrap, seeds admin
- Exposes Prometheus metrics on `/metrics`

### Frontend (`web/Dockerfile`)
- Node 20 Alpine, multi-stage build
- Production Next.js with `npm run start`
- Proxies API calls to backend via `AEON_PYTHON_URL`

### Database (`postgres:16-alpine`)
- UUID, pg_trgm, and hstore extensions enabled
- Persistent volume at `postgres-data`

---

## 🔧 Development

```bash
# Backend (local)
python aeon_server.py

# Frontend (local)
cd web && npm install && npm run dev

# With monitoring
cd monitoring && docker compose up --build
```

---

## 📊 Monitoring

See [monitoring/README.md](monitoring/README.md) for the full observability stack:
- **Prometheus** — metrics scraping at `/metrics`
- **Alertmanager** — alert routing to Slack/email
- **Grafana** — pre-built dashboard with 8+ panels

---

## 🔒 Security (Phase 13)

AEON includes a hardened security layer:

- **Baseline security headers**: `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Permissions-Policy`, etc.
- **CORS**: configurable via `AEON_CORS_ALLOWED_ORIGINS` and `AEON_CORS_ALLOW_CREDENTIALS`.
- **RBAC**: workspace-scoped roles (`VIEWER`, `OPERATOR`, `ADMIN`, `SUPER_ADMIN`) enforced on sensitive routes.
- **API key rotation**: `POST /api-keys/<id>/rotate`.
- **JWT rotation**: `POST /auth/jwt/rotate` and `GET /auth/jwt/status`.
- **Audit PII redaction**: automatic redaction of emails, keys, and tokens in audit metadata.
- **CI security scans**: Bandit and pip-audit run on every PR.

### Local Security Scanning

Run the same checks locally before opening a PR:

```bash
# Static security analysis of Python source (zero open issues)
bandit -c bandit.yaml -r aeon*.py

# Dependency vulnerability audit
pip-audit -r requirements.txt -r requirements-dev.txt --desc
```

AEON now pins `transformers>=5.5.0` and `sentence-transformers>=5.6.1`, which clears the previous `transformers` 4.x RCE findings. The remaining project dependencies pass `pip-audit` cleanly.

---

## ✋ Human-in-the-Loop Approvals (Phase 19)

AEON automations can require human approval before executing. When a rule has `approval_required: true`, the automation engine pauses and creates a pending approval request instead of running the action. Workspace operators can review the request in `/os/approvals` and choose to approve or reject it. Approved requests execute the deferred action immediately; rejected requests are logged and skipped.

### Approval API

```bash
GET    /approvals?status=pending   # list pending approvals
POST   /approvals                  # create a manual approval request
GET    /approvals/<id>             # view a single approval
POST   /approvals/<id>/resolve     # { "decision": "approved" | "rejected", "reason": "..." }
```

---

## 🤖 Advanced Agent Orchestration (Phase 14)

AEON can now coordinate multiple agents as a swarm to solve complex tasks:

- **Role-based agents**: planner, executor, reviewer, and summarizer roles.
- **Task allocation**: the planner decomposes a prompt into `SwarmTask`s and assigns them to agents by capability/role.
- **Message bus**: every swarm has an shared inbox and broadcast log.
- **Reflection loop**: the reviewer agent reflects on task outputs and can request corrective follow-ups.
- **Safe evolution hook**: the reviewer can emit `tool_improvement` JSON suggestions; they are returned for explicit review and are never auto-executed.

### Swarm API

```bash
POST /swarm/run
{
  "app_ids": ["researcher", "writer", "reviewer", "editor"],
  "prompt": "Write a security runbook for the new API",
  "roles": {
    "researcher": "planner",
    "writer": "executor",
    "reviewer": "reviewer",
    "editor": "summarizer"
  }
}
```

```bash
GET  /swarm/<swarm_id>
GET  /swarm/<swarm_id>/messages
```

The `POST /swarm/run` response includes the `swarm_id`, per-agent `roles`, the task breakdown, reflection, summary, and any evolution suggestions.

---

##  License

MIT — see [LICENSE](LICENSE)
