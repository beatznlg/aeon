# AEON OS — Oracle Cloud Deployment Runbook

Complete, copy-paste path from a fresh Oracle Cloud VM to a running,
auto-updating AEON OS. The shorter overview lives in
[`DEPLOY_ORACLE.md`](../DEPLOY_ORACLE.md); this is the full manual.
The migration rationale is in [`../ORACLE_MIGRATION_PLAN.md`](../ORACLE_MIGRATION_PLAN.md).

## 0. Architecture produced by these steps

```text
GitHub (main) ──push──▶ GitHub Actions ──ssh──▶ Oracle VM
                                                │  backup → pull → build → health gate → (rollback on failure)
                                                ▼
        Caddy :80/:443 (auto-HTTPS with a domain)
             ├──▶ web  (Next.js :3000)   internal
             └──▶ backend (Flask :5000)  internal
                      └──▶ postgres (:5432) internal only
        Volumes: pgdata · backend_state · web_data · caddy_data · caddy_config
        Host backups: /opt/aeon/backups (retention AEON_BACKUP_KEEP=14)
```

## 1. Create the Oracle VM

1. OCI Console → **Compute → Instances → Create Instance**.
2. Image: **Ubuntu 22.04+**. Shape: `VM.Standard.A1.Flex` (2–4 OCPU, Ampere
   always-free) or any x86 shape with ≥ 2 OCPU / 8 GB RAM.
3. Add your SSH public key. Note the **public IP**.
4. Networking: ensure the VCN Security List / NSG allows inbound
   **TCP 22, 80, 443** (and nothing else from 0.0.0.0/0).

## 2. Connect and run the one-command bootstrap

```bash
ssh ubuntu@<VM_PUBLIC_IP>
sh -c "$(wget -qO- https://raw.githubusercontent.com/beatznlg/aeon/main/scripts/deploy-oracle.sh)"
```

The script: installs Docker + Compose, opens host ports 80/443 in iptables/ufw
(before the default REJECT rule), clones the repo to `/opt/aeon`, generates
strong secrets into `/opt/aeon/.env` (chmod 600), self-repairs admin seed and
`NEXTAUTH_URL`, builds and starts the full stack, and installs the
30-minute auto-update timer.

First boot runs Alembic migrations (fail-closed) and seeds the admin from
`AEON_ADMIN_EMAIL` / `AEON_ADMIN_PASSWORD` (first boot only; ignored later).

## 3. Configure `.env`

```bash
cd /opt/aeon
sudo nano .env
```

| Variable | Purpose |
|---|---|
| `AEON_DOMAIN` | Your DNS name → enables automatic Let's Encrypt HTTPS. Empty = HTTP on :80. |
| `AEON_ADMIN_EMAIL` / `AEON_ADMIN_PASSWORD` | Admin seed used on first boot only. |
| `AEON_LLM_PROVIDER` | `stub` (no key needed), `openai`, `anthropic`, `google`, `mistral`, `openrouter`, `ollama`, `lmstudio`, `vllm`, `hf`, `qwen`, `custom`. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / … | Provider keys for AI features (optional). |
| `STRIPE_*` | Billing only (optional). |
| `SUPABASE_*` | Optional mirror for select features; PostgreSQL stays authoritative. |

Apply changes: `sudo docker compose -f docker-compose.oci.yml up -d`.

## 4. DNS and HTTPS

Create an `A` record (e.g. `aeon.example.com` → VM public IP), set
`AEON_DOMAIN=aeon.example.com` in `.env`, then restart Caddy:
`docker compose -f docker-compose.oci.yml up -d caddy`. Certificates are
issued/renewed automatically. Without a domain the app serves plain HTTP on
port 80 and `NEXTAUTH_URL` is auto-set to the VM IP.

## 5. Admin account and demo account

```bash
# Reset or create the admin at any time (no restart needed):
sudo sh /opt/aeon/scripts/set-admin.sh you@example.com 'YourStrongPassword'

# Self-service: /login → Create Account
# Demo (works even if the backend is briefly down): admin@demo.local / demo123
```

Registration persists in PostgreSQL (users, personal workspace, ADMIN
membership). The web→backend identity bridge uses the shared `AEON_API_TOKEN`
that both containers receive from `.env`; the VM self-repair re-seeds the
configured admin every auto-update tick, idempotently.

## 6. Verify

```bash
curl --fail http://localhost/health            # {"ok": true, ...}
curl --fail http://localhost/api/health        # frontend → backend proxy
curl --fail http://localhost/ready
docker compose -f /opt/aeon/docker-compose.oci.yml ps
```

From the internet: `http://<VM_PUBLIC_IP>` (or your HTTPS domain). If it times
out, check §12 (firewall) before anything else.

## 7. Automatic deployment from GitHub

Two redundant paths:

**A. GitHub Actions on every push to `main`** —
`.github/workflows/deploy-oracle.yml`. Add three repository secrets
(Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `ORACLE_HOST` | VM public IP |
| `ORACLE_USER` | `ubuntu` |
| `ORACLE_SSH_KEY` | **Private** key from instance launch (full PEM, including trailing newline) |

The workflow backs up the database, pulls, rebuilds, and health-checks; on a
failed health gate it resets to the previous commit, rebuilds, re-verifies
(rollback), and fails the run.

**B. VM-side auto-update timer** (works with no billing/Actions): runs every
30 minutes, deploys only when `main` moved.

```bash
systemctl list-timers aeon-autoupdate.timer
sudo systemctl start aeon-autoupdate.service   # update now
journalctl -u aeon-autoupdate.service -f       # live logs
```

## 8. Updating AEON manually

```bash
cd /opt/aeon && sudo sh scripts/deploy-oracle.sh   # pull + rebuild + restart
```

## 9. Backups and restore

```bash
sudo sh /opt/aeon/scripts/backup-db.sh                    # now (also run by CI pre-deploy)
sudo AEON_BACKUP_KEEP=30 sh /opt/aeon/scripts/backup-db.sh  # custom retention
ls -lh /opt/aeon/backups
```

Archives are gzipped `pg_dump --clean --if-exists` dumps stored on the host at
`/opt/aeon/backups` (outside all containers). Copy them off-box regularly
(e.g. `scp ubuntu@<ip>:/opt/aeon/backups/*.sql.gz .`).

Restore (stops backend/web, imports, restarts):

```bash
sudo sh /opt/aeon/scripts/restore-db.sh /opt/aeon/backups/aeon-YYYYmmdd-HHMMSS.sql.gz
# non-interactive (CI): sudo AEON_FORCE_RESTORE=1 sh scripts/restore-db.sh <file>
```

## 10. Rollback a bad deployment

Automatic: the Actions workflow rolls back to the previous commit when the
health gate fails. Manual:

```bash
cd /opt/aeon
git fetch origin main
git reset --hard <previous-good-sha>
docker compose -f docker-compose.oci.yml up -d --build --remove-orphans
```

If the database schema moved forward irreversibly, restore the pre-deploy
backup (§9) created automatically before the bad deploy.

## 11. Logs and monitoring

```bash
docker compose -f /opt/aeon/docker-compose.oci.yml logs -f backend
docker compose -f /opt/aeon/docker-compose.oci.yml logs -f web
docker compose -f /opt/aeon/docker-compose.oci.yml logs -f caddy
curl -s http://localhost/health/detailed | python3 -m json.tool
curl -s http://localhost/metrics | head        # Prometheus format
```

Optional full observability stack (Prometheus/Grafana/Alertmanager) ships in
`monitoring/` and composes alongside the OCI stack.

## 12. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Site times out from outside | OCI Security List lacks 80/443, **or** host iptables REJECT rule fires first — rerun `scripts/deploy-oracle.sh` (idempotent) which inserts ACCEPT before REJECT. |
| `503 /health` | Postgres not ready / wrong `POSTGRES_PASSWORD`: `docker compose logs postgres backend`. |
| `401` everywhere | `AEON_JWT_SECRET` missing/short (≥32 chars, fail-closed in production). |
| Login fails after deploy | `AUTH_SECRET` changed (sessions invalidated), or `NEXTAUTH_URL` ≠ public origin. Env self-repair fixes both on next auto-update tick. |
| Registration 500 | Migrations failed on boot — `docker compose logs backend`, fix, restart; fail-closed by design. |
| CORS errors | Set `AEON_CORS_ALLOWED_ORIGINS` to the exact public origin. |
| Certificate not issued | DNS A record must point at the VM and ports 80/443 open. |
| Disk pressure | `docker image prune -f`; auto-update already prunes dangling layers. |

## 13. Reboot resilience

All services use `restart: unless-stopped`; Docker starts on boot, and the
auto-update timer persists (`Persistent=true`). After a VM reboot the stack
comes back on its own — verify with `docker compose ps` and `/health`.
