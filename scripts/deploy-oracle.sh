#!/usr/bin/env sh
# AEON OS — one-command bootstrap for a fresh Oracle Cloud VM
# ============================================================
# Run ON the VM (Ubuntu 22.04+/Debian 12, ARM Ampere A1 or x86):
#   sh scripts/deploy-oracle.sh https://github.com/beatznlg/aeon.git
#
# Installs Docker, generates secrets, writes .env, and starts the full
# stack (Postgres + Flask kernel + Next.js web + Caddy TLS). Re-run any
# time to update to the latest main branch — data lives in named volumes.

set -eu

REPO_URL="${1:-https://github.com/beatznlg/aeon.git}"
APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
BRANCH="${AEON_BRANCH:-main}"

echo "=== AEON OS — Oracle Cloud bootstrap ==="

# ── Docker ──────────────────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 required"; exit 1; }

# ── Code ────────────────────────────────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" fetch origin "$BRANCH"
    git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
    git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# ── Secrets (.env created once, preserved across updates) ──────────────────
if [ ! -f .env ]; then
    echo "Generating production secrets..."
    POSTGRES_PASSWORD="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 32)"
    AUTH_SECRET="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 48)"
    JWT_SECRET="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 48)"
    cat > .env <<EOF
# AEON OS production secrets (generated $(date -u +%Y-%m-%dT%H:%M:%SZ))
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
AUTH_SECRET=$AUTH_SECRET
AEON_JWT_SECRET=$JWT_SECRET
AEON_MASTER_KMS_KEY=$JWT_SECRET

# Point at your DNS name (A record -> this VM's public IP) for HTTPS.
# Until then Caddy serves plain HTTP on :80.
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
    echo ".env written — edit it to set AEON_DOMAIN and admin credentials."
fi

# ── Firewall note + launch ──────────────────────────────────────────────────
echo ""
echo "NOTE: ensure OCI Security List / NSG allows ingress TCP 80 and 443."
echo "Starting stack..."
docker compose -f docker-compose.oci.yml up -d --build

echo ""
echo "=== Done. Check status:  docker compose -f docker-compose.oci.yml ps"
echo "Kernel health:           curl http://localhost/health"
