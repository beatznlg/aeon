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

## 📄 License

MIT — see [LICENSE](LICENSE)
