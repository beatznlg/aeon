#!/usr/bin/env sh
# AEON OS — deterministic production preflight gate.
# This gate is safe to run locally or on the Oracle VM. It validates the
# production configuration without requiring access to secrets.
set -eu

APP_DIR="${AEON_APP_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
COMPOSE="docker compose -f "$APP_DIR/docker-compose.oci.yml""

fail() { echo "[production-gate] FAIL: $*" >&2; exit 1; }
ok() { echo "[production-gate] OK: $*"; }

[ -f "$APP_DIR/docker-compose.oci.yml" ] || fail "missing docker-compose.oci.yml"
[ -f "$APP_DIR/Caddyfile" ] || fail "missing Caddyfile"

# Docker Compose must render successfully before deployment.
$COMPOSE config >/dev/null || fail "Oracle Compose configuration is invalid"
ok "Oracle Compose renders successfully"

# Production must expose only the reverse proxy. These ports must never be
# published directly from the Oracle stack.
if $COMPOSE config | grep -E '^[[:space:]]*-?[[:space:]]*"?(5432|6379|5000|3000)(:|/)' >/dev/null 2>&1; then
    fail "database, Redis, backend, or frontend port is publicly published"
fi
ok "internal services are not publicly published"

# Required services are part of the production contract.
for service in postgres redis backend worker beat web caddy; do
    $COMPOSE config --services | grep -qx "$service" || fail "missing production service: $service"
done
ok "all seven production services are defined"

# Production compose must use explicit secrets for authentication/encryption.
for key in AEON_JWT_SECRET AEON_ENCRYPTION_MASTER_KEY NEXTAUTH_SECRET; do
    grep -q "$key" "$APP_DIR/docker-compose.oci.yml" || fail "missing secret contract: $key"
done
ok "production secret contracts are present"

# Fail if legacy managed-host runtime variables are wired into the OCI stack.
if grep -nE 'SUPABASE_SERVICE_ROLE_KEY|SUPABASE_URL|VERCEL_TOKEN|RAILWAY_TOKEN|RENDER_API_KEY' "$APP_DIR/docker-compose.oci.yml" >/dev/null 2>&1; then
    fail "legacy managed-host credentials are present in Oracle production Compose"
fi
ok "Oracle production Compose has no legacy hosting credentials"

# Ensure no obvious secret literals are checked into the production compose.
if grep -nE '(^|[ =])([A-Za-z0-9_]*(PASSWORD|SECRET|TOKEN|API_KEY)[A-Za-z0-9_]*)[=:][[:space:]]*[A-Za-z0-9+/=_-]{16,}' "$APP_DIR/docker-compose.oci.yml" >/dev/null 2>&1; then
    fail "possible hard-coded production secret found in Oracle Compose"
fi
ok "no obvious hard-coded production secret found"

echo "[production-gate] PASS — static production preflight completed"
