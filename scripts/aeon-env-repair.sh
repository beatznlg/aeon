#!/usr/bin/env sh
# AEON OS — idempotent .env self-repair for the Oracle Cloud VM.
# ==============================================================
# Fixes the three conditions that make login impossible on installs created
# by earlier bootstrap versions:
#   1. AEON_ADMIN_EMAIL / AEON_ADMIN_PASSWORD left empty  -> no user in DB
#   2. NEXTAUTH_URL left empty                            -> Auth.js breaks
#   3. Required secrets missing                           -> compose won't start
# Run automatically by scripts/aeon-autoupdate.sh (every 30 min) and by
# scripts/deploy-oracle.sh. Never blocks a deploy: exits 0 on any problem it
# cannot fix. Safe to re-run at any time.
#   View the admin login afterwards:  sudo grep AEON_ADMIN /opt/aeon/.env
set -eu

APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
ENV_FILE="$APP_DIR/.env"

[ -f "$ENV_FILE" ] || { echo "[env-repair] no $ENV_FILE — nothing to repair"; exit 0; }

get() { sed -n "s|^$1=||p" "$ENV_FILE" | head -1; }

set_kv() {
    if grep -q "^$1=" "$ENV_FILE"; then
        sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"
    else
        printf '%s=%s\n' "$1" "$2" >>"$ENV_FILE"
    fi
}

gen() { head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c "$1"; }

# ── 1. Required secrets (repairs .env files created before these existed) ──
for KEY in POSTGRES_PASSWORD AUTH_SECRET AEON_JWT_SECRET; do
    VAL=$(get "$KEY")
    if [ -z "$VAL" ]; then
        set_kv "$KEY" "$(gen 32)"
        echo "[env-repair] generated missing $KEY"
    fi
done

# ── 2. Admin login: create one if email or password is missing ─────────────
ADMIN_EMAIL=$(get AEON_ADMIN_EMAIL)
ADMIN_PASS=$(get AEON_ADMIN_PASSWORD)
if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASS" ]; then
    [ -n "$ADMIN_EMAIL" ] || ADMIN_EMAIL="admin@aeon.local"
    [ -n "$ADMIN_PASS" ] || ADMIN_PASS="$(gen 14)"
    set_kv AEON_ADMIN_EMAIL "$ADMIN_EMAIL"
    set_kv AEON_ADMIN_PASSWORD "$ADMIN_PASS"
    [ -n "$(get AEON_ADMIN_NAME)" ] || set_kv AEON_ADMIN_NAME "Admin"
    echo "[env-repair] admin login ensured: $ADMIN_EMAIL"
    echo "[env-repair]   view password:  sudo grep AEON_ADMIN_PASSWORD $ENV_FILE"
fi

# ── 3. Public URL for Auth.js (AEON_DOMAIN stays empty -> Caddy serves :80) ─
NEXT_URL=$(get NEXTAUTH_URL)
if [ -z "$NEXT_URL" ]; then
    PUB_IP=""
    PUB_IP=$(curl -fs --max-time 5 https://api.ipify.org 2>/dev/null || true)
    [ -n "$PUB_IP" ] || PUB_IP=$(curl -fs --max-time 5 https://ipv4.icanhazip.com 2>/dev/null | tr -d '[:space:]' || true)
    if [ -n "$PUB_IP" ]; then
        set_kv NEXTAUTH_URL "http://$PUB_IP"
        set_kv AEON_CORS_ALLOWED_ORIGINS "http://$PUB_IP"
        echo "[env-repair] NEXTAUTH_URL -> http://$PUB_IP"
    else
        echo "[env-repair] WARNING: could not detect public IP; set NEXTAUTH_URL in $ENV_FILE manually"
    fi
fi

chmod 600 "$ENV_FILE" 2>/dev/null || true
echo "[env-repair] done"
exit 0
