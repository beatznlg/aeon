#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/aeon}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.gcp.yml}"
BACKUP_KEEP="${AEON_BACKUP_KEEP:-14}"

cd "$APP_DIR"

echo "== AEON OS Google Cloud deployment =="
test -f "$COMPOSE_FILE" || { echo "Missing $COMPOSE_FILE" >&2; exit 1; }
test -f .env || { echo "Missing $APP_DIR/.env" >&2; exit 1; }

required=(POSTGRES_PASSWORD AEON_JWT_SECRET AEON_MASTER_KMS_KEY AUTH_SECRET NEXTAUTH_URL NEXT_PUBLIC_APP_URL AEON_CORS_ALLOWED_ORIGINS AEON_DOMAIN)
for key in "${required[@]}"; do
  grep -Eq "^${key}=.+" .env || { echo "Missing required .env variable: $key" >&2; exit 1; }
done

PREV_SHA="$(git rev-parse HEAD 2>/dev/null || true)"

if command -v docker >/dev/null 2>&1; then
  sudo -n true 2>/dev/null || true
fi

sudo AEON_BACKUP_KEEP="$BACKUP_KEEP" sh scripts/backup-db.sh || echo "Backup skipped: database stack may not exist yet."

git fetch origin main
git reset --hard origin/main

docker compose -f "$COMPOSE_FILE" config >/dev/null
docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans
docker compose -f "$COMPOSE_FILE" ps

for svc in postgres redis backend web worker beat caddy; do
  id="$(docker compose -f "$COMPOSE_FILE" ps --status running -q "$svc")"
  test -n "$id" || { echo "Service $svc is not running" >&2; docker compose -f "$COMPOSE_FILE" logs --tail 100 "$svc" || true; exit 1; }
done

for i in $(seq 1 30); do
  if curl -fsS http://localhost/health | grep -q '"ok"'; then
    curl -fsS http://localhost/api/health >/dev/null
    echo "AEON OS is healthy on Google Cloud."
    exit 0
  fi
  sleep 5
done

echo "Health gate failed; attempting rollback to $PREV_SHA" >&2
if test -n "$PREV_SHA"; then
  git reset --hard "$PREV_SHA"
  docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans
  sleep 10
fi

echo "Deployment failed." >&2
exit 1
