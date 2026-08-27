#!/usr/bin/env bash
# Re-sync the AEON admin password: set the DB hash to match AEON_ADMIN_PASSWORD
# from /opt/aeon/.env, then verify Flask login and the NextAuth session flow.
# Never prints secrets.
set -e
cd /opt/aeon
set -a; . ./.env; set +a

EMAIL="${AEON_ADMIN_EMAIL:-admin@aeon.local}"
PASS="$(grep -E '^AEON_ADMIN_PASSWORD=' .env | cut -d= -f2- || true)"
if [ -z "$PASS" ]; then echo "NO_PASSWORD_IN_ENV — generating one into .env"; PASS="$(openssl rand -base64 18)"; echo "AEON_ADMIN_PASSWORD=$PASS" >> .env; fi
echo "NEXTAUTH_URL is: ${NEXTAUTH_URL:-<unset>}"

echo "== 1. update admin password hash in DB =="
/opt/aeon/venv/bin/python3 - "$EMAIL" "$PASS" <<'PY'
import sys
from werkzeug.security import generate_password_hash
import aeon_db  # app's own SQLAlchemy models/session

email, password = sys.argv[1], sys.argv[2]
pw_hash = generate_password_hash(password)
with aeon_db.session_scope() as s:
    user = s.query(aeon_db.User).filter_by(email=email).one_or_none()
    if user is None:
        print("admin row missing!")
        sys.exit(2)
    user.password = pw_hash
    if getattr(user, "role", None) != "ADMIN":
        user.role = "ADMIN"
    print("password hash updated for", email, "| role:", user.role)
PY

echo "== 2. direct Flask login =="
curl -s --max-time 20 -X POST http://127.0.0.1:5000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | python3 -c "
import sys,json
d=json.load(sys.stdin)
u=d.get('user') or {}
print('flask ok:', d.get('ok'), '| role:', u.get('role'), '| workspace:', u.get('workspace_id'))"

echo "== 3. NextAuth session flow =="
JAR=$(mktemp); BASE="http://127.0.0.1:3000"
CSRF=$(curl -s -c "$JAR" "$BASE/api/auth/csrf" | python3 -c "import sys,json;print(json.load(sys.stdin)['csrfToken'])")
LOC=$(curl -s -o /dev/null -w "%{redirect_url}" -b "$JAR" -c "$JAR" -X POST "$BASE/api/auth/callback/credentials" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "csrfToken=$CSRF" --data-urlencode "email=$EMAIL" \
  --data-urlencode "password=$PASS" --data-urlencode "json=true")
echo "redirect: $LOC"
SESS=$(curl -s -b "$JAR" "$BASE/api/auth/session")
echo "session: $(echo "$SESS" | head -c 250)"
WS=$(echo "$SESS" | python3 -c "import sys,json;d=json.load(sys.stdin);print((d.get('user') or {}).get('workspaceId') or '')" 2>/dev/null || true)

echo "== 4. wizard APIs with real session =="
curl -s -o /tmp/pc.out -w "PUT platform/config: %{http_code} " -b "$JAR" -X PUT "$BASE/api/platform/config" \
  -H "Content-Type: application/json" \
  -d '{"company":"NLGbeatz","industry":"core","currency":"EUR","country":"Malta","deployment_mode":"cloud","modules":["identity"],"connectors":[]}'
head -c 160 /tmp/pc.out; echo
curl -s -o /tmp/br.out -w "POST branding: %{http_code} " -b "$JAR" -X POST "$BASE/api/workspaces/$WS/branding" \
  -H "Content-Type: application/json" \
  -d '{"companyName":"NLGbeatz","productName":"NLGbeatz Defense Command","tagline":"Mission-Critical Cyber Operations","primaryColor":"#6366f1","dashboardComponents":[],"modules":[],"onboardingComplete":true}'
head -c 160 /tmp/br.out; echo
echo "PROBE_COMPLETE"
