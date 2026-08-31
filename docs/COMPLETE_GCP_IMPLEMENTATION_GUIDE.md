# AEON OS — Complete Google Cloud Implementation & User Guide

> Canonical deployment and operating guide. AEON OS production infrastructure is Google Cloud. GitHub is source control and CI/CD.

## 1. Scope

This guide covers the complete lifecycle:

1. Google Cloud project creation
2. Required APIs and IAM
3. Compute Engine deployment
4. Docker/Compose installation
5. PostgreSQL, Redis, Flask, Next.js, Celery and Caddy
6. DNS and HTTPS
7. Secrets
8. Authentication and demo mode
9. GitHub automatic deployment
10. Backups and restore
11. Monitoring and health checks
12. Security hardening
13. Company onboarding
14. Agents and assistants
15. Knowledge bases
16. Workflows
17. Integrations and model providers
18. Troubleshooting
19. Release/rollback procedure
20. Production acceptance testing

## 2. Google Cloud architecture

```text
                         GitHub
                           |
                    source + CI/CD
                           |
                           v
                  Google Cloud project
                           |
                 +---------+---------+
                 |                   |
          Artifact Registry     Secret Manager
                 |                   |
                 +---------+---------+
                           |
                           v
                   Compute Engine VM
                           |
                        Caddy
                    HTTPS :443/:80
                           |
             +-------------+-------------+
             |                           |
          Next.js                     Flask API
          frontend                       |
                                  +------+------+
                                  |             |
                             PostgreSQL       Redis
                                  |             |
                                  |        Celery Worker
                                  |             |
                                  |        Celery Beat
                                  |
                           persistent disk
                                  |
                           Cloud Storage
                           off-host backups
```

The initial deployment uses one VM because it preserves AEON's existing container architecture. Google Cloud supports storing Docker images in Artifact Registry and allowing Compute Engine to pull them with the VM service account. citeturn0search1turn0search7

## 3. Free-tier reality

Google Cloud currently advertises an Always Free Compute Engine allowance of one e2-micro VM, up to 30 GB standard persistent disk and up to 1 GB/month outbound data transfer for eligible usage. New customers also receive $300 of trial credit for 90 days. citeturn0search3turn0search13

The e2-micro is **not a recommended production size for the full AEON stack**. Next.js, Flask, PostgreSQL, Redis and Celery can exhaust 1 GB RAM. Use the free VM for development/smoke testing or use the trial credit for a larger VM while validating the application.

Cloud Build currently provides 2,500 free build-minutes/month for all customers, subject to Google's terms and limits. citeturn0search4

## 4. Create the project

In Google Cloud Console:

1. Create a project.
2. Attach billing if required by the selected services/free-trial eligibility.
3. Record `PROJECT_ID`.
4. Choose one region and keep compute, registry and storage close together where practical.

Enable the required APIs:

```bash
gcloud services enable \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com
```

Cloud Build integrates with GitHub and can build/test/deploy from repository changes. citeturn0search6turn0search8

## 5. Artifact Registry

Create a Docker repository:

```bash
gcloud artifacts repositories create aeon \
  --repository-format=docker \
  --location=REGION
```

Configure Docker authentication:

```bash
gcloud auth configure-docker REGION-docker.pkg.dev
```

Use immutable commit-based image tags such as `$COMMIT_SHA`. Artifact Registry is Google's recommended location for container artifacts and supports vulnerability scanning and IAM controls. citeturn0search7turn0search12

## 6. VM creation

Recommended starting point for a real evaluation:

- Ubuntu LTS
- x86_64
- 2+ vCPU
- 8+ GB RAM if running the complete stack together
- 30–50+ GB persistent disk
- static external IP
- automatic security updates

For a strict free smoke test, use the eligible e2-micro but expect severe resource limits.

Firewall:

- TCP 80 — public
- TCP 443 — public
- TCP 22 — restricted to administrator IPs

Never expose 3000, 5000, 5432 or 6379 publicly.

## 7. Install Docker

```bash
sudo apt update
sudo apt upgrade -y
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
```

Reconnect and verify:

```bash
docker --version
docker compose version
```

## 8. Application installation

```bash
sudo mkdir -p /opt/aeon
sudo chown -R "$USER":"$USER" /opt/aeon
cd /opt/aeon
git clone https://github.com/beatznlg/aeon.git .
```

Create the production environment from `.env.gcp.example` and set unique secrets.

Never commit `.env`.

## 9. Secrets

Required production secrets must be stored outside Git:

- database password
- JWT secret
- application master key
- authentication secret
- model/provider API keys
- integration credentials

Prefer Google Secret Manager for centralized production secrets. Google documents Secret Manager as a secure store for API keys, passwords and certificates. citeturn0search3

For the first VM-based deployment, a root-owned `0600` environment file is acceptable while migrating to Secret Manager.

## 10. Start AEON

Validate the Compose configuration first:

```bash
docker compose -f docker-compose.gcp.yml config
```

Then:

```bash
bash scripts/deploy-gcp.sh
```

Verify:

```bash
docker compose -f docker-compose.gcp.yml ps
curl -f http://127.0.0.1/health
curl -f http://127.0.0.1/api/health
```

## 11. DNS and HTTPS

Create an A record:

```text
app.example.com -> STATIC_VM_IP
```

Set:

```text
AEON_DOMAIN=app.example.com
NEXTAUTH_URL=https://app.example.com
NEXT_PUBLIC_APP_URL=https://app.example.com
AEON_CORS_ALLOWED_ORIGINS=https://app.example.com
```

Caddy handles HTTPS certificates and renewal.

## 12. Authentication

### Registration

1. Open `/register`.
2. Enter name, email and password.
3. Submit.
4. Confirm the account can log in.

### Login

1. Open `/login`.
2. Enter credentials.
3. Verify the authenticated dashboard loads.
4. Verify logout invalidates the application session.

### Demo

Demo mode is opt-in. Recommended production setting:

```text
AEON_DEMO_ENABLED=false
```

Only enable it when a controlled demonstration is required, and use a unique strong password supplied through the deployment environment.

## 13. First company setup

1. Create the first administrator.
2. Create the company/workspace.
3. Invite team members.
4. Define roles.
5. Configure AI providers.
6. Create the first knowledge base.
7. Upload authoritative documents.
8. Create the first assistant.
9. Create one workflow.
10. Test with non-production data.
11. Enable production actions only after approval.

## 14. Agents

Every production agent should define:

- business purpose
- target users
- model/provider
- system instructions
- knowledge sources
- allowed tools
- input requirements
- output requirements
- escalation rules
- human approval requirements

Avoid agents with unrestricted destructive or financial actions.

## 15. Knowledge bases

Recommended process:

```text
Collect authoritative files
        |
Remove obsolete copies
        |
Upload
        |
Ingest/index
        |
Test representative questions
        |
Review answers
        |
Assign knowledge owner
```

Keep a documented owner for every production knowledge collection.

## 16. Workflows

A workflow should be explicit and observable:

```text
Trigger
  -> classify
  -> retrieve knowledge
  -> AI processing
  -> validation
  -> human approval (when required)
  -> action
  -> audit/log
```

Test every branch, including failure and retry behavior.

## 17. Company implementation patterns

### Technology
Support automation, engineering assistants, incident knowledge, documentation and release workflows.

### Finance/accounting
Policy retrieval, reporting, document workflows and approval processes. Keep sensitive financial actions behind authorization.

### Legal
Matter knowledge, document research and controlled drafting. Require human review for legal conclusions or external actions.

### Healthcare/life sciences
Administrative and research workflows. Apply organization-specific privacy, security and regulatory controls before handling regulated data.

### Retail/e-commerce
Customer support, product knowledge, marketing workflows and operational automation.

### Manufacturing/logistics
SOP assistants, maintenance knowledge, quality workflows and supply-chain reporting.

### Hospitality/restaurants
Operations assistant, SOP knowledge, staff workflows, customer support and marketing automation.

### Education
Course knowledge, research assistants, administration and student-support workflows.

### Agencies/media
Separate client workspaces, research, content workflows and approval pipelines.

## 18. Benefits

- One AI operating layer for assistants, workflows and knowledge.
- Provider/model flexibility.
- Company-controlled knowledge retrieval.
- Repeatable workflow automation.
- Multi-tenant workspace model.
- Background processing through Celery.
- Operational visibility.
- Self-hosted Google Cloud runtime.
- Portable Docker architecture.
- GitHub-based version control and automated delivery.

## 19. CI/CD

Preferred production flow:

```text
Developer
   |
 git push
   v
GitHub
   |
Cloud Build trigger
   |
Lint + type check + tests + security
   |
Docker build
   |
Artifact Registry
   |
Deployment
   |
Health/readiness verification
   |
PASS -> live
FAIL -> stop/rollback
```

Google documents GitHub-triggered Cloud Build workflows and Artifact Registry integration. citeturn0search5turn0search6

Cloud Build can build images, push them to Artifact Registry and automate deployment. citeturn0search2

## 20. Backups

Back up PostgreSQL to Google Cloud Storage, not only to the VM's local disk.

Minimum policy:

- daily backup
- weekly retained backup
- encrypted bucket
- restricted service account
- lifecycle/retention policy
- monthly restore test

A backup that has never been restored is not proven recoverable.

## 21. Monitoring

Monitor:

- frontend HTTP status
- API health/readiness
- CPU/RAM/disk
- PostgreSQL connections and disk
- Redis connectivity
- Celery queue depth
- worker failures
- scheduled-job failures
- backup success
- authentication failures
- application exceptions

## 22. Security baseline

- HTTPS only for application traffic.
- Restrict SSH by source IP.
- Do not expose databases.
- Use least-privilege IAM.
- Use dedicated service accounts.
- Use Artifact Registry Reader for the VM when it only needs to pull images. Google documents this role for Compute Engine image pulls. citeturn0search1
- Rotate secrets.
- Keep production secrets out of Git.
- Patch the OS.
- Review container vulnerabilities.
- Test authentication and authorization.
- Maintain an incident/rollback procedure.

## 23. Release acceptance checklist

A release is production-ready only when all are green:

- [ ] frontend production build
- [ ] TypeScript checks
- [ ] Python tests
- [ ] security tests
- [ ] Docker builds
- [ ] Compose validation
- [ ] PostgreSQL migrations
- [ ] API health
- [ ] readiness
- [ ] login
- [ ] registration
- [ ] logout
- [ ] permissions
- [ ] demo mode when enabled
- [ ] Redis
- [ ] Celery worker
- [ ] Celery Beat
- [ ] knowledge ingestion
- [ ] representative workflow
- [ ] backups
- [ ] restore test
- [ ] HTTPS
- [ ] DNS
- [ ] rollback

## 24. Troubleshooting

### UI cannot reach API

Check `NEXT_PUBLIC_APP_URL`, CORS, Caddy routing and API health.

### Login fails

Check authentication secret configuration, database connectivity, session configuration and server logs.

### Workers are stuck

Check Redis and Celery worker logs:

```bash
docker compose -f docker-compose.gcp.yml logs --tail=200 redis worker beat
```

### Database errors

```bash
docker compose -f docker-compose.gcp.yml logs --tail=200 postgres backend
```

### HTTPS fails

Verify DNS points to the VM, ports 80/443 are allowed and `AEON_DOMAIN` is correct.

### Deployment fails

Do not repeatedly redeploy. Capture the failing logs, preserve the previous working image/revision, fix the cause, then rerun the production gate.

## 25. Google Cloud-only policy

The AEON application runtime must not depend on Vercel, Render, Railway, Supabase or Oracle Cloud.

External third-party AI providers may still be configured as model providers when required by the product; this does not make them application hosting platforms.

## 26. Production philosophy

A successful build is not a successful production deployment. AEON is considered ready only after the target Google Cloud environment passes functional, security, operational and recovery checks.
