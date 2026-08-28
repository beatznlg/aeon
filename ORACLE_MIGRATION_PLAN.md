# AEON OS — Oracle Cloud Migration Plan

Written before any destructive change, per the inspect-first rule. This plan is
based on a full audit of the repository at commit `7fe084c` plus the working
tree (PostgreSQL-backed login bridge, `AEON_API_TOKEN` identity bridge, admin
seeding hardening).

## 1. Current architecture

```text
Browser
  ↓
Next.js 15 frontend (`web/`, React 19, Tailwind, Auth.js v5 credentials)
  ↓ same-origin `/api/*` routes → server proxy (`web/lib/proxy.ts`,
    `web/lib/backend-fetch.ts`) with demo-data fallback
Flask backend (`aeon_server.py`, SQLAlchemy 2.0, Alembic migrations)
  ↓
PostgreSQL (Docker container, persistent `pgdata` volume)
  ↓
LLM providers via `aeon_llm.py` (stub default; OpenAI, Anthropic, Google,
Mistral, OpenRouter, Ollama, LM Studio, vLLM, HF, Qwen, custom endpoints)
```

Stateful extras: local JSON stores under `AEON_ROOT` (approvals, inbound
webhooks, AI ledger), optional Supabase REST mirroring, optional Redis/Celery.

## 2. Current hosting inventory (audited)

| Provider reference | Where it appears | Status |
|---|---|---|
| Oracle Cloud | `docker-compose.oci.yml`, `scripts/deploy-oracle.sh`, `scripts/aeon-autoupdate.sh`, `.github/workflows/deploy-oracle.yml`, `DEPLOY.md`, `DEPLOY_ORACLE.md`, `PRODUCTION.md` | **Production target (kept)** |
| Supabase | optional REST fallbacks in `aeon_*.py`, `web/lib/supabase.ts`, `web/auth.ts` fallback chain | Optional dependency, not hosting; local PostgreSQL remains authoritative |
| Vercel | `web/.env.example` comment, `.gitignore` comment | Cosmetic only; no Vercel config or build path |
| Railway | `.github/workflows/railway-deploy.yml`, `scripts/setup-railway.sh` | Unused alternate host — removed (see §11) |
| Colab/Lightning | `colab_runner.ipynb`, notebook badge | Legacy notebook artifact, not deployment |
| Tencent CloudBase | (working tree only, never committed/deployed) | Unused scaffolding — removed (see §11) |

No code path points production traffic at Vercel/Supabase/Render/Railway.
Frontend API calls are same-origin (`/api/*`), proxied server-side to
`AEON_PYTHON_URL`; no hardcoded production IP or localhost in shipped config
defaults beyond dev fallbacks documented in `env.example`.

## 3. What already works on Oracle (verified in this session)

- `docker-compose.oci.yml`: postgres + backend + web + Caddy, health checks,
  persistent volumes (`pgdata`, `backend_state`, `web_data`, Caddy data).
- `scripts/deploy-oracle.sh`: Docker install, iptables/ufw 80/443, secret
  generation, admin seed, auto-update timer install.
- `scripts/aeon-autoupdate.sh` + systemd timer: pull-only-when-changed
  redeploys with health gate and admin re-seed.
- Auth fixes (committed + working tree): registration persists via
  `seed_admin.py` transaction fix; Next.js → Flask identity bridge via shared
  `AEON_API_TOKEN` (`X-API-Token` + `X-User-*` headers); offline local-user
  fallback store; demo account (`admin@demo.local` / `demo123`) works without
  the backend; env self-repair seeds the configured admin.
- Backend tests: 30/30 passed (`tests/test_auth.py`, `tests/test_demo_seed.py`,
  `tests/test_health.py`). Frontend production build passes.

## 4. Target architecture (unchanged from what exists, now completed)

```text
GitHub (main)
  ↓ push
GitHub Actions deploy-oracle.yml
  ├── pre-deploy: pg_dump backup on VM (scripts/backup-db.sh)
  ├── pull latest main, docker compose up -d --build
  ├── health gate: /health + /api/health
  └── on failure: git reset --hard <previous SHA>, rebuild, re-verify (rollback)
Oracle Cloud VM (Ubuntu, Ampere A1 or x86)
  Caddy :80/:443 ──┬─▶ web (Next.js :3000)
                   └─▶ backend (Flask :5000) ─▶ postgres (:5432, internal only)
  volumes: pgdata, backend_state, web_data, caddy_data, caddy_config
  host backups: /opt/aeon/backups (retention AEON_BACKUP_KEEP, default 14)
```

Caddy is retained instead of Nginx: it is already integrated, provides
automatic Let's Encrypt HTTPS, and satisfies the same reverse-proxy
requirements (proxy headers, compression, single public entrypoint).

## 5. Files that change in this migration

| File | Change |
|---|---|
| `ORACLE_MIGRATION_PLAN.md` | new — this plan |
| `scripts/backup-db.sh` | new — pg_dump to host dir with retention |
| `scripts/restore-db.sh` | new — guarded restore with confirmation |
| `.github/workflows/deploy-oracle.yml` | add pre-deploy backup + rollback on failed health gate |
| `docs/oracle-cloud-deployment.md` | new — full step-by-step runbook |
| `README.md` | Oracle-first quick start + automatic deployment section |
| `.github/workflows/railway-deploy.yml` | deleted (unused alternate host) |
| `scripts/setup-railway.sh` | deleted (unused alternate host) |

## 6. Files that remain

All application code, Alembic migrations, tests, monitoring stack, SDKs, and
the Oracle deployment scripts listed in §3. Optional Supabase/Redis/Stripe
integrations remain as code paths but are not hosting dependencies; the
platform runs fully on Oracle PostgreSQL with them unset.

## 7. Database migration strategy

- Schema owner: Alembic (`alembic/versions/*`), run automatically by
  `scripts/docker-entrypoint.sh` on backend boot; fail-closed on error.
- No destructive migrations are introduced by this plan.
- Fresh installs: empty PostgreSQL + `alembic upgrade head` + admin seed from
  `AEON_ADMIN_EMAIL`/`AEON_ADMIN_PASSWORD` (first boot only).
- Existing installs: backups before every deploy (workflow) and on demand
  (`scripts/backup-db.sh`); restore procedure tested path documented in
  `docs/oracle-cloud-deployment.md`.
- Extensions required: `uuid-ossp`, `pg_trgm`, `hstore` (already provisioned by
  `scripts/init-db.sql` in the local compose and by the OCI entrypoint).

## 8. Deployment strategy

Two redundant paths (both already wired):

1. **GitHub Actions** (`.github/workflows/deploy-oracle.yml`) on push to
   `main`: secrets `ORACLE_HOST`, `ORACLE_USER`, `ORACLE_SSH_KEY`; SSH in,
   backup, pull, rebuild, health gate, rollback on failure.
2. **VM-side auto-update timer** every 30 minutes (works without Actions
   billing): pull-only-when-changed, env self-repair, admin re-seed, health
   gate. First deploy is always `scripts/deploy-oracle.sh` over SSH.

## 9. Security strategy

- Secrets only in `/opt/aeon/.env` (chmod 600) and GitHub Actions secrets;
  never in git. `env.example` documents keys without values.
- PostgreSQL, backend, web ports internal to the Docker network; only 22/80/443
  exposed at the host and OCI Security List.
- Backend JWT secret ≥ 32 chars enforced fail-closed in production
  (`aeon_auth._resolve_jwt_secret`); dev header fallback disabled in
  production; service-to-service identity via `AEON_API_TOKEN` constant-time
  comparison.
- Admin seed password used once at first boot; rotation via
  `scripts/set-admin.sh` (Werkzeug hash, no plaintext at rest).
- CORS pinned to the public origin via `AEON_CORS_ALLOWED_ORIGINS`.

## 10. Testing strategy

- Backend: `python3 -m pytest -q tests/test_auth.py tests/test_demo_seed.py
  tests/test_health.py` (registration, duplicate email, login, fallback admin
  disabled in production, workspace isolation, tokens).
- Frontend: `npm --prefix web run build` (includes TypeScript checks).
- Scripts: `sh -n` syntax checks; scripts use `set -eu`.
- Post-deploy: `/health`, `/api/health`, registration → login → protected API
  round-trip, demo login, rollback drill (documented).

## 11. Removals performed in this migration

- `.github/workflows/railway-deploy.yml`, `scripts/setup-railway.sh`: unused
  Railway deployment path; no code or docs referenced it as required.
- Tencent CloudBase working-tree scaffolding (`cloudbaserc.json`,
  `cloudbase/`, `scripts/deploy-cloudbase.sh`,
  `TENCENT_CLOUDBASE_DEPLOYMENT.md`, `deploy:cloudbase` npm scripts, env
  template block): never committed, never deployed, no data existed. Removed
  because Oracle is the sole production target per the migration directive.
- Nothing application-functional was removed. Supabase/Redis/Stripe/Colab
  artifacts remain as optional or legacy features, not hosting.

## 12. Known limitations (honest)

- Live end-to-end verification of the running VM (HTTPS over a domain, real
  browser login) requires SSH access from the VM side; the Freebuff workspace
  has no route into the VM. All repository-side checks pass; the VM converges
  via auto-update on next pull.
- A domain is optional; without one Caddy serves plain HTTP on :80 and
  `NEXTAUTH_URL` uses the VM IP (self-repaired automatically).
