#!/usr/bin/env bash
# Start the full AEON preview stack: Python backend + Next.js frontend.
set -e

# Make user-installed Python packages visible when the preview runs under a
# different user or a stripped environment.
export PYTHONPATH="/home/daytona/.local/lib/python3.10/site-packages:${PYTHONPATH}"

# Ensure the Next.js dev server binds to all interfaces.
export HOST="0.0.0.0"
export HOSTNAME="0.0.0.0"

# Use the local SQLite automation_executions table when Supabase is not
# configured, so the preview dashboard can still show real metrics.
export AEON_METRICS_LOCAL_FALLBACK="1"

cd web
export AEON_PYTHON_URL="${AEON_PYTHON_URL:-http://127.0.0.1:5000}"
npm run dev:full
