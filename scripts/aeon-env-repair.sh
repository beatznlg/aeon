#!/usr/bin/env sh
# AEON OS — idempotent .env self-repair for the Oracle Cloud VM.
# Generates missing secrets and a random first-boot admin password without
# embedding user-specific credentials in source control.
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
gen() { head -c 64 /dev/urandom | base64 | tr -d '/+=' | head -c "$1"; }

# Required independent secrets. Do not reuse authentication keys for encryption.
for KEY in POSTGRES_PASSWORD AUTH_SECRET AEON_JWT_SECRET AEON_API_TOKEN; do
    VAL=$(get "$KEY")
    if [ -z "$VAL" ]; then
        set_kv "$KEY" "$(gen 48)"
        echo "[env-repair] generated missing $KEY"
    fi
done

KMS=$(get AEON_MASTER_KMS_KEY)
if [ -z "$KMS" ] || [ "$KMS" = "$(get AEON_JWT_SECRET)" ]; then
    set_kv AEON_MASTER_KMS_KEY "$(gen 64)"
    echo "[env-repair] generated independent AEON_MASTER_KMS_KEY"
fi

# First-boot admin: never ship a fixed password. Existing credentials are preserved.
ADMIN_EMAIL=$(get AEON_ADMIN_EMAIL)
ADMIN_PASS=$(get AEON_ADMIN_PASSWORD)
if [ -z "$ADMIN_EMAIL" ]; then
    ADMIN_EMAIL="admin@aeon.local"
    set_kv AEON_ADMIN_EMAIL "$ADMIN_EMAIL"
fi
if [ -z "$ADMIN_PASS" ]; then
    ADMIN_PASS="$(gen 28)"
    set_kv AEON_ADMIN_PASSWORD "$ADMIN_PASS"
    echo "[env-repair] generated a random first-boot admin password"
fi
[ -n "$(get AEON_ADMIN_NAME)" ] || set_kv AEON_ADMIN_NAME "Platform Admin"

# Public URL. Prefer an explicit domain; otherwise use the detected public IP.
NEXT_URL=$(get NEXTAUTH_URL)
case "$NEXT_URL" in
    ""|http://localhost|http://localhost:*|https://localhost|https://localhost:*|http://127.0.0.1|http://127.0.0.1:*)
        PUB_IP=$(curl -fs --max-time 5 https://api.ipify.org 2>/dev/null || true)
        PUB_IP=${PUB_IP:-$(curl -fs --max-time 5 https://ipv4.icanhazip.com 2>/dev/null | tr -d '[:space:]' || true)}
        if [ -n "$PUB_IP" ]; then
            set_kv NEXTAUTH_URL "http://$PUB_IP"
            set_kv AEON_CORS_ALLOWED_ORIGINS "http://$PUB_IP"
            set_kv NEXT_PUBLIC_APP_URL "http://$PUB_IP"
            echo "[env-repair] NEXTAUTH_URL -> http://$PUB_IP"
        else
            echo "[env-repair] WARNING: could not detect public IP; set NEXTAUTH_URL manually"
        fi
        ;;
    *) echo "[env-repair] NEXTAUTH_URL ok: $NEXT_URL" ;;
esac

chmod 600 "$ENV_FILE" 2>/dev/null || true
echo "[env-repair] done"
