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
`AEON_ADMIN_EMAIL` / `AEON_ADMIN_PASSWORD`. If those are empty, the **auto-update
timer and the bootstrap both self-repair `.env`**: they generate an admin login
(`admin@aeon.local` + random password), set `NEXTAUTH_URL` to the VM's public
IP, and fill any missing secrets. View the generated login with:

```bash
sudo grep AEON_ADMIN /opt/aeon/.env
```

To choose your own email/password instead:
```bash
sudo sh scripts/set-admin.sh you@example.com 'YourPassword123'
```

This creates (or resets) the ADMIN account immediately — no container restart
needed. You can also self-register at `/login` → **Create Account**, or use
the built-in demo (`admin@demo.local` / `demo123`).

Forgot your password later? Re-run `set-admin.sh` with a new password.

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

## Automatic updates — two options

### Option A (recommended, no billing required): systemd timer on the VM

The bootstrap script installs **`aeon-autoupdate.timer`** automatically: as
root it runs every 30 minutes, pulls `main`, and redeploys **only when the
commit changed** — idle ticks are no-ops. It never touches GitHub Actions or
billing.

Manage it on the VM:

```bash
docker compose -f docker-compose.oci.yml ps   # current version
systemctl list-timers aeon-autoupdate.timer   # next scheduled pull
sudo systemctl start aeon-autoupdate.service  # update now
journalctl -u aeon-autoupdate.service -f      # live logs
```

Change the cadence by editing `OnUnitActiveSec=` in
`scripts/install-autoupdate.sh` and re-running it.

### Option B: GitHub Actions on every push to `main`

Also available if billing is sorted out. Enable by adding three repository
secrets (**Settings → Secrets and variables → Actions**):

| Secret | Value |
|---|---|
| `ORACLE_HOST` | VM public IP, e.g. `138.2.153.2` |
| `ORACLE_USER` | `ubuntu` |
| `ORACLE_SSH_KEY` | The **private** key from instance launch (`-----BEGIN OPENSSH PRIVATE KEY-----…`, full file including last newline) |

Each run: opens host-firewall ports 80/443, stops any legacy systemd stack,
pulls latest `main`, rebuilds the Compose stack, and fails the run if health
checks don't pass.

> While Option A is active you can leave these unset — the VM keeps itself up
> to date without them.

## Troubleshooting

| Symptom | Meaning / fix |
|---|---|
| Browser: *took too long to respond* | Packets dropped: check OCI **Security List + NSG on the VNIC** allow TCP 80/443 (0.0.0.0/0), then host firewall — both are auto-fixed by deploy-oracle.sh and by each workflow run |
| Workflow shows billing/payment error | GitHub refused to start the job — fix payment method / spending limit in Billing settings, or just rely on Option A |
| Page loads but `/health` = 502 | Caddy is up but the Flask kernel isn't reachable — run the workflow (or `sh scripts/deploy-oracle.sh`) to rebuild; kernel container may have crashed: `docker compose -f docker-compose.oci.yml logs backend` |
| Deploy workflow fails in ~5 s | Missing repo secret — see table above |
| Port 80 already in use during compose up | A legacy native install holds it; the scripts stop it automatically, or manually: `sudo systemctl disable --now aeon-backend aeon-web caddy` |
| Login page loads but data calls fail | Expected with `AEON_LLM_PROVIDER=stub` only for AI features; other errors → backend logs above |
| *Sign-in failed. Check your credentials.* | No admin exists yet — wait for the auto-update tick (it creates one, then `sudo grep AEON_ADMIN /opt/aeon/.env`), or run `sudo sh scripts/set-admin.sh <email> '<password>'`, or use `admin@demo.local` / `demo123` |

## Updating

```bash
sh scripts/deploy-oracle.sh        # re-run: pulls main, rebuilds, restarts
```

Data survives updates (named volumes). Back up with:

```bash
docker exec aeon-os-postgres-1 pg_dump -U aeon aeon > backup.sql
```
