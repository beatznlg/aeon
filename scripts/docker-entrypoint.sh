#!/usr/bin/env bash
# AEON OS — Docker Entrypoint for Flask Backend
# ==============================================
# - Waits for Postgres to be ready
# - Runs database schema bootstrap
# - Seeds default admin user (if configured) via scripts/seed_admin.py
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
except Exception:
    sys.exit(1)
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

    # ── Run ordered DB migrations ───────────────────────────────────────
    echo "Running database migrations..."
    python3 -c "
import sys
sys.path.insert(0, '/app')
from aeon_db import migrate_database
migrate_database()
print('  ✓ Database schema is at Alembic head')
"

    # ── Seed default admin ──────────────────────────────────────────────
    # Credentials come from the environment only (never interpolated into
    # code, so special characters in passwords are safe).
    if [ -n "${AEON_ADMIN_EMAIL:-}" ] && [ -n "${AEON_ADMIN_PASSWORD:-}" ]; then
        echo "Seeding admin user: ${AEON_ADMIN_EMAIL} ..."
        python3 /app/scripts/seed_admin.py 2>&1 ||
            echo "WARNING: admin seeding failed — continuing startup"
    fi
else
    echo "No AEON_DATABASE_URL set — running without persistence"
fi

# ── Start Flask Kernel ──────────────────────────────────────────────────
APP_HOST="${AEON_PYTHON_HOST:-0.0.0.0}"
APP_PORT="${AEON_PYTHON_PORT:-${PORT:-5000}}"
echo "Starting AEON kernel server on ${APP_HOST}:${APP_PORT} ..."
exec python3 /app/aeon_server.py
