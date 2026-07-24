#!/bin/bash
set -e

# AEON Docker entrypoint
# Defaults can be overridden via environment variables.
export AEON_PYTHON_HOST=${AEON_PYTHON_HOST:-0.0.0.0}
export AEON_PYTHON_PORT=${AEON_PYTHON_PORT:-5000}
export AEON_ROOT=${AEON_ROOT:-/home/aeon/app/aeon_state}

# Ensure runtime directories exist and are writable by aeon user.
mkdir -p "$AEON_ROOT"

echo "AEON starting on ${AEON_PYTHON_HOST}:${AEON_PYTHON_PORT}"
echo "AEON_ROOT=${AEON_ROOT}"

# Run whatever command was passed, defaulting to gunicorn.
exec "$@"
