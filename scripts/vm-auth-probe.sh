#!/usr/bin/env bash
# Reproduce the wizard "unauthorized" failure end-to-end on the VM.
# Logs in through NextAuth credentials, then calls the two APIs the
# onboarding wizard uses. Never prints secrets.
set -e
cd /opt/aeon
set -a; . ./.env; set +a

EMAIL="${AEON_ADMIN_EMAIL:-admin@aeon.local}"
PASS="$(grep -E '^AEON_ADMIN_PASSWORD=' .env | cut -d= -f2- || true)"
[ -z "$PASS" ] && PASS="${ADMIN_PASSWORD:-}"
if [ -z "$PASS" ]; then echo "NO_PASSWORD_IN_ENV"; exit 1; fi

JAR=$(mktemp)
BASE="http://127.0.0.1:3000"

echo "== csrf =="
CSRF=$(curl -s -c "$JAR" "$BASE/api/auth/csrf" | python3 -c "import sys,json;print(json.load(sys.stdin)['csrfToken'])")

echo "== credentials login =="
CODE=$(curl -s -o /dev/null -w "%{http_code}" -b "$JAR" -c "$JAR" -X POST "$BASE/api/auth/callback/credentials" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "csrfToken=$CSRF" \
  --data-urlencode "email=$EMAIL" \
  --data-urlencode "password=$PASS" \
  --data-urlencode "json=true")
echo "login status: $CODE"

echo "== session =="
curl -s -b "$JAR" "$BASE/api/auth/session" | head -c 400; echo

echo "== PUT /api/platform/config =="
curl -s -o /tmp/pc.out -w "status: %{http_code}\n" -b "$JAR" -X PUT "$BASE/api/platform/config" \
  -H "Content-Type: application/json" \
  -d '{"company":"Probe Co","industry":"core","currency":"EUR","country":"Malta","deployment_mode":"cloud","modules":["identity"],"connectors":[]}'
head -c 300 /tmp/pc.out; echo

echo "== POST branding =="
WS=$(curl -s -b "$JAR" "$BASE/api/auth/session" | python3 -c "import sys,json;d=json.load(sys.stdin);print((d.get('user') or {}).get('workspaceId') or '')")
echo "workspaceId from session: '$WS'"
curl -s -o /tmp/br.out -w "status: %{http_code}\n" -b "$JAR" -X POST "$BASE/api/workspaces/$WS/branding" \
  -H "Content-Type: application/json" \
  -d '{"companyName":"Probe Co","productName":"Probe","tagline":"","primaryColor":"#6366f1","dashboardComponents":[],"modules":[],"onboardingComplete":true}'
head -c 300 /tmp/br.out; echo
