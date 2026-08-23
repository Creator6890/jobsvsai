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
# Verify against a real file inside the container rather than piping the archive to
# pg_restore's stdin: a pipe is not seekable, and on some Docker hosts binary stdin is
# mangled in transit, which fails a perfectly good dump.
verify_path="/tmp/verify-$(basename "$target")"
# Git Bash rewrites a bare /tmp/... argument into a Windows path. It leaves "service:/path"
# alone, and it leaves a doubled leading slash alone, so `cp` takes the single-slash form
# and `exec` takes the doubled one. Linux treats //tmp and /tmp identically.
verify_path_exec="/$verify_path"
verify_ok=1
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES cp "$target" "postgres:$verify_path" >/dev/null 2>&1 || verify_ok=0
if [ "$verify_ok" -eq 1 ]; then
  # shellcheck disable=SC2086
  docker compose $COMPOSE_FILES exec -T postgres pg_restore --list "$verify_path_exec" >/dev/null 2>&1 || verify_ok=0
fi
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES exec -T postgres rm -f "$verify_path_exec" >/dev/null 2>&1 || true

if [ "$verify_ok" -ne 1 ]; then
  # Quarantine rather than delete. An unverified archive may still be restorable, and a
  # backup script that destroys its own output on a false negative is worse than useless.
  mv "$target" "$target.unverified"
  echo "!! Archive failed verification. Kept for inspection: $target.unverified" >&2
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
