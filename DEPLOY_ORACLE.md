# AEON OS — Full Deployment on Oracle Cloud

Everything (frontend, kernel, database, TLS) runs on **one Oracle Cloud
Compute VM** via Docker Compose. The always-free **VM.Standard.A1.Flex**
(Ampere ARM) tier covers this stack comfortably: 4 OCPU / 24 GB RAM.

```
                    Oracle Cloud VM (Ubuntu, Ampere A1)
   ┌──────────────────────────────────────────────────────────┐
   │  Caddy :80/:443 ── auto-HTTPS ─┬─▶ web    (Next.js :3000)│
   │                                └─▶ backend (Flask  :5000) │
   │                                     └─▶ postgres (:5432)  │
   │  data persists in Docker volumes (pgdata, backend_state)  │
   └──────────────────────────────────────────────────────────┘
```

## 1. Create the VM

1. OCI Console → **Compute → Instances → Create Instance**
2. Image: **Ubuntu 22.04+** · Shape: **VM.Standard.A1.Flex** (2–4 OCPU)
3. SSH keys: add yours · Networking: public IPv4 + allow **TCP 22, 80, 443**

## 2. Point DNS (optional but recommended)

Create an `A` record for e.g. `aeon.yourdomain.com` → the VM's public IP.
Caddy then issues/renews Let's Encrypt certificates automatically. Without a
domain the site serves plain HTTP on port 80.

## 3. One command

```bash
ssh ubuntu@<VM_PUBLIC_IP>
sh -c "$(wget -qO- https://raw.githubusercontent.com/beatznlg/aeon/main/scripts/deploy-oracle.sh)"
```

The script installs Docker, generates strong secrets into `/opt/aeon/.env`,
and starts the whole stack. Then edit the env and restart:

```bash
cd /opt/aeon
nano .env            # set AEON_DOMAIN, AEON_ADMIN_EMAIL/PASSWORD, LLM keys
docker compose -f docker-compose.oci.yml up -d
```

First boot runs Alembic migrations and seeds the admin user from
`AEON_ADMIN_EMAIL` / `AEON_ADMIN_PASSWORD` (ignored on later boots).

## 4. Verify

```bash
curl http://localhost/health          # {"ok": true, ...}
curl https://aeon.yourdomain.com/api/health
```

## Environment variables (.env)

| Variable | Required | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | ✅ (auto-generated) | Postgres superuser password |
| `AUTH_SECRET` | ✅ (auto-generated) | Auth.js session signing |
| `AEON_JWT_SECRET` | ✅ (auto-generated) | Kernel JWT signing |
| `AEON_MASTER_KMS_KEY` | recommended | Encryption-at-rest master key |
| `AEON_DOMAIN` | for HTTPS | Your DNS name; empty = HTTP only |
| `AEON_ADMIN_EMAIL` / `AEON_ADMIN_PASSWORD` | first boot | Admin seed |
| `AEON_LLM_PROVIDER` | no | `stub`, `openai`, `anthropic`, … |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | if LLM ≠ stub | Provider keys |

Supabase variables (`SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_*`) are optional —
the platform falls back to its local Postgres and demo-data rendering when
they are unset, so nothing breaks by leaving them blank.

## Updating

```bash
sh scripts/deploy-oracle.sh        # re-run: pulls main, rebuilds, restarts
```

Data survives updates (named volumes). Back up with:

```bash
docker exec aeon-os-postgres-1 pg_dump -U aeon aeon > backup.sql
```
