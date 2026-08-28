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

case "$EMAIL" in
    *[!A-Za-z0-9._%+-]*@*[!A-Za-z0-9.-]*) echo "ERROR: invalid email" >&2; exit 2 ;;
esac
[ "${#PASSWORD}" -ge 6 ] || { echo "ERROR: password must be at least 6 characters" >&2; exit 2; }
APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
COMPOSE="docker compose -f $APP_DIR/docker-compose.oci.yml"

# ── 1. Seed into PostgreSQL via the Flask backend container ────────────
echo "[seed-user] creating/updating user $EMAIL in PostgreSQL ..."
if [ -n "$($COMPOSE ps --status running -q backend 2>/dev/null)" ]; then
    $COMPOSE exec -T \
        -e AEON_ADMIN_EMAIL="$EMAIL" \
        -e AEON_ADMIN_PASSWORD="$PASSWORD" \
        -e AEON_ADMIN_NAME="${NAME:-$(echo "$EMAIL" | cut -d@ -f1)}" \
        -e AEON_ADMIN_RESET_PASSWORD=true \
        backend python3 /app/scripts/seed_admin.py 2>&1 || {
        echo "[seed-user] ERROR: backend database seed failed" >&2
        exit 1
    }
else
    echo "[seed-user] backend container not running — skipping DB seed"
fi

# ── 2. Seed the Next.js local store only as an offline fallback ─────────
# Oracle's web_data named volume is mounted inside the web container at
# /app/.data; writing $APP_DIR/web/.data on the host does not update it.
# Prefer the database above. If the volume is available, update it through
# the running web container so the fallback survives rebuilds.
if [ -n "$($COMPOSE ps --status running -q web 2>/dev/null)" ]; then
    $COMPOSE exec -T \
        -e AEON_SEED_EMAIL="$EMAIL" \
        -e AEON_SEED_PASSWORD="$PASSWORD" \
        -e AEON_SEED_NAME="${NAME:-$(echo "$EMAIL" | cut -d@ -f1)}" \
        web node <<'NODE'
const fs = require("fs");
const crypto = require("crypto");
const bcrypt = require("bcryptjs");
const file = "/app/.data/aeon-users.json";
const email = String(process.env.AEON_SEED_EMAIL || "").trim().toLowerCase();
const password = String(process.env.AEON_SEED_PASSWORD || "");
const name = String(process.env.AEON_SEED_NAME || email.split("@")[0]);
let users = [];
try {
  const parsed = JSON.parse(fs.readFileSync(file, "utf8"));
  if (Array.isArray(parsed)) users = parsed;
} catch {}
const existing = users.find((user) => user.email === email);
if (existing) {
  existing.passwordHash = bcrypt.hashSync(password, 10);
  existing.name = name;
} else {
  users.push({
    id: `user_${crypto.randomUUID()}`,
    email,
    name,
    passwordHash: bcrypt.hashSync(password, 10),
    role: "ADMIN",
    workspaceId: `ws_${crypto.randomUUID()}`,
    createdAt: new Date().toISOString(),
  });
}
fs.mkdirSync("/app/.data", { recursive: true });
fs.writeFileSync(file, JSON.stringify(users, null, 2), { encoding: "utf8", mode: 0o600 });
console.log(`[seed-user] local store updated: ${email}`);
NODE
else
    echo "[seed-user] web container not running — database seed remains authoritative"
fi

echo "[seed-user] done"
exit 0
