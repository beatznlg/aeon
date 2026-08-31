# AEON OS — Google Cloud deployment

This is the Google Cloud deployment target for AEON OS. The first production shape uses one Compute Engine VM so the existing Docker architecture remains unchanged and portable.

## Architecture

```text
Internet
   |
Google Cloud VPC / firewall
   |
Compute Engine VM
   |
Caddy :80/:443
   +-- Next.js frontend :3000 (private)
   +-- Flask API :5000 (private)
   +-- PostgreSQL :5432 (private Docker network)
   +-- Redis :6379 (private Docker network)
   +-- Celery worker
   +-- Celery Beat
```

Only TCP 80, 443 and SSH (restricted to an administrator IP range) should be allowed by the Google Cloud firewall. Do not expose PostgreSQL, Redis, Flask or Next.js directly.

## VM baseline

For a real production workload, use a VM with enough memory for Next.js + Flask + PostgreSQL + Redis + Celery. The smallest Always Free e2-micro is suitable for smoke tests only and should not be represented as a production sizing recommendation for the complete stack.

Recommended first setup:

- Ubuntu LTS
- Docker Engine + Compose plugin
- Static external IP
- DNS A/AAAA record pointing at the VM
- Google Cloud firewall: 22 (restricted), 80, 443
- Automatic OS security updates
- Separate persistent disk for `/opt/aeon` and database volumes where practical

## First deployment

```bash
sudo mkdir -p /opt/aeon
sudo chown "$USER":"$USER" /opt/aeon
cd /opt/aeon
git clone https://github.com/beatznlg/aeon.git .
cp .env.gcp.example .env
chmod 600 .env
```

Generate strong secrets locally on the VM (do not paste examples into production):

```bash
openssl rand -hex 32
```

Use independent values for `POSTGRES_PASSWORD`, `AEON_JWT_SECRET`, `AEON_MASTER_KMS_KEY`, and `AUTH_SECRET`.

Then:

```bash
bash scripts/deploy-gcp.sh
```

## DNS and TLS

Set `AEON_DOMAIN` to the DNS name pointing at the VM. Caddy automatically obtains and renews a certificate. Confirm ports 80 and 443 are reachable before the first start.

## GitHub Actions deployment

The workflow `.github/workflows/deploy-gcp.yml` expects these repository Actions secrets:

- `GCP_HOST` — VM public IP or DNS name
- `GCP_USER` — deployment SSH user
- `GCP_SSH_KEY` — private SSH key for that deployment user

The VM must already have the repository checked out at `/opt/aeon`, Docker installed, and a production `.env` file present. The workflow never transfers secrets from GitHub into `.env`.

## Backup and recovery

Run `scripts/backup-db.sh` regularly. For serious production use, configure an off-host backup destination such as Google Cloud Storage and test restoration on a separate VM. A backup stored only on the same VM is not a disaster-recovery plan.

## Scaling path

The single-VM deployment is intentionally the simplest migration from the Oracle architecture. The next GCP-native evolution is:

```text
Cloud Load Balancer
       |
   +---+---+
   |       |
Cloud Run  Cloud Run
 frontend  API
       |
 Cloud SQL PostgreSQL
       |
 managed Redis / Memorystore
       |
 Cloud Run Jobs / dedicated worker compute
       |
 Cloud Storage
```

Do not migrate to this split architecture until the single-VM release is stable; the worker/Beat/Redis semantics must be validated first.
