#!/usr/bin/env bash
# Probe each leg of the auth chain on the VM. Never prints secrets.
set -e
cd /opt/aeon
set -a; . ./.env; set +a

EMAIL="${AEON_ADMIN_EMAIL:-admin@aeon.local}"
PASS="$(grep -E '^AEON_ADMIN_PASSWORD=' .env | cut -d= -f2- || true)"
[ -z "$PASS" ] && PASS="${ADMIN_PASSWORD:-}"

echo "== 1. direct Flask backend login =="
curl -s --max-time 20 -X POST http://127.0.0.1:5000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print('ok:', d.get('ok'), '| user id:', (d.get('user') or {}).get('id'), '| role:', (d.get('user') or {}).get('role'), '| ws:', (d.get('user') or {}).get('workspace_id'))
except Exception as e:
    print('unparseable response:', e)"

echo "== 2. env var names present in .env =="
grep -E '^(AUTH_SECRET|NEXTAUTH_SECRET|AUTH_TRUST_HOST|AEON_PYTHON_URL|ADMIN_EMAIL|ADMIN_PASSWORD|NEXTAUTH_URL|AUTH_URL)=' .env | cut -d= -f1 || echo none

echo "== 3. cookie jar after NextAuth callback =="
JAR=$(mktemp)
CSRF=$(curl -s -c "$JAR" http://127.0.0.1:3000/api/auth/csrf | python3 -c "import sys,json;print(json.load(sys.stdin)['csrfToken'])")
LOC=$(curl -s -o /dev/null -w "%{redirect_url}" -b "$JAR" -c "$JAR" -X POST http://127.0.0.1:3000/api/auth/callback/credentials \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "csrfToken=$CSRF" \
  --data-urlencode "email=$EMAIL" \
  --data-urlencode "password=$PASS" \
  --data-urlencode "json=true")
echo "redirect target: $LOC"
echo "cookies set:"
awk '$6 ~ /authjs|next-auth|session/ {print "  - " $6}' "$JAR" || true
