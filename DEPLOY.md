# AEON Production Deployment Guide

This guide deploys the **AEON Python backend** to [Railway](https://railway.app) and the **Next.js frontend** to [Vercel](https://vercel.com).

---

## Architecture

```
┌─────────────┐      ┌─────────────────┐      ┌──────────────┐
│  Vercel     │──────▶│  Railway Flask  │──────▶│   Railway    │
│  Next.js    │      │  Backend        │      │   Postgres   │
└─────────────┘      └─────────────────┘      └──────────────┘
```

---

## 1. Backend — Deploy to Railway

### 1.1 Create a Railway Project

1. Go to [Railway Dashboard](https://railway.app/dashboard).
2. Click **New Project** → **Deploy from GitHub repo** → select `beatznlg/aeon`.
3. In the project, click **New** → **Service** → **+ Add Service** → **Empty Service**.
4. Click the service → **Settings** → **Build**:
   - **Builder**: `Docker`
   - **Dockerfile path**: `Dockerfile`
   - **Root directory**: `/` (repo root)
   - **Healthcheck Path**: `/health`
   - **Healthcheck Timeout**: `120`
5. Under **Deploy**, set:
   - **Restart Policy**: `ON_FAILURE`

Or, if Railway supports config files, point the service to `railway.backend.json`.

### 1.2 Add a Postgres Database

1. In the Railway project, click **New** → **Database** → **Add PostgreSQL**.
2. Once provisioned, open the Postgres service → **Connect** tab.
3. Copy the **Database URL** (it looks like `postgresql://...`).
4. Go to your backend service → **Variables** → **New Variable**:
   - Name: `AEON_DATABASE_URL`
   - Value: the copied Postgres URL

Railway injects `PORT` automatically. The backend reads it via `AEON_PYTHON_PORT` and defaults to `5000`.

### 1.3 Required Backend Environment Variables

| Variable | Value | Required |
|---|---|---|
| `AEON_DATABASE_URL` | `postgresql://user:pass@host:5432/db` | ✅ Yes |
| `NEXTAUTH_SECRET` | Same secret used by the frontend | ✅ Yes |
| `AEON_PYTHON_HOST` | `0.0.0.0` | No (default) |
| `AEON_PYTHON_PORT` | Railway injects `PORT` | No (default 5000) |
| `AEON_ROOT` | `/app/state` | No (Docker default) |
| `AEON_LLM_PROVIDER` | `stub`, `openai`, `anthropic` | No (default `stub`) |
| `AEON_ADMIN_EMAIL` | `admin@aeon.local` | No (first-run seed) |
| `AEON_ADMIN_PASSWORD` | strong password | No (first-run seed) |

### 1.4 Optional Provider Keys

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | OpenAI LLM provider |
| `ANTHROPIC_API_KEY` | Anthropic Claude provider |
| `HUGGINGFACE_TOKEN` | Hugging Face model downloads |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase admin key |
| `SUPABASE_ANON_KEY` | Supabase anon key |

### 1.5 Optional Stripe Keys

| Variable | Purpose |
|---|---|
| `STRIPE_API_KEY` | `sk_test_...` or `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook endpoint secret |
| `STRIPE_PRICE_TEAM` | Price ID for Team plan |
| `STRIPE_PRICE_ENTERPRISE` | Price ID for Enterprise plan |

### 1.6 Deploy Backend

Click **Deploy** in Railway. Wait for the healthcheck to pass.

Copy the backend public URL, e.g. `https://aeon-backend.up.railway.app`.

---

## 2. Frontend — Deploy to Vercel

### 2.1 Import Project

1. Go to [vercel.com/new](https://vercel.com/new).
2. Import `beatznlg/aeon`.
3. Configure:
   - **Framework Preset**: Next.js
   - **Root Directory**: `web`
   - **Build Command**: `next build`
   - **Output Directory**: `.next`

### 2.2 Required Vercel Environment Variables

| Variable | Value | Required |
|---|---|---|
| `NEXTAUTH_SECRET` | Strong random string (match backend) | ✅ Yes |
| `NEXTAUTH_URL` | `https://your-project.vercel.app` | ✅ Yes |
| `AEON_PYTHON_URL` | Backend public URL (e.g. `https://aeon-backend.up.railway.app`) | ✅ Yes |

### 2.3 Optional Variables

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `AEON_HF_SPACE_URL` | Hugging Face Gradio fallback |

---

## 3. Health Checks

After both services are deployed, run:

```bash
# Backend only
python scripts/healthcheck.py https://your-backend.up.railway.app/health

# Backend + frontend
python scripts/healthcheck.py https://your-backend.up.railway.app/health https://your-frontend.vercel.app/api/health
```

You should see `OK` for both.

---

## 4. Troubleshooting

### Backend healthcheck fails

- Check Railway deploy logs for import errors.
- Verify `AEON_DATABASE_URL` is set and the database is reachable.
- Ensure `PORT` env var is being used (Railway injects it automatically).

### Frontend returns "AEON_PYTHON_URL not set"

- Add `AEON_PYTHON_URL` in Vercel → Project Settings → Environment Variables.
- Redeploy after adding variables.

### Login fails / JWT errors

- `NEXTAUTH_SECRET` must be identical on backend and frontend.
- `NEXTAUTH_URL` must match the frontend public URL.

---

## 5. Monitoring in Production

The backend exposes Prometheus metrics at `/metrics`. Point your monitoring stack (or the included `monitoring/docker-compose.yml`) to the backend URL:

```yaml
scrape_configs:
  - job_name: 'aeon-backend'
    static_configs:
      - targets: ['https://your-backend.up.railway.app']
```

---

## 6. CI/CD

Existing GitHub Actions workflows handle deploys:

| Workflow | Trigger | Action |
|---|---|---|
| `docker-ci.yml` | push/PR to `main` | Lint, typecheck, build Docker images |
| `docker-release.yml` | tag `v*.*.*` | Push multi-arch images to GHCR |
| `vercel-deploy.yml` | push/PR to `main` | Deploy frontend to Vercel |

For Railway, you can also enable **GitHub integration** in Railway project settings for automatic deploys on push.
