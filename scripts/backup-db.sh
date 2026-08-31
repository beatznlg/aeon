#!/usr/bin/env sh
# AEON OS — PostgreSQL backup on the Oracle VM.
# Local backups are retained; set S3-compatible variables for off-host copies.
set -eu
APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
BACKUP_DIR="${1:-${AEON_BACKUP_DIR:-$APP_DIR/backups}}"
KEEP="${AEON_BACKUP_KEEP:-14}"
COMPOSE="docker compose -f $APP_DIR/docker-compose.oci.yml"
[ "$(id -u)" = 0 ] || { echo "Run with sudo."; exit 1; }
mkdir -p "$BACKUP_DIR"
TS=$(date -u +%Y%m%d-%H%M%S)
FILE="$BACKUP_DIR/aeon-$TS.sql.gz"
$COMPOSE exec -T postgres pg_dump -U aeon --clean --if-exists aeon | gzip -9 > "$FILE"
[ -s "$FILE" ] || { echo "ERROR: empty dump" >&2; rm -f "$FILE"; exit 1; }
chmod 600 "$FILE"
echo "[backup] wrote $(du -h "$FILE" | cut -f1)"

# Optional S3-compatible off-host copy. OCI Object Storage can be used with
# its S3 compatibility endpoint by setting AWS_ENDPOINT_URL, AWS_ACCESS_KEY_ID,
# AWS_SECRET_ACCESS_KEY, AWS_REGION and AWS_S3_BUCKET.
if [ -n "${AWS_S3_BUCKET:-}" ]; then
  : "${AWS_ENDPOINT_URL:?AWS_ENDPOINT_URL required for off-host backup}"
  : "${AWS_REGION:?AWS_REGION required for off-host backup}"
  : "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID required for off-host backup}"
  : "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY required for off-host backup}"
  command -v aws >/dev/null 2>&1 || { echo "aws CLI required for off-host backup" >&2; exit 1; }
  aws s3 cp "$FILE" "s3://${AWS_S3_BUCKET}/aeon/postgres/$(basename "$FILE")" \
    --endpoint-url "$AWS_ENDPOINT_URL" --region "$AWS_REGION" --only-show-errors
  echo "[backup] off-host copy complete"
fi

if [ "$KEEP" -gt 0 ]; then
  ls -1t "$BACKUP_DIR"/aeon-*.sql.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
    rm -f "$old"
  done
fi
echo "[backup] done — restore with: sudo sh scripts/restore-db.sh $FILE"
