# AEON OS — Google Cloud (Free Tier) Deployment Runbook

Complete, copy-paste path from a fresh Google Cloud project to a running,
auto-updating AEON OS on the **GCP Always Free tier**. The Oracle Cloud
equivalent lives in [`oracle-cloud-deployment.md`](./oracle-cloud-deployment.md);
both use the same portable Docker stack (`docker-compose.oci.yml`).

## 0. What "free" actually covers

GCP's Always Free tier includes (per month, in eligible US regions):

| Resource | Free limit |
|---|---|
| `e2-micro` VM | 1 instance, 2 vCPU (shared-core), **1 GB RAM** — `us-west1`, `us-central1`, `us-east1` |
| Persistent disk | 30 GB **standard** PD (not SSD) |
| Snapshot storage | 5 GB |
| External IP | free when attached to a running VM |
| Egress | 1 GB/month (Network egress via **Standard** tier, excluding China/Australia) |

New accounts additionally get **$300 credit / 90 days** (Free Trial), which
easily covers the build phase (the Next.js Docker build is CPU-hungry but runs
fine on the VM thanks to the 2 GB swap the bootstrap script creates).

⚠️ **Cost traps to avoid:**

- Region must be one of the three above — other regions are not always-free.
- Disk type must be **Standard persistent disk** (default), not SSD.
- External IP is free **only while the VM runs**; a stopped-but-reserved IP
  bills. Stop the VM with "release IP" if you park it.
- If you see a charge, it's almost always region, disk type, or a second VM.

## 1. Create the VM

**Console path:** Compute Engine → VM instances → Create instance

| Setting | Value |
|---|---|
| Name | `aeon` |
| Region / Zone | `us-west1` (or `us-central1` / `us-east1`) / any |
| Machine type | `e2-micro` (2 shared vCPU, 1 GB) |
| Boot disk | 30 GB, **Standard persistent disk**, Ubuntu 22.04 LTS |
| Firewall | check *Allow HTTP traffic* and *Allow HTTPS traffic* |
| Service account | default is fine |

Or with gcloud (from Cloud Shell):

```bash
gcloud compute instances create aeon \
  --zone=us-west1-a \
  --machine-type=e2-micro \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-standard \
  --tags=http-server,https-server

gcloud compute firewall-rules create aeon-http \
  --allow tcp:80,tcp:443 --direction INGRESS \
  --source-ranges 0.0.0.0/0 \
  --target-tags=http-server,https-server
```

Note the **external IP** from the instance list.

## 2. Connect and run the one-command bootstrap

```bash
gcloud compute ssh aeon --zone=us-west1-a
sh -c "$(wget -qO- https://raw.githubusercontent.com/beatznlg/aeon/main/scripts/deploy-gcp.sh)"
```

The script (idempotent — re-run any time to update to latest `main`):

1. Installs Docker + Compose v2.
2. Creates a **2 GB swapfile** — required, because e2-micro has 1 GB RAM and
   the Next.js Docker build OOMs without swap.
3. Clones the repo to `/opt/aeon`.
4. Generates strong secrets into `/opt/aeon/.env` (chmod 600).
5. Self-repairs admin seed and `NEXTAUTH_URL` (`scripts/aeon-env-repair.sh`).
6. Builds and starts the full stack (Postgres + Flask kernel + Next.js web +
   Caddy TLS proxy).
7. Installs the 30-minute auto-update timer.

First boot runs Alembic migrations (fail-closed) and seeds the admin from
`AEON_ADMIN_EMAIL` / `AEON_ADMIN_PASSWORD` (first boot only).

> **First build takes ~10–15 minutes on e2-micro.** This is normal — the
> shared-core CPU plus swap is slow but succeeds. Watch progress with
> `docker compose -f docker-compose.oci.yml logs -f` or
> `watch docker compose -f docker-compose.oci.yml ps`.

## 3. Configure `.env`

```bash
cd /opt/aeon && sudo nano .env
# apply changes:
sudo docker compose -f docker-compose.oci.yml up -d
```

| Variable | Purpose |
|---|---|
| `AEON_DOMAIN` | Your DNS name → enables automatic Let's Encrypt HTTPS. Empty = HTTP on :80. |
| `AEON_ADMIN_EMAIL` / `AEON_ADMIN_PASSWORD` | Admin seed used on first boot only. |
| `AEON_LLM_PROVIDER` | `stub` (no key needed), `openai`, `anthropic`, `google`, `mistral`, `openrouter`, `ollama`, `lmstudio`, `vllm`, `hf`, `qwen`, `custom`. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / … | Provider keys for AI features (optional). |
| `STRIPE_*` | Billing only (optional). |
| `SUPABASE_*` | Optional mirror for select features; PostgreSQL stays authoritative. |
| `AEON_STORAGE_BACKEND` | `local` (default) or `gcs` — see the storage section below. |

## 4. DNS and HTTPS

Create an `A` record (e.g. `aeon.example.com` → VM external IP), set
`AEON_DOMAIN=aeon.example.com` in `.env`, then:
`docker compose -f docker-compose.oci.yml up -d caddy`.
Certificates issue/renew automatically via Caddy. Without a domain the app
serves plain HTTP on port 80 and `NEXTAUTH_URL` is auto-set to the VM IP.

## 5. Admin account

```bash
# Reset or create the admin at any time (no restart needed):
sudo sh /opt/aeon/scripts/set-admin.sh you@example.com 'YourStrongPassword'

# Self-service: /login → Create Account
# Demo (works even if the backend is briefly down): admin@demo.local / demo123
```

## 6. Verify

```bash
curl --fail http://localhost/health            # {"ok": true, ...}
curl --fail http://localhost/api/health        # frontend → backend proxy
docker compose -f /opt/aeon/docker-compose.oci.yml ps
```

From the internet: `http://<VM_EXTERNAL_IP>` (or your HTTPS domain).

## 7. Automatic deployment from GitHub

Two redundant paths:

**A. GitHub Actions on every push to `main`** —
`.github/workflows/deploy-gcp.yml`. Add three repository secrets
(GitHub → beatznlg/aeon → Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `GCP_HOST` | VM external IP (e.g. `34.121.10.20`) |
| `GCP_USER` | SSH user (`ubuntu`) |
| `GCP_SSH_KEY` | **Private** key matching the public key on the VM (full PEM, trailing newline). Generate with `ssh-keygen -t ed25519` and add the public half to the VM. |

The workflow backs up the database, pulls, rebuilds, health-checks; on a
failed health gate it resets to the previous commit and rebuilds (rollback).

**B. VM-side auto-update timer** (works with no billing/Actions): runs every
30 minutes, deploys only when `main` moved.

```bash
systemctl list-timers aeon-autoupdate.timer
sudo systemctl start aeon-autoupdate.service   # update now
journalctl -u aeon-autoupdate.service -f       # live logs
```

## 8. Storage on GCS (optional, replaces local disk)

The app's storage layer supports Google Cloud Storage
(`AEON_STORAGE_BACKEND=gcs`). Free tier: 5 GB regional storage/month.
Requires `AEON_GCS_BUCKET` + `GOOGLE_APPLICATION_CREDENTIALS` (service
account JSON) — see `env.example`.

## 9. Backups

```bash
sudo sh /opt/aeon/scripts/backup-db.sh         # also run by CI pre-deploy
ls -lh /opt/aeon/backups
```

Archives are gzipped `pg_dump` dumps on the host. Copy off-box regularly:
`gcloud compute scp aeon:/opt/aeon/backups/*.sql.gz . --zone=us-west1-a`.

## 10. Logs, monitoring, troubleshooting

```bash
docker compose -f /opt/aeon/docker-compose.oci.yml logs -f backend
curl -s http://localhost/health/detailed | python3 -m json.tool
```

| Symptom | Cause / fix |
|---|---|
| Site times out from outside | Missing VPC firewall rule for 80/443 (§1), or the VM was created without the `http-server`/`https-server` tags. |
| Build OOM / killed during deploy | Swap missing — re-run `scripts/deploy-gcp.sh` (idempotent, adds 2 GB swap). |
| `503 /health` | Postgres not ready: `docker compose logs postgres backend`. |
| `401` everywhere | `AEON_JWT_SECRET` missing/short (≥32 chars, fail-closed in production). |
| Login loop after deploy | `NEXTAUTH_URL` ≠ public origin — env self-repair fixes on next tick. |
| Unexpected charges | Wrong region (must be `us-west1`/`us-central1`/`us-east1`), SSD disk, or a second non-e2-micro VM. |

## 11. Reboot resilience

All services use `restart: unless-stopped`; Docker starts on boot and the
auto-update timer persists. After a VM reboot the stack returns on its own.
