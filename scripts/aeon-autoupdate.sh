#!/usr/bin/env sh
# AEON OS — VM-side auto-updater (runs under the systemd timer below).
# Pulls latest main and redeploys the Docker stack ONLY when the commit
# changed, so idle runs cost nothing. No GitHub Actions / billing needed.
#   View logs:      journalctl -u aeon-autoupdate.service -f
#   Run once now:   sudo systemctl start aeon-autoupdate.service
set -eu

APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
BRANCH="${AEON_BRANCH:-main}"
COMPOSE_FILE="docker-compose.oci.yml"

# Never overlap with a run still in progress (timer fired mid-build).
exec 9>/run/aeon-autoupdate.lock
flock -n 9 || { echo "$(date -u +%FT%TZ) another update already running — skipping"; exit 0; }

test -d "$APP_DIR/.git" || {
    echo "ERROR: $APP_DIR is not a git checkout — run scripts/deploy-oracle.sh first"
    exit 1
}
cd "$APP_DIR"

# Self-heal .env every tick (admin login, NEXTAUTH_URL, missing secrets) so
# installs created by older bootstraps converge without manual commands.
sh scripts/aeon-env-repair.sh || true

git fetch origin "$BRANCH"
if [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$BRANCH")" ]; then
    echo "$(date -u +%FT%TZ) already up to date at $(git rev-parse --short HEAD)"
    exit 0
fi

echo "$(date -u +%FT%TZ) updating $(git rev-parse --short HEAD) -> $(git rev-parse --short "origin/$BRANCH")"
git reset --hard "origin/$BRANCH"

docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans

# Release disk from replaced images (only dangling layers are pruned).
docker image prune -f >/dev/null 2>&1 || true

# Wait for backend to be healthy before seeding users.
echo "Waiting for backend to be healthy..."
for i in $(seq 1 30); do
    if curl --fail --silent http://localhost/health | grep -q '"ok"'; then
        echo "Backend is healthy!"
        break
    fi
    sleep 3
done

# Seed the primary user into both DB and local store.
# This is idempotent — safe to run every tick.
sh scripts/seed-user.sh 'beatznlg@gmail.com' 'Niku1991!' 'nlg' || true

# Health gate: frontend API proxy + Flask kernel.
curl --fail --silent http://localhost/api/health >/dev/null && echo "frontend API OK"
curl --fail --silent http://localhost/health | grep -q '"ok"' || {
    echo "WARNING: kernel /health not OK after update — recent backend logs:"
    docker compose -f "$COMPOSE_FILE" logs --tail 50 backend || true
    exit 1
}

echo "$(date -u +%FT%TZ) AEON updated and healthy"
