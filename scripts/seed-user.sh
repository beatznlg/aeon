#!/usr/bin/env sh
# AEON OS — seed a user into BOTH the Flask backend DB and the local store
# ======================================================================
#   sh scripts/seed-user.sh email password [name]
#
# Creates the user in PostgreSQL via the running backend container AND
# saves a copy to the Next.js local user store so the user can log in
# even when the backend is temporarily unreachable.
#
# Designed to be called by the auto-updater after every pull.
set -eu

EMAIL="${1:?usage: seed-user.sh <email> <password> [name]}"
PASSWORD="${2:?usage: seed-user.sh <email> <password> [name]}"
NAME="${3:-}"
APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
COMPOSE="docker compose -f $APP_DIR/docker-compose.oci.yml"

# ── 1. Seed into PostgreSQL via the Flask backend container ────────────
echo "[seed-user] creating/updating user $EMAIL in PostgreSQL ..."
if docker ps --format '{{.Names}}' | grep -q aeon-backend; then
    $COMPOSE exec -T \
        -e AEON_ADMIN_EMAIL="$EMAIL" \
        -e AEON_ADMIN_PASSWORD="$PASSWORD" \
        -e AEON_ADMIN_NAME="${NAME:-$(echo "$EMAIL" | cut -d@ -f1)}" \
        -e AEON_ADMIN_RESET_PASSWORD=true \
        backend python3 /app/scripts/seed_admin.py 2>&1 || \
        echo "[seed-user] WARNING: backend seed failed — continuing"
else
    echo "[seed-user] backend container not running — skipping DB seed"
fi

# ── 2. Seed into the Next.js local user store ─────────────────────────
# Write a small Node.js one-liner that calls createLocalUser().
WEB_DATA="$APP_DIR/web-data"
WEB_DATA_DIR="$APP_DIR/web/.data"
# In Docker the web_data volume is mounted at /app/.data inside the container,
# but we can also write directly from the host if the directory exists.
TARGET_DIR="${WEB_DATA_DIR:-$WEB_DATA}"
mkdir -p "$TARGET_DIR"
LOCAL_FILE="$TARGET_DIR/aeon-users.json"

if command -v node >/dev/null 2>&1; then
    node -e "
const fs = require('fs');
const crypto = require('crypto');
const bcrypt = require('$APP_DIR/web/node_modules/bcryptjs');

const file = '$LOCAL_FILE';
let users = [];
try {
    const raw = fs.readFileSync(file, 'utf8');
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) users = parsed;
} catch {}

const email = '$EMAIL'.toLowerCase().trim();
const existing = users.find(u => u.email === email);
const hash = bcrypt.hashSync('$PASSWORD', 10);
const name = '${NAME:-$(echo "$EMAIL" | cut -d@ -f1)}';

if (existing) {
    existing.passwordHash = hash;
    existing.name = name;
    console.log('[seed-user] updated local user: ' + email);
} else {
    users.push({
        id: 'user_' + crypto.randomUUID(),
        email,
        name,
        passwordHash: hash,
        role: 'ADMIN',
        workspaceId: 'ws_' + crypto.randomUUID(),
        createdAt: new Date().toISOString(),
    });
    console.log('[seed-user] created local user: ' + email);
}
fs.writeFileSync(file, JSON.stringify(users, null, 2), { encoding: 'utf-8', mode: 0o600 });
" 2>/dev/null && echo "[seed-user] local store updated" || \
    echo "[seed-user] WARNING: could not update local store (node/bcryptjs unavailable)"
else
    echo "[seed-user] node not found — skipping local store seed"
fi

echo "[seed-user] done"
exit 0
