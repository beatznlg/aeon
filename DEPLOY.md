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

### 1.1 Automated Setup (Recommended)

Install the Railway CLI and run the helper script:

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login (opens browser or uses token)
railway login

# 3. Run the setup helper
./scripts/setup-railway.sh [my-project-name]
```

This script will:
- Create a Railway project
- Provision a PostgreSQL database
- Add the `aeon-backend` service from the repo
- Set required environment variables
- Deploy the backend

### 1.2 Manual Setup

If you prefer the dashboard:

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

## 2. Backend — Deploy to Vercel (Experimental)

> ⚠️ Vercel is primarily a frontend/serverless platform. The AEON backend is a long-running Flask application with in-memory state, background threads, and heavy ML dependencies. This adapter works for simple requests, but expect slow cold starts, no persistent background jobs, and possible function-size failures if all ML packages are installed.
>
> For production, deploy the backend to **Railway** (Section 1 above) instead.

### 2.1 Create the Project

1. Go to [vercel.com/new](https://vercel.com/new).
2. Import `beatznlg/aeon`.
3. In **Project Settings**, use these values:
   - **Framework Preset**: `Other`
   - **Root Directory**: `/` (repo root)
   - **Build Command**: leave empty (Vercel auto-builds Python functions)
   - **Install Command**: leave empty
4. Open **Project Settings → General**, and change the local config file to `vercel.backend.json` if the dashboard lets you; otherwise deploy locally with the CLI in Step 2.3.

### 2.2 Required Vercel Environment Variables

Set these in **Project Settings → Environment Variables**:

| Variable | Value | Required |
|---|---|---|
| `AEON_DATABASE_URL` | `postgresql://...` | ✅ Yes |
| `NEXTAUTH_SECRET` | Same secret used by the frontend | ✅ Yes |
| `AEON_ROOT` | `/tmp/aeon_state` | ✅ Yes (ephemeral writable path) |
| `AEON_LLM_PROVIDER` | `stub`, `openai`, or `anthropic` | No (default `stub`) |
| `OPENAI_API_KEY` | OpenAI key | Only if provider is `openai` |
| `ANTHROPIC_API_KEY` | Anthropic key | Only if provider is `anthropic` |

### 2.3 Deploy from the CLI

If the Vercel dashboard does not let you select a custom config file, deploy manually:

```bash
npm install -g vercel
vercel --local-config vercel.backend.json --prod
```

### 2.4 Limitations on Vercel

| Feature | Behaviour |
|---|---|
| **Cold starts** | Every cold start re-imports all `aeon*.py` modules and heavy ML packages. First request may take 10–30 s. |
| **State** | In-memory agent cache, rate limiter, and job queue reset after each invocation. Use Postgres/Supabase as the source of truth. |
| **Background jobs** | `JobQueue` threads are created per-request but killed when the function returns. Async `/jobs/<id>` polling will not work reliably. |
| **Function size** | `torch`, `transformers`, and `sentence-transformers` can exceed Vercel's serverless function size limits. Consider trimming `requirements.txt` or using external LLM APIs only. |
| **Timeouts** | `maxDuration` is set to 60 s in `vercel.backend.json`. This requires Vercel Pro; the free tier is much shorter. |

### 2.5 Connect the Frontend

Copy the backend's Vercel URL (e.g. `https://aeon-backend.vercel.app`) and set it in the frontend project:

| Variable | Value |
|---|---|
| `AEON_PYTHON_URL` | `https://aeon-backend.vercel.app` |

Use the same `NEXTAUTH_SECRET` on both projects.

---

## 4. Frontend — Deploy to Vercel

### 4.1 Import Project

1. Go to [vercel.com/new](https://vercel.com/new).
2. Import `beatznlg/aeon`.
3. Configure:
   - **Framework Preset**: Next.js
   - **Root Directory**: `web`
   - **Build Command**: `next build`
   - **Output Directory**: `.next`

### 4.2 Required Vercel Environment Variables

| Variable | Value | Required |
|---|---|---|
| `NEXTAUTH_SECRET` | Strong random string (match backend) | ✅ Yes |
| `NEXTAUTH_URL` | `https://your-project.vercel.app` | ✅ Yes |
| `AEON_PYTHON_URL` | Backend public URL (e.g. `https://aeon-backend.up.railway.app`) | ✅ Yes |

### 4.3 Optional Variables

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `AEON_HF_SPACE_URL` | Hugging Face Gradio fallback |

---

## 5. Health Checks

After both services are deployed, run:

```bash
# Backend only
python scripts/healthcheck.py https://your-backend.up.railway.app/health

# Backend + frontend
python scripts/healthcheck.py https://your-backend.up.railway.app/health https://your-frontend.vercel.app/api/health
```

You should see `OK` for both.

---

## 6. Troubleshooting

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

## 7. Monitoring in Production

The backend exposes Prometheus metrics at `/metrics`. Point your monitoring stack (or the included `monitoring/docker-compose.yml`) to the backend URL:

```yaml
scrape_configs:
  - job_name: 'aeon-backend'
    static_configs:
      - targets: ['https://your-backend.up.railway.app']
```

---

## 8. CI/CD

Existing GitHub Actions workflows handle deploys:

| Workflow | Trigger | Action |
|---|---|---|
| `docker-ci.yml` | push/PR to `main` | Lint, typecheck, build Docker images |
| `docker-release.yml` | tag `v*.*.*` | Push multi-arch images to GHCR |
| `vercel-deploy.yml` | push/PR to `main` | Deploy frontend to Vercel |

For Railway, you can also enable **GitHub integration** in Railway project settings for automatic deploys on push.
