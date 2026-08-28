#!/usr/bin/env sh
# AEON OS — restore a PostgreSQL backup created by scripts/backup-db.sh.
# ======================================================================
# DESTRUCTIVE to the CURRENT database contents: tables are replaced with the
# backup. Asks for typed confirmation unless AEON_FORCE_RESTORE=1 (CI use).
#
# Usage:
#   sudo sh scripts/restore-db.sh /opt/aeon/backups/aeon-YYYYmmdd-HHMMSS.sql.gz
set -eu

FILE="${1:?usage: restore-db.sh <aeon-TIMESTAMP.sql.gz>}"
[ -f "$FILE" ] || { echo "backup not found: $FILE" >&2; exit 1; }

APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
COMPOSE="docker compose -f $APP_DIR/docker-compose.oci.yml"
[ "$(id -u)" = 0 ] || { echo "Run with sudo."; exit 1; }

if [ "${AEON_FORCE_RESTORE:-0}" != "1" ]; then
    printf 'This overwrites the CURRENT aeon database with:\n  %s\nType RESTORE to continue: ' "$FILE"
    read -r answer
    [ "$answer" = "RESTORE" ] || { echo "aborted — nothing changed"; exit 1; }
fi

echo "[restore] stopping backend/web to prevent writes during import..."
$COMPOSE stop backend web >/dev/null 2>&1 || true

echo "[restore] importing $FILE ..."
gunzip -c "$FILE" | $COMPOSE exec -T postgres psql -U aeon -d aeon -v ON_ERROR_STOP=1

echo "[restore] restarting stack..."
$COMPOSE start backend web >/dev/null 2>&1 || $COMPOSE up -d backend web

echo "[restore] done. Verify: curl --fail http://localhost/health"
