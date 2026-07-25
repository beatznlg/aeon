#!/usr/bin/env bash
# AEON OS — Docker Entrypoint for Flask Backend
# ==============================================
# - Waits for Postgres to be ready
# - Runs database schema bootstrap
# - Seeds default admin user (if configured)
# - Starts the Flask kernel server

set -euo pipefail

echo "=== AEON OS Backend Entrypoint ==="

# ── Wait for Postgres ───────────────────────────────────────────────────────
DB_URL="${AEON_DATABASE_URL:-}"
if [ -n "$DB_URL" ]; then
    # Extract host:port from database URL
    DB_HOST=$(echo "$DB_URL" | sed -n 's/.*@\([^:/]*\).*/\1/p')
    DB_PORT=$(echo "$DB_URL" | sed -n 's/.*@[^:/]*:\([0-9]*\).*/\1/p')
    DB_HOST="${DB_HOST:-postgres}"
    DB_PORT="${DB_PORT:-5432}"

    echo "Waiting for Postgres at $DB_HOST:$DB_PORT ..."
    for i in $(seq 1 30); do
        if python3 -c "
import socket, sys
try:
    s = socket.create_connection(('$DB_HOST', $DB_PORT), timeout=2)
    s.close()
    sys.exit(0)
except: sys.exit(1)
" 2>/dev/null; then
            echo "Postgres is ready!"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "ERROR: Postgres did not become ready in time"
            exit 1
        fi
        sleep 2
    done

    # ── Run DB schema bootstrap ────────────────────────────────────────────
    echo "Running database schema bootstrap..."
    python3 -c "
import sys
sys.path.insert(0, '/app')
from aeon_db import get_db, Base
try:
    db = get_db()
    # Create all tables
    Base.metadata.create_all(bind=db.engine)
    print('  ✓ Tables created/verified')
except Exception as e:
    print(f'  ⚠ DB schema error (may be retried): {e}')
" || echo "  ⚠ Schema bootstrap skipped (may already exist)"

    # ── Seed default admin ──────────────────────────────────────────────────
    if [ -n "${AEON_ADMIN_EMAIL:-}" ] && [ -n "${AEON_ADMIN_PASSWORD:-}" ]; then
        echo "Seeding admin user: ${AEON_ADMIN_EMAIL} ..."
        python3 -c "
import sys
sys.path.insert(0, '/app')
from werkzeug.security import generate_password_hash
from aeon_db import get_db, User, Workspace, Membership

db = get_db()
email = '$AEON_ADMIN_EMAIL'
existing = db.get_user_by_email(email)
if existing:
    print('  ✓ Admin user already exists')
else:
    with db.session() as s:
        user = User(
            email=email,
            name='${AEON_ADMIN_NAME:-Admin}',
            password=generate_password_hash('$AEON_ADMIN_PASSWORD'),
            role='ADMIN',
        )
        s.add(user)
        s.flush()
        ws = Workspace(slug='default', name='Default Workspace', plan='free')
        s.add(ws)
        s.flush()
        membership = Membership(workspace_id=ws.id, user_id=user.id, role='ADMIN')
        s.add(membership)
        s.commit()
    print(f'  ✓ Admin user created (workspace: default)')
" 2>&1
    fi
else
    echo "No AEON_DATABASE_URL set — running without persistence"
fi

# ── Start Flask Kernel ──────────────────────────────────────────────────────
echo "Starting AEON kernel server on 0.0.0.0:5000 ..."
exec python3 /app/aeon_server.py
