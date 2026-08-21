#!/usr/bin/env bash
# Take a compressed, verified PostgreSQL backup and prune old ones.
#
# Custom format (-Fc) rather than plain SQL: it restores selectively, in parallel, and
# pg_restore can list its contents, which is how the integrity check below works without
# actually restoring anything.
#
# Cron (daily 03:15, log to syslog):
#   15 3 * * * cd /opt/jobsvsai && ./scripts/backup-db.sh >> /var/log/jobsvsai-backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml}"
DB_USER="${POSTGRES_USER:-jobsvsai}"
DB_NAME="${POSTGRES_DB:-jobsvsai}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/jobsvsai}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/jobsvsai-$stamp.dump"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# Refuse to start a dump that cannot finish. The live database is several GB; a -Fc dump
# compresses to roughly a tenth of that, so require 25% of the database size as headroom.
db_bytes="$(docker compose $COMPOSE_FILES exec -T postgres psql -U "$DB_USER" -d "$DB_NAME"   -qtAX -c "SELECT pg_database_size('$DB_NAME');" 2>/dev/null | tr -d ' ' || echo 0)"
needed_kb=$(( (${db_bytes:-0} / 1024) / 4 ))
avail_kb="$(df -Pk "$BACKUP_DIR" | awk 'NR==2{print $4}')"
echo "==> Disk: $((avail_kb/1024)) MB free at $BACKUP_DIR, ~$((needed_kb/1024)) MB estimated"
if [ "${needed_kb:-0}" -gt 0 ] && [ "$avail_kb" -lt "$needed_kb" ]; then
  echo "!! Not enough free space for a backup. Prune old archives or grow the volume." >&2
  exit 1
fi

echo "==> Backing up $DB_NAME to $target"
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES exec -T postgres \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --compress=9 > "$target.partial"

# Only promote to a real backup filename once the dump completed. A partial file with a
# valid name is worse than no file, because it looks restorable.
mv "$target.partial" "$target"
chmod 600 "$target"

echo "==> Verifying archive is readable"
if ! docker compose $COMPOSE_FILES exec -T postgres pg_restore --list /dev/stdin < "$target" >/dev/null 2>&1; then
  echo "!! Backup failed verification and has been removed: $target" >&2
  rm -f "$target"
  exit 1
fi

sha256sum "$target" > "$target.sha256"
size="$(du -h "$target" | cut -f1)"
echo "==> OK: $target ($size)"

echo "==> Pruning backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name 'jobsvsai-*.dump' -type f -mtime "+$RETENTION_DAYS" -print -delete
find "$BACKUP_DIR" -name 'jobsvsai-*.dump.sha256' -type f -mtime "+$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name '*.partial' -type f -mtime +1 -delete

remaining="$(find "$BACKUP_DIR" -name 'jobsvsai-*.dump' -type f | wc -l)"
echo "==> $remaining backup(s) retained in $BACKUP_DIR"
