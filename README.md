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

---

## 🛠️ Developer Experience

AEON ships with first-class developer tooling:

- **OpenAPI Spec & Swagger UI**: Start the backend and visit [`http://localhost:5000/docs`](http://localhost:5000/docs) for interactive documentation.
- **OpenAPI JSON**: `GET /openapi.json` serves the latest spec.
- **Official SDKs**:
  - Python SDK in [`sdk/python`](sdk/python)
  - TypeScript SDK in [`sdk/typescript`](sdk/typescript)
- **Quickstarts**: See [`examples`](examples) for runnable Python and TypeScript examples.

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
