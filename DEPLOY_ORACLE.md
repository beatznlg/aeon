# AEON OS — Full Deployment on Oracle Cloud

Everything required for the AEON application runtime is self-hosted on **one Oracle Cloud Compute VM** via Docker Compose: Next.js, Flask, PostgreSQL, Redis, Celery worker, Celery Beat and Caddy.

```text
                    Oracle Cloud VM (Ubuntu, Ampere A1)
   ┌─────────────────────────────────────────────────────────────┐
   │ Caddy :80/:443 ── auto-HTTPS ──▶ web (Next.js :3000)       │
   │                         └──────▶ backend (Flask :5000)      │
   │                                      │                     │
   │                           ┌──────────┴──────────┐          │
   │                           ▼                     ▼          │
   │                      PostgreSQL              Redis         │
   │                                                 │          │
   │                                      Celery worker + Beat  │
   │                                                             │
   │ Persistent Docker volumes: database, state, Redis, web,    │
   │ and Caddy certificates/configuration.                      │
   └─────────────────────────────────────────────────────────────┘
```

## 1. Create the VM

1. OCI Console → **Compute → Instances → Create Instance**
2. Ubuntu 22.04+ · Shape `VM.Standard.A1.Flex` (2–4 OCPU is a sensible starting point)
3. Add your SSH key.
4. Allow inbound TCP **22, 80, 443** in the OCI Security List/NSG. Do not expose PostgreSQL or Redis publicly.

## 2. Point DNS

Create an `A` record such as `aeon.yourdomain.com` → the VM public IP. Set `AEON_DOMAIN` and `NEXTAUTH_URL` to the HTTPS URL before customer traffic. Caddy automatically obtains and renews the certificate.

## 3. Bootstrap

```bash
ssh ubuntu@<VM_PUBLIC_IP>
sh -c "$(wget -qO- https://raw.githubusercontent.com/beatznlg/aeon/main/scripts/deploy-oracle.sh)"
```

The bootstrap installs Docker, creates `/opt/aeon/.env` with independent secrets, repairs required configuration, and starts the complete stack.

For a domain deployment, set at minimum:

```bash
cd /opt/aeon
nano .env
# AEON_DOMAIN=aeon.yourdomain.com
# NEXTAUTH_URL=https://aeon.yourdomain.com
# AEON_CORS_ALLOWED_ORIGINS=https://aeon.yourdomain.com
# AEON_LLM_PROVIDER=openai
# OPENAI_API_KEY=...
docker compose -f docker-compose.oci.yml up -d --build
```

If no admin credentials are supplied, `aeon-env-repair.sh` creates `admin@aeon.local` with a random password. **Save it securely and rotate it after first login.** Never commit the generated `.env`.

To choose an admin account explicitly:

```bash
sudo sh scripts/set-admin.sh you@example.com 'A-unique-strong-password'
```

## 4. Verify the full stack

```bash
cd /opt/aeon
docker compose -f docker-compose.oci.yml ps
curl http://localhost/health
curl http://localhost/api/health
```

All of these services must be running:

- `postgres`
- `redis`
- `backend`
- `worker`
- `beat`
- `web`
- `caddy`

## 5. Oracle-only runtime rules

- Vercel is **not required** for frontend hosting.
- Supabase is **not required** for application persistence/authentication.
- Railway/Render are **not required** for backend/workers.
- PostgreSQL and Redis remain inside the Docker network.
- Only Caddy is publicly exposed on ports 80/443; SSH is handled at the OCI/network layer.
- External APIs such as OpenAI, Anthropic, Stripe, email providers and third-party integrations may still be used when explicitly configured; these are dependencies, not hosting platforms.

## 6. Automatic updates

The VM can run `aeon-autoupdate.timer` every 30 minutes. It pulls `main` and redeploys when the commit changes.

```bash
systemctl list-timers aeon-autoupdate.timer
sudo systemctl start aeon-autoupdate.service
journalctl -u aeon-autoupdate.service -f
```

GitHub Actions can also deploy on every push when `ORACLE_HOST`, `ORACLE_USER` and `ORACLE_SSH_KEY` repository secrets are configured. The workflow backs up the database, rebuilds the stack and verifies all seven services before declaring success.

## 7. Backups

Local backups are not a complete disaster-recovery strategy. At minimum, run:

```bash
sudo sh /opt/aeon/scripts/backup-db.sh
```

For production, copy verified backups to an **independent Oracle Object Storage bucket** and test restoration regularly. The VM itself is a single failure domain.

## 8. Security requirements

Before accepting real customer traffic:

- Use HTTPS with a real domain.
- Keep `.env` at mode `600`.
- Rotate the bootstrap admin password.
- Keep Postgres and Redis private.
- Use unique independent secrets for Auth.js, JWT, API authentication and encryption.
- Configure rate limits.
- Configure Stripe webhook signing when billing is enabled.
- Review audit logs and AI execution ledger.
- Verify backup and restore on a clean environment.
- Run CI security gates before release.

## 9. Troubleshooting

| Symptom | Check |
|---|---|
| Browser timeout | OCI Security List/NSG and host firewall allow 80/443 |
| `/health` 502 | `docker compose -f docker-compose.oci.yml logs backend` |
| Worker not running | `docker compose -f docker-compose.oci.yml logs worker` |
| Scheduled automations not running | Check `beat`, `worker`, Redis and automation schedule state |
| Redis unavailable | `docker compose -f docker-compose.oci.yml logs redis` |
| Login problems | Verify `AUTH_SECRET`, `NEXTAUTH_URL`, admin account and CORS configuration |
| TLS not issued | DNS A record must point to the VM and TCP 80/443 must be reachable |
| Migration failure | Inspect backend logs; migrations are intentionally fail-closed |

## 10. Updating

```bash
cd /opt/aeon
sh scripts/deploy-oracle.sh
```

Named volumes preserve application data across normal rebuilds. Always take a verified database backup before schema-changing releases.
