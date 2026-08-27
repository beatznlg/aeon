#!/usr/bin/env sh
# AEON OS — set or reset the admin login on a deployed VM.
#
#   sudo sh scripts/set-admin.sh you@example.com 'YourPassword123'
#
# Persists the credentials in /opt/aeon/.env (used by every backend restart)
# and immediately creates/updates the user inside the running backend
# container via scripts/seed_admin.py. Password characters to avoid: | & \ /
set -eu

EMAIL="${1:?usage: set-admin.sh <email> <password>}"
PASSWORD="${2:?usage: set-admin.sh <email> <password>}"
APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
COMPOSE="docker compose -f $APP_DIR/docker-compose.oci.yml"

test -f "$APP_DIR/.env" || { echo "ERROR: $APP_DIR/.env not found — run deploy-oracle.sh first"; exit 1; }

# Persist for future container starts (replaces existing lines if present).
sed -i "s|^AEON_ADMIN_EMAIL=.*|AEON_ADMIN_EMAIL=$EMAIL|" "$APP_DIR/.env"
if grep -q '^AEON_ADMIN_PASSWORD=' "$APP_DIR/.env"; then
    sed -i "s|^AEON_ADMIN_PASSWORD=.*|AEON_ADMIN_PASSWORD=$PASSWORD|" "$APP_DIR/.env"
else
    printf 'AEON_ADMIN_PASSWORD=%s\n' "$PASSWORD" >>"$APP_DIR/.env"
fi
chmod 600 "$APP_DIR/.env"

# Apply now inside the running backend (works even while the kernel is up).
if $COMPOSE exec -T \
    -e AEON_ADMIN_EMAIL="$EMAIL" \
    -e AEON_ADMIN_PASSWORD="$PASSWORD" \
    -e AEON_ADMIN_RESET_PASSWORD=true \
    backend python3 /app/scripts/seed_admin.py; then
    echo ""
    echo "Admin account ready. Sign in with:"
    echo "  $EMAIL"
elif docker ps --format '{{.Names}}' | grep -q aeon-backend; then
    echo "WARNING: could not reach the backend python — the timer/restart will seed from .env"
else
    echo "Backend not running — starting it so the entrypoint seeds the admin..."
    $COMPOSE up -d backend
    sleep 20
    echo "Done. Sign in at your site URL with: $EMAIL"
fi
