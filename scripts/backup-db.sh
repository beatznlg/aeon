#!/usr/bin/env sh
# AEON OS — PostgreSQL backup (run on the Oracle VM).
# ===================================================
# Dumps the aeon database to a gzipped archive OUTSIDE the containers so
# backups survive rebuilds and are trivially copyable off-box.
#
# Usage:
#   sudo sh scripts/backup-db.sh                      # default dir /opt/aeon/backups
#   sudo AEON_BACKUP_KEEP=30 sh scripts/backup-db.sh  # custom retention
#
# Retention: keeps the newest AEON_BACKUP_KEEP archives (default 14). Manual
# .sql files are never pruned automatically.
set -eu

APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
BACKUP_DIR="${1:-${AEON_BACKUP_DIR:-$APP_DIR/backups}}"
KEEP="${AEON_BACKUP_KEEP:-14}"
COMPOSE="docker compose -f $APP_DIR/docker-compose.oci.yml"

[ "$(id -u)" = 0 ] || { echo "Run with sudo (writes the host backup directory)."; exit 1; }
mkdir -p "$BACKUP_DIR"

TS=$(date -u +%Y%m%d-%H%M%S)
FILE="$BACKUP_DIR/aeon-$TS.sql.gz"

echo "[backup] dumping aeon database -> $FILE"
$COMPOSE exec -T postgres pg_dump -U aeon --clean --if-exists aeon | gzip > "$FILE"

[ -s "$FILE" ] || { echo "[backup] ERROR: dump is empty — not replacing anything" >&2; rm -f "$FILE"; exit 1; }
echo "[backup] wrote $(du -h "$FILE" | cut -f1)"

# Retention: prune oldest archives beyond the keep count.
if [ "$KEEP" -gt 0 ]; then
    ls -1t "$BACKUP_DIR"/aeon-*.sql.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
        rm -f "$old"
        echo "[backup] pruned $old (retention $KEEP)"
    done
fi

echo "[backup] done — restore with: sudo sh scripts/restore-db.sh $FILE"
