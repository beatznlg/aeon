#!/usr/bin/env sh
# AEON OS — deterministic production preflight gate.
# Safe locally, in CI, and on the Oracle VM. CI uses synthetic values only to
# render Compose; real production secrets are never committed or required here.
set -eu

APP_DIR="${AEON_APP_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
COMPOSE="docker compose -f $APP_DIR/docker-compose.oci.yml"

fail() { echo "[production-gate] FAIL: $*" >&2; exit 1; }
ok() { echo "[production-gate] OK: $*"; }

[ -f "$APP_DIR/docker-compose.oci.yml" ] || fail "missing docker-compose.oci.yml"
[ -f "$APP_DIR/Caddyfile" ] || fail "missing Caddyfile"

# Compose requires production variables even though this static gate does not
# need their real values. Supply deterministic CI-only placeholders so the
# configuration can be rendered without creating a .env file or leaking secrets.
compose_config() {
    env \
      POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-ci-postgres-password-0123456789}" \
      AEON_JWT_SECRET="${AEON_JWT_SECRET:-ci-jwt-secret-012345678901234567890123}" \
      AEON_MASTER_KMS_KEY="${AEON_MASTER_KMS_KEY:-ci-kms-key-012345678901234567890123}" \
      AUTH_SECRET="${AUTH_SECRET:-ci-auth-secret-012345678901234567890123}" \
      NEXTAUTH_URL="${NEXTAUTH_URL:-https://example.invalid}" \
      NEXT_PUBLIC_APP_URL="${NEXT_PUBLIC_APP_URL:-https://example.invalid}" \
      AEON_CORS_ALLOWED_ORIGINS="${AEON_CORS_ALLOWED_ORIGINS:-https://example.invalid}" \
      AEON_DOMAIN="${AEON_DOMAIN:-example.invalid}" \
      sh -c "$COMPOSE config $*"
}

compose_config >/dev/null || fail "Oracle Compose configuration is invalid"
ok "Oracle Compose renders successfully"

# Production must expose only the reverse proxy. These ports must never be
# published directly from the Oracle stack.
if compose_config | grep -E '^[[:space:]]*-?[[:space:]]*"?(5432|6379|5000|3000)(:|/)' >/dev/null 2>&1; then
    fail "database, Redis, backend, or frontend port is publicly published"
fi
ok "internal services are not publicly published"

# Required services are part of the production contract.
for service in postgres redis backend worker beat web caddy; do
    compose_config --services | grep -qx "$service" || fail "missing production service: $service"
done
ok "all seven production services are defined"

# Validate the actual variable names used by the Oracle stack.
for key in POSTGRES_PASSWORD AEON_JWT_SECRET AEON_MASTER_KMS_KEY AUTH_SECRET NEXTAUTH_URL NEXT_PUBLIC_APP_URL AEON_CORS_ALLOWED_ORIGINS AEON_DOMAIN; do
    grep -q "$key" "$APP_DIR/docker-compose.oci.yml" || fail "missing production config contract: $key"
done
ok "production secret and URL contracts are present"

# Legacy managed-host credentials must not be wired into the Oracle stack.
if grep -nE 'SUPABASE_SERVICE_ROLE_KEY|SUPABASE_URL|VERCEL_TOKEN|RAILWAY_TOKEN|RENDER_API_KEY' "$APP_DIR/docker-compose.oci.yml" >/dev/null 2>&1; then
    fail "legacy managed-host credentials are present in Oracle production Compose"
fi
ok "Oracle production Compose has no legacy hosting credentials"

# Ensure no obvious secret literals are checked into production Compose.
if grep -nE '(^|[ =])([A-Za-z0-9_]*(PASSWORD|SECRET|TOKEN|API_KEY)[A-Za-z0-9_]*)[=:][[:space:]]*[A-Za-z0-9+/=_-]{16,}' "$APP_DIR/docker-compose.oci.yml" >/dev/null 2>&1; then
    fail "possible hard-coded production secret found in Oracle Compose"
fi
ok "no obvious hard-coded production secret found"

echo "[production-gate] PASS — static production preflight completed"
