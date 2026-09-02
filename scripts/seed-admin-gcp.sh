#!/bin/sh
# ============================================================================
# AEON OS — seed the dashboard admin user on the GCP Cloud Run deployment
#
# Run from Cloud Shell after the CI/CD deploy has succeeded:
#
#     cd ~/aeon && git pull origin main && sh scripts/seed-admin-gcp.sh
#
# or with explicit credentials:
#
#     sh scripts/seed-admin-gcp.sh you@example.com 'YourPassword123'
#
# What it does:
#   1. Gates on the deployment being healthy (backend /health must return
#      ok:true — refuses to run against a half-deployed stack).
#   2. Uses your email/password, or generates a strong random password and
#      prints it exactly once.
#   3. Sets AEON_ADMIN_EMAIL / AEON_ADMIN_PASSWORD (temporarily also
#      AEON_ADMIN_RESET_PASSWORD) on the aeon-api Cloud Run service. The new
#      revision's entrypoint runs scripts/seed_admin.py at boot, which
#      idempotently creates the OWNER user + 'default' workspace membership.
#   4. Removes the reset flag afterwards so routine restarts never overwrite
#      a password changed later inside the app.
#   5. Verifies end-to-end by logging in via POST /auth/login and prints the
#      dashboard URL.
#
# Notes:
#   - Idempotent: safe to re-run (re-running resets the password to the given
#     values).
#   - Credentials are stored as Cloud Run environment variables on aeon-api
#     (visible to project Editors). For stricter secret handling migrate them
#     to Secret Manager later; this matches the project's documented env-var
#     configuration.
#   - Requires only gcloud + curl; never touches Cloud SQL or other env vars.
# ============================================================================
set -eu

REGION="${AEON_GCP_REGION:-europe-west1}"
BACKEND_SERVICE="${AEON_BACKEND_SERVICE:-aeon-api}"
FRONTEND_SERVICE="${AEON_FRONTEND_SERVICE:-aeon-web}"

say()  { printf '\n===> %s\n' "$1"; }
info() { printf '    %s\n' "$1"; }

command -v gcloud >/dev/null 2>&1 || { echo "ERROR: gcloud not found. Run this in Cloud Shell." >&2; exit 1; }
command -v curl   >/dev/null 2>&1 || { echo "ERROR: curl not found." >&2; exit 1; }

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
[ -n "$PROJECT_ID" ] && [ "$PROJECT_ID" != "None" ] || {
  echo "ERROR: no active gcloud project. Run: gcloud config set project <project-id>" >&2
  exit 1
}

BACKEND_URL=$(gcloud run services describe "$BACKEND_SERVICE" \
  --region "$REGION" --format='value(status.url)' 2>/dev/null || true)
[ -n "$BACKEND_URL" ] || {
  echo "ERROR: service '$BACKEND_SERVICE' not found in $PROJECT_ID/$REGION." >&2
  echo "Deploy first: sh scripts/setup-gcp-cicd.sh" >&2
  exit 1
}
FRONTEND_URL=$(gcloud run services describe "$FRONTEND_SERVICE" \
  --region "$REGION" --format='value(status.url)' 2>/dev/null || true)

say "Project $PROJECT_ID — backend: $BACKEND_URL"

# 1 ─ Deploy-success gate ────────────────────────────────────────────────────
say "Step 1/5: waiting for the deployed backend to report healthy"
i=0
HEALTHY=""
while [ "$i" -lt 30 ]; do
  if curl -fsS "$BACKEND_URL/health" 2>/dev/null | grep -q '"ok":true'; then
    HEALTHY=1
    break
  fi
  i=$((i + 1))
  sleep 5
done
[ -n "$HEALTHY" ] || {
  echo "ERROR: backend /health did not return ok:true — deploy is not complete." >&2
  echo "Run 'sh scripts/setup-gcp-cicd.sh' first, then re-run this script." >&2
  exit 1
}
info "backend healthy"
if [ -n "$FRONTEND_URL" ]; then
  if curl -fsS -o /dev/null "$FRONTEND_URL/api/health" 2>/dev/null; then
    info "frontend responding at $FRONTEND_URL"
  else
    info "WARNING: frontend not responding yet — dashboard may still be rolling out"
  fi
else
  info "WARNING: frontend service '$FRONTEND_SERVICE' not found yet"
fi

# 2 ─ Credentials ────────────────────────────────────────────────────────────
say "Step 2/5: preparing admin credentials"
EMAIL="${1:-${AEON_ADMIN_EMAIL:-}}"
PASSWORD="${2:-}"

if [ -z "$EMAIL" ]; then
  printf 'Admin email [%s]: ' "$(gcloud config get-value account 2>/dev/null)"
  read -r EMAIL
fi
EMAIL=$(printf '%s' "$EMAIL" | tr '[:upper:]' '[:lower:]')
case "$EMAIL" in
  *[!A-Za-z0-9._%+-]*@*[!A-Za-z0-9.-]*|""|*@*.*@*)
    echo "ERROR: invalid email '$EMAIL'" >&2; exit 1 ;;
esac

if [ -z "$PASSWORD" ]; then
  GENERATED=1
  # hex (not base64): no '=', '+', or '/' — safe inside the comma-separated
  # --update-env-vars list below.
  PASSWORD=$(openssl rand -hex 16)
fi
[ "${#PASSWORD}" -ge 8 ] || {
  echo "ERROR: password must be at least 8 characters" >&2; exit 1
}

info "admin email: $EMAIL"
if [ "${GENERATED:-0}" = "1" ]; then
  echo
  echo "  ┌─────────────────────────────────────────────────────────────┐"
  echo "  │ GENERATED PASSWORD (shown once — store it now):            │"
  echo "  │                                                             │"
  echo "  │   $PASSWORD"
  echo "  │                                                             │"
  echo "  └─────────────────────────────────────────────────────────────┘"
  echo
fi

# 3 ─ Apply via Cloud Run env vars (entrypoint seeds at revision boot) ──────
say "Step 3/5: updating $BACKEND_SERVICE — new revision will seed the admin"
# Only these keys change; database URL, JWT secret, and everything else on
# the service are preserved. RESET=true makes re-runs overwrite the password.
gcloud run services update "$BACKEND_SERVICE" \
  --region "$REGION" \
  --update-env-vars \
"AEON_ADMIN_EMAIL=$EMAIL,AEON_ADMIN_PASSWORD=$PASSWORD,AEON_ADMIN_RESET_PASSWORD=true" \
  --quiet >/dev/null
info "revision deployed — waiting for the service to become ready"
gcloud run services wait "$BACKEND_SERVICE" --region "$REGION" >/dev/null 2>&1 || true

# 4 ─ Remove the reset flag (future boots must not clobber app-changed pw) ──
say "Step 4/5: removing one-time reset flag"
gcloud run services update "$BACKEND_SERVICE" \
  --region "$REGION" \
  --remove-env-vars AEON_ADMIN_RESET_PASSWORD \
  --quiet >/dev/null
gcloud run services wait "$BACKEND_SERVICE" --region "$REGION" >/dev/null 2>&1 || true
info "done — AEON_ADMIN_EMAIL/PASSWORD remain set for future reseeds if needed"

# 5 ─ Verify by logging in ──────────────────────────────────────────────────
say "Step 5/5: verifying login"
i=0
LOGIN_OK=""
while [ "$i" -lt 24 ]; do
  CODE=$(curl -sS -o /tmp/aeon_login_check.json -w '%{http_code}' -m 10 \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
    "$BACKEND_URL/auth/login" 2>/dev/null || echo 000)
  if [ "$CODE" = "200" ] && grep -q '"ok":true' /tmp/aeon_login_check.json 2>/dev/null; then
    LOGIN_OK=1
    break
  fi
  i=$((i + 1))
  sleep 5
done
rm -f /tmp/aeon_login_check.json

say "Seed complete"
if [ -n "$LOGIN_OK" ]; then
  echo "  Admin user : $EMAIL (OWNER of the 'default' workspace)"
  echo "  Login check: OK (POST /auth/login -> 200)"
  [ -n "$FRONTEND_URL" ] && echo "  Dashboard  : $FRONTEND_URL"
  echo
  echo "  Sign in on the dashboard with the email + password above."
else
  echo "  WARNING: could not confirm login yet — the revision may still be" >&2
  echo "  starting. Try again in a minute:" >&2
  echo "    curl -s -X POST $BACKEND_URL/auth/login -H 'Content-Type: application/json' -d '{\"email\":\"$EMAIL\",\"password\":\"<your-password>\"}'" >&2
  exit 1
fi
