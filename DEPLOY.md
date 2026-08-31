# AEON OS — Google Cloud Production Deployment

AEON OS runs as a single full-stack production unit on Google Cloud Compute Engine: Next.js frontend, Flask API/kernel, PostgreSQL, Redis, Celery worker/Beat, and Caddy all run inside the GCP VM using Docker Compose.

## Architecture

```text
Internet
  |
Caddy :80/:443
  |-- Next.js :3000
  `-- Flask :5000
       |-- PostgreSQL :5432
       `-- Redis :6379
             |-- Celery worker
             `-- Celery Beat
```

Only Caddy is publicly exposed. PostgreSQL, Redis, API, workers and frontend are private Docker services.

## Quick start

1. Create an Ubuntu Compute Engine VM in Google Cloud.
2. Install Docker Engine and Docker Compose.
3. Clone this repository to `/opt/aeon`.
4. Create `/opt/aeon/.env` from `.env.gcp.example`.
5. Point your DNS A record at the VM public IP.
6. Set `AEON_DOMAIN`, `NEXTAUTH_URL`, `NEXT_PUBLIC_APP_URL`, CORS and production secrets.
7. Run:

```bash
cd /opt/aeon
bash scripts/deploy-gcp.sh
```

## Required environment variables

| Variable | Required | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | yes | PostgreSQL password |
| `AUTH_SECRET` | yes | Auth.js session signing |
| `AEON_JWT_SECRET` | yes | Kernel JWT signing |
| `AEON_MASTER_KMS_KEY` | yes | Encryption master key |
| `AEON_CORS_ALLOWED_ORIGINS` | yes | Browser/API origin allowlist |
| `AEON_DOMAIN` | yes | Public DNS name and HTTPS |
| `NEXTAUTH_URL` | yes | Auth.js canonical URL |
| `NEXT_PUBLIC_APP_URL` | yes | Public application URL |

Optional provider keys can be supplied for the configured AI provider. Stripe is external payment infrastructure and is not used for hosting.

## Verify

```bash
docker compose -f docker-compose.gcp.yml ps
curl --fail http://localhost/health
curl --fail http://localhost/api/health
```

All seven services must be healthy/running:
`postgres`, `redis`, `backend`, `web`, `worker`, `beat`, `caddy`.

## Automatic GitHub deployment

Production deployment is handled by `.github/workflows/deploy-gcp.yml` on every push to `main`.

Configure these GitHub Actions secrets:

- `GCP_HOST`
- `GCP_USER`
- `GCP_SSH_KEY`

The workflow connects to the GCP VM, verifies the checkout, runs the GCP deployment script, rebuilds the stack, and performs health verification. A failed health gate must not be treated as a successful deployment.

## Backups

Use the backup scripts to create PostgreSQL backups. Production backups should be copied to Google Cloud Storage so the VM is not the only copy.

## Production principle

Google Cloud is the sole hosting platform for AEON OS. Oracle Cloud, Vercel, Render, Railway and Supabase are not production runtime dependencies.
