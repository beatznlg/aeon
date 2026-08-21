# AEON OS — Production Deployment Guide

## Architecture Overview

AEON OS uses a **split deployment** model:

| Component | Stack | Deployment Platform | URL Pattern |
|-----------|-------|-------------------|-------------|
| Frontend | Next.js 14, React, Tailwind, shadcn/ui | Vercel | `https://app.aeonos.com` |
| Backend | Flask/Python 3.11, SQLAlchemy | Railway (Docker) | `https://api.aeonos.com` |
| Database | PostgreSQL 15+ | Railway Managed / Supabase | — |
| Cache | Redis 7+ (optional) | Railway Managed | — |

The frontend proxies API requests to the backend via Next.js API routes or direct rewriting.

---

## Prerequisites

- **Node.js** 18+ and **Bun** (for frontend)
- **Python** 3.11+ (for backend)
- **PostgreSQL** 15+ (or Supabase)
- **Redis** 7+ (optional, for caching and job queues)
- **Stripe** account (for billing)
- **OpenAI / Anthropic / other LLM** API key (for AI features)

---

## 1. Backend Deployment (Railway)

### Environment Variables

Set these in Railway's dashboard under **Variables**:

```bash
# ── Required ────────────────────────────────────────────────────────────────
AEON_DATABASE_URL=postgresql://user:pass@host:5432/aeon
AEON_JWT_SECRET=<random-64-char-string>    # openssl rand -base64 48
NEXTAUTH_SECRET=<same-as-frontend>          # Must match frontend
AEON_ENV=production

# ── Auth ────────────────────────────────────────────────────────────────────
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD_HASH=<werkzeug-hash>         # Generate: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"
ADMIN_NAME=Platform Admin

# ── CORS ────────────────────────────────────────────────────────────────────
AEON_CORS_ALLOWED_ORIGINS=https://app.aeonos.com,https://aeonos.com

# ── LLM Provider (choose one) ──────────────────────────────────────────────
AEON_LLM_PROVIDER=openai                    # or anthropic, google, mistral, etc.
OPENAI_API_KEY=sk-...                       # Required if provider=openai

# ── Stripe (billing) ────────────────────────────────────────────────────────
STRIPE_API_KEY=sk_live_...                  # or sk_test_... for staging
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_TEAM=price_...                 # Team plan price ID
STRIPE_PRICE_ENTERPRISE=price_...           # Enterprise plan price ID

# ── Supabase (optional, for automation rules) ───────────────────────────────
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# ── Rate Limiting ───────────────────────────────────────────────────────────
AEON_RATE_LIMIT_USER=600                    # Per-user requests/min
AEON_RATE_LIMIT_WORKSPACE=1800              # Per-workspace requests/min

# ── Optional ────────────────────────────────────────────────────────────────
AEON_REDIS_URL=redis://...                  # Enables caching and job queues
HUGGINGFACE_TOKEN=hf_...                    # For HuggingFace models
AEON_API_TOKEN=<shared-secret>              # For service-to-service auth
```

### Docker Build

The backend uses a multi-stage Dockerfile:

```bash
# Build
docker build -t aeon-backend -f Dockerfile .

# Run (local testing)
docker run -p 5000:5000 \
  -e AEON_DATABASE_URL=postgresql://... \
  -e AEON_JWT_SECRET=... \
  aeon-backend
```

### Database Migrations

Migrations run **automatically** on startup via the Docker entrypoint. The entrypoint:

1. Waits for PostgreSQL to be ready
2. Runs `migrate_database()` which applies Alembic migrations
3. Seeds admin user if `ADMIN_EMAIL` and `ADMIN_PASSWORD_HASH` are set
4. Starts the Flask server

For manual migration control:

```bash
# Apply migrations
python3 -c "from aeon_db import migrate_database; migrate_database()"

# Check current migration head
python3 -m alembic current

# Generate new migration (after ORM model changes)
python3 -m alembic revision --autogenerate -m "description"
```

### Health Endpoints

| Endpoint | Purpose | Auth Required |
|----------|---------|---------------|
| `GET /health` | Liveness + dependency status | No |
| `GET /ready` | Readiness probe (env, agents, queue) | No |
| `GET /health/detailed` | Full health with AI ledger + dead letters | No |
| `GET /metrics` | Prometheus-format metrics | No |

The Railway healthcheck uses `GET /health` (configured in `railway.backend.json`).

---

## 2. Frontend Deployment (Vercel)

### Environment Variables

Set these in Vercel's dashboard under **Settings → Environment Variables**:

```bash
# ── Required ────────────────────────────────────────────────────────────────
NEXTAUTH_SECRET=<same-as-backend>           # Must match backend JWT secret
NEXTAUTH_URL=https://app.aeonos.com
AEON_PYTHON_URL=https://api.aeonos.com     # Backend API URL

# ── Optional ────────────────────────────────────────────────────────────────
NEXT_PUBLIC_APP_NAME=AEON OS
NEXT_PUBLIC_APP_URL=https://app.aeonos.com
```

### Build & Deploy

```bash
# Local build test
cd web && npm install && npm run build

# Vercel deploys automatically on push to main
# Or deploy manually:
vercel --prod
```

### Vercel Configuration

The `vercel.json` at the project root configures:
- Build command: `cd web && npm install && npm run build`
- Output directory: `web/.next`
- API function timeout: 120s

---

## 3. Stripe Setup

### Required Price IDs

Create these in the Stripe Dashboard:

1. **Team Plan** — Monthly subscription
   - Create a Product → Add a Price (recurring, monthly)
   - Set `STRIPE_PRICE_TEAM` env var to the price ID

2. **Enterprise Plan** — Monthly subscription
   - Create a Product → Add a Price (recurring, monthly)
   - Set `STRIPE_PRICE_ENTERPRISE` env var to the price ID

### Webhook Configuration

1. Go to **Stripe Dashboard → Developers → Webhooks**
2. Add endpoint: `https://api.aeonos.com/stripe/webhook`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copy the **signing secret** → set as `STRIPE_WEBHOOK_SECRET`

---

## 4. Security Checklist

### Authentication
- [ ] `AEON_JWT_SECRET` is a strong random string (≥32 chars)
- [ ] `NEXTAUTH_SECRET` matches between frontend and backend
- [ ] `AEON_ENV=production` (disables dev fallbacks)
- [ ] Admin password is hashed with `werkzeug.security.generate_password_hash`

### Network
- [ ] `AEON_CORS_ALLOWED_ORIGINS` is set to your actual domains only
- [ ] Backend is not exposed to public internet without HTTPS
- [ ] Database is in a private network (not public IP)

### Secrets
- [ ] No secrets in git history
- [ ] All API keys set through platform secret managers
- [ ] `.env` files are gitignored

### Rate Limiting
- [ ] Per-user and per-workspace rate limits are configured
- [ ] Stripe webhook has signature verification enabled

### Data
- [ ] Audit logging is enabled (default)
- [ ] AI execution ledger is recording (default)
- [ ] Backup policies are configured for production data

---

## 5. Monitoring & Observability

### Built-in Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service health with dependency checks |
| `GET /health/detailed` | Full health: DB, governance, Stripe, AI ledger, dead letters |
| `GET /ready` | Readiness: environment, loaded agents, queue status |
| `GET /metrics` | Prometheus metrics |
| `GET /operations/snapshot` | Admin: worker queue, memory, automations |
| `GET /operations/observability` | Admin: AI stats, dependency health, security events |
| `GET /events` | Domain event outbox status |

### Key Metrics to Monitor

- Request rate and latency (from `/metrics`)
- Error rate (5xx responses)
- AI execution cost and token usage (`/ai/ledger/summary`)
- Pending events in outbox (`/events`)
- Dead letter count (`/health/detailed`)
- Automation execution success/failure rate

---

## 6. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `503 on /health` | Database not reachable — check `AEON_DATABASE_URL` |
| `401 on all endpoints` | `AEON_JWT_SECRET` not set or mismatched |
| `CORS errors` | `AEON_CORS_ALLOWED_ORIGINS` doesn't include frontend URL |
| `Stripe webhook 400` | `STRIPE_WEBHOOK_SECRET` wrong or missing |
| `Migration errors` | Run `python3 -m alembic upgrade head` manually |
| `Blank preview` | Frontend env vars missing — check `AEON_PYTHON_URL` |
| `Rate limited` | Increase `AEON_RATE_LIMIT_USER` or check for loops |

### Logs

```bash
# Railway logs
railway logs

# Docker logs
docker logs <container-id>

# Local development
python3 aeon_server.py  # Logs to stdout
```

---

## 7. Rollback Procedure

### Backend
1. Railway keeps previous deployments — use Railway dashboard to roll back
2. Database migrations are forward-only; if a migration causes issues, fix forward

### Frontend
1. Vercel keeps deployment history — use Vercel dashboard to promote a previous deployment
2. No database changes on the frontend side

### Database
1. If a migration breaks, create a fix-forward migration
2. For data issues, restore from backup (see `/backup` endpoints)

---

## 8. Production Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AEON_DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `AEON_JWT_SECRET` | ✅ | — | JWT signing secret (≥32 chars) |
| `NEXTAUTH_SECRET` | ✅ | — | Must match frontend |
| `AEON_ENV` | ✅ | `development` | Set to `production` |
| `AEON_CORS_ALLOWED_ORIGINS` | ✅ | — | Comma-separated allowed origins |
| `ADMIN_EMAIL` | ✅ | — | Initial admin email |
| `ADMIN_PASSWORD_HASH` | ✅ | — | Werkzeug password hash |
| `ADMIN_NAME` | — | `Admin` | Admin display name |
| `AEON_LLM_PROVIDER` | — | `stub` | LLM provider name |
| `OPENAI_API_KEY` | — | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | — | Anthropic API key |
| `STRIPE_API_KEY` | — | — | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | — | — | Stripe webhook signing secret |
| `STRIPE_PRICE_TEAM` | — | — | Stripe price ID for Team plan |
| `STRIPE_PRICE_ENTERPRISE` | — | — | Stripe price ID for Enterprise plan |
| `SUPABASE_URL` | — | — | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | — | — | Supabase service role key |
| `AEON_REDIS_URL` | — | — | Redis connection string |
| `AEON_RATE_LIMIT_USER` | — | `600` | Per-user requests/minute |
| `AEON_RATE_LIMIT_WORKSPACE` | — | `1800` | Per-workspace requests/minute |
| `AEON_API_TOKEN` | — | — | Shared secret for service auth |
| `AEON_PYTHON_HOST` | — | `0.0.0.0` | Bind host |
| `AEON_PYTHON_PORT` | — | `5000` | Bind port |
