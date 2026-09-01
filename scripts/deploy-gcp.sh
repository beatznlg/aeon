#!/usr/bin/env sh
# AEON OS — Google Cloud bootstrap / deploy script
# =====================================================
# Fresh VM bootstrap (installs Docker + swap, clones repo, starts stack):
#   sh scripts/deploy-gcp.sh https://github.com/beatznlg/aeon.git
#
# Existing checkout (pull latest main, backup DB, rebuild, health gate):
#   cd /opt/aeon && bash scripts/deploy-gcp.sh
#
# Stack: docker-compose.gcp.yml
# (postgres, redis, backend, web, worker, beat, caddy)

set -eu

REPO_URL="${1:-https://github.com/beatznlg/aeon.git}"
APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
BRANCH="${AEON_BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.gcp.yml}"
BACKUP_KEEP="${AEON_BACKUP_KEEP:-14}"

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

echo "=== AEON OS — Google Cloud deployment ==="

# ── Fresh VM: install Docker + swap ────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 required" >&2; exit 1; }

if [ "$(id -u)" != "0" ] && ! swapon --show 2>/dev/null | grep -q '/swapfile'; then
  echo "Creating 2G swapfile (small VMs OOM during the Next.js build without it)..."
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  sudo sysctl -w vm.swappiness=10 >/dev/null
  echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-aeon-swap.conf >/dev/null
fi

# ── Code ────────────────────────────────────────────────────────────────
if [ ! -d "$APP_DIR/.git" ]; then
  echo "Cloning repository..."
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# ── Secrets (.env created once, preserved across updates) ───────────────
if [ ! -f .env ]; then
  echo "Generating production secrets..."
  POSTGRES_PASSWORD="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 32)"
  AUTH_SECRET="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 48)"
  JWT_SECRET="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 48)"
  API_TOKEN="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 48)"
  cat > .env <<EOF
# AEON OS production secrets (generated $(date -u +%Y-%m-%dT%H:%M:%SZ))
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
AUTH_SECRET=$AUTH_SECRET
AEON_JWT_SECRET=$JWT_SECRET
AEON_API_TOKEN=$API_TOKEN
AEON_MASTER_KMS_KEY=$JWT_SECRET

# Public DNS name (A record -> this VM's public IP) for HTTPS via Caddy.
AEON_DOMAIN=

# First-boot admin seed (ignored if the user already exists).
AEON_ADMIN_EMAIL=
AEON_ADMIN_PASSWORD=
AEON_ADMIN_NAME=Admin

# LLM provider: stub | openai | anthropic | google | mistral | openrouter ...
AEON_LLM_PROVIDER=stub
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
EOF
  chmod 600 .env
fi

# Required variable gate (fail fast before touching the running stack)
for key in POSTGRES_PASSWORD AEON_JWT_SECRET AEON_MASTER_KMS_KEY AUTH_SECRET NEXTAUTH_URL NEXT_PUBLIC_APP_URL AEON_CORS_ALLOWED_ORIGINS AEON_DOMAIN; do
  grep -Eq "^${key}=.+" .env || echo "::warning::recommended .env variable missing or empty: $key"
done

# Self-heal .env (admin login, NEXTAUTH_URL) when the helper exists
if [ -f scripts/aeon-env-repair.sh ]; then
  sh scripts/aeon-env-repair.sh || true
fi

# ── Backup DB, then pull latest main ────────────────────────────────────
PREV_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
if [ -f scripts/backup-db.sh ]; then
  sudo AEON_BACKUP_KEEP="$BACKUP_KEEP" sh scripts/backup-db.sh \
    || echo "Backup skipped (first deploy or stack not running yet)."
fi
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

# ── Build and start the stack ───────────────────────────────────────────
compose config >/dev/null
compose up -d --build --remove-orphans
compose ps

# ── Service liveness gate ───────────────────────────────────────────────
for svc in postgres redis backend web worker beat caddy; do
  id="$(compose ps --status running -q "$svc" 2>/dev/null || true)"
  if [ -z "$id" ]; then
    echo "::error::Service '$svc' is not running" >&2
    compose logs --tail 100 "$svc" || true
    exit 1
  fi
done

# ── Health gate (auto-rollback on failure) ──────────────────────────────
i=0
while [ "$i" -lt 30 ]; do
  if curl -fsS http://localhost/health 2>/dev/null | grep -q '"ok"'; then
    curl -fsS http://localhost/api/health >/dev/null 2>&1 || true
    echo ""
    echo "=== AEON OS is healthy on Google Cloud. ==="
    [ -f "$APP_DIR/.env" ] && {
      _email=$(sed -n 's/^AEON_ADMIN_EMAIL=//p' "$APP_DIR/.env" | head -1)
      _pass=$(sed -n 's/^AEON_ADMIN_PASSWORD=//p' "$APP_DIR/.env" | head -1)
      [ -n "$_email" ] && echo "Admin login: $_email / $_pass"
    }
    echo "Status:   docker compose -f $COMPOSE_FILE ps"
    echo "Health:   curl http://localhost/health"
    exit 0
  fi
  i=$((i + 1))
  sleep 5
done

echo "::error::Health gate failed — rolling back to $PREV_SHA" >&2
if [ -n "$PREV_SHA" ]; then
  git reset --hard "$PREV_SHA"
  compose up -d --build --remove-orphans
  sleep 10
  if curl -fsS http://localhost/health 2>/dev/null | grep -q '"ok"'; then
    echo "Rollback to $PREV_SHA succeeded — site remains on the previous healthy version."
  else
    echo "::error::Rollback also unhealthy — check: docker compose -f $COMPOSE_FILE logs --tail 50 backend" >&2
    compose logs --tail 50 backend || true
  fi
fi
exit 1
