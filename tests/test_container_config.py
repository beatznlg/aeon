"""Static regression tests for container port configuration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docker_healthcheck_uses_runtime_port_precedence():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    # Dockerfile HEALTHCHECK only supports the CMD keyword (shell-form).
    # CMD-SHELL is docker-compose syntax and, in a Dockerfile, would try to
    # exec a binary literally named CMD-SHELL (regression fixed in d3e1de3).
    assert 'CMD curl -f "http://localhost:${AEON_PYTHON_PORT:-${PORT:-5000}}/health"' in dockerfile
    assert "CMD-SHELL" not in dockerfile


def test_docker_image_includes_alembic_migrations():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY aeon*.py requirements.txt alembic.ini ./" in dockerfile
    assert "COPY alembic ./alembic" in dockerfile


def test_entrypoint_runs_ordered_migrations_and_fails_closed():
    entrypoint = (ROOT / "scripts" / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert "from aeon_db import migrate_database" in entrypoint
    assert "migrate_database()" in entrypoint
    assert "|| echo \"  ⚠ Schema bootstrap skipped" not in entrypoint


def test_entrypoint_reports_and_preserves_runtime_port_precedence():
    entrypoint = (ROOT / "scripts" / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert 'APP_PORT="${AEON_PYTHON_PORT:-${PORT:-5000}}"' in entrypoint
    assert 'APP_HOST="${AEON_PYTHON_HOST:-0.0.0.0}"' in entrypoint
    assert 'echo "Starting AEON kernel server on ${APP_HOST}:${APP_PORT} ..."' in entrypoint
    assert '0.0.0.0:5000 ...' not in entrypoint
