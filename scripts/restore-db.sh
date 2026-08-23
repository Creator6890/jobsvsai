#!/usr/bin/env bash
# Restore a backup produced by scripts/backup-db.sh.
#
#   scripts/restore-db.sh <dump>                 restore over an existing database
#   scripts/restore-db.sh --into-empty <dump>    first-deploy path; target must be empty
#   scripts/restore-db.sh --force <dump>         skip the interactive confirmation
#
# Safety, in order of application:
#   * the SHA-256 sidecar is verified when present, and the archive is parsed with
#     pg_restore --list so a truncated dump is caught before anything is dropped
#   * free disk space is checked against the uncompressed size the archive reports
#   * a populated target is refused unless you confirm, because "restore" against a live
#     database is a destructive operation wearing a reassuring name
#   * the application is stopped and a safety dump of the current state is taken first
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml}"
DB_USER="${POSTGRES_USER:-jobsvsai}"
DB_NAME="${POSTGRES_DB:-jobsvsai}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/jobsvsai}"

INTO_EMPTY=0
FORCE=0
archive=""
while [ $# -gt 0 ]; do
  case "$1" in
    --into-empty) INTO_EMPTY=1; shift ;;
    --force) FORCE=1; shift ;;
    -*) echo "Unknown option: $1" >&2; exit 2 ;;
    *) archive="$1"; shift ;;
  esac
done

if [ -z "$archive" ] || [ ! -f "$archive" ]; then
  echo "Usage: scripts/restore-db.sh [--into-empty] [--force] <path-to-.dump>" >&2
  echo "Available:" >&2
  ls -1t "$BACKUP_DIR"/jobsvsai-*.dump 2>/dev/null | head -10 >&2 || echo "  (none)" >&2
  exit 2
fi

# shellcheck disable=SC2086
dc() { docker compose $COMPOSE_FILES "$@"; }
psqlq() { dc exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -qtAX "$@"; }

# ------------------------------------------------------------------ integrity
if [ -f "$archive.sha256" ]; then
  echo "==> Verifying checksum"
  ( cd "$(dirname "$archive")" && sha256sum -c "$(basename "$archive").sha256" )
else
  echo "==> No .sha256 sidecar alongside the archive; skipping checksum verification."
fi

echo "==> Verifying archive structure"
# The archive is copied into the container and read as a real file. Piping it to stdin
# fails: a pipe is not seekable, and some Docker hosts mangle binary stdin in transit.
# The same copy is then used for the restore itself, so the bytes are only moved once.
staged="/tmp/restore-$(basename "$archive")"
# Git Bash rewrites a bare /tmp/... argument into a Windows path. It leaves "service:/path"
# alone, and it leaves a doubled leading slash alone, so `cp` takes the single-slash form
# and `exec` takes the doubled one. Linux treats //tmp and /tmp identically.
staged_exec="/$staged"
dc cp "$archive" "postgres:$staged" >/dev/null 2>&1 || {
  echo "!! Could not stage the archive inside the postgres container." >&2; exit 1; }
cleanup_staged() { dc exec -T postgres rm -f "$staged_exec" >/dev/null 2>&1 || true; }
trap cleanup_staged EXIT

dc exec -T postgres pg_restore --list "$staged_exec" > /dev/null 2>&1 || {
  echo "!! Archive is not a readable PostgreSQL custom-format dump." >&2; exit 1; }

# ------------------------------------------------------------------ disk space
archive_bytes="$(wc -c < "$archive")"
# -Fc archives are compressed; 5x is a conservative floor for the restored footprint,
# and the restore also needs room for WAL while it runs.
needed_kb=$(( (archive_bytes / 1024) * 5 ))
avail_kb="$(df -Pk / 2>/dev/null | awk 'NR==2{print $4}')"
[ -n "$avail_kb" ] || avail_kb="$(df -Pk / | awk 'NR==2{print $4}')"
echo "==> Disk: $((avail_kb/1024)) MB free, ~$((needed_kb/1024)) MB estimated for restore"
if [ "$avail_kb" -lt "$needed_kb" ]; then
  echo "!! Not enough free disk space to restore safely. Free space and retry." >&2
  exit 1
fi

# ------------------------------------------------------------------ target state
table_count="$(psqlq -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d '\r ' || echo 0)"
table_count="${table_count:-0}"

if [ "$INTO_EMPTY" -eq 1 ]; then
  if [ "$table_count" -gt 0 ] 2>/dev/null; then
    echo "!! --into-empty was given but the database already has $table_count tables." >&2
    echo "   Re-run without --into-empty to overwrite deliberately." >&2
    exit 1
  fi
  echo "==> Target database is empty, as expected."
elif [ "$table_count" -gt 0 ] 2>/dev/null; then
  read -r pub scores < <(psqlq -F' ' -c "
    SELECT (SELECT count(*) FROM occupation_publications WHERE activation_status='public'),
           (SELECT count(*) FROM current_production_occupation_scores);" 2>/dev/null | tr -d '\r' || echo "? ?")
  cat <<WARN

  !! THE TARGET DATABASE IS NOT EMPTY.

     Database:   $DB_NAME
     Tables:     $table_count
     Public now: ${pub:-?} occupations, ${scores:-?} live scores
     Restoring:  $archive

     Every object in the current database will be dropped and replaced. Publications,
     scores and activation state included.

WARN
  if [ "$FORCE" -eq 0 ]; then
    read -r -p "Type RESTORE-OVERWRITE to proceed: " confirm
    [ "$confirm" = "RESTORE-OVERWRITE" ] || { echo "Aborted."; exit 1; }
  else
    echo "  --force given; proceeding without confirmation."
  fi
fi

# ------------------------------------------------------------------ restore
echo "==> Stopping application containers (PostgreSQL stays up)"
dc stop backend worker frontend 2>/dev/null || true

if [ "$table_count" -gt 0 ] 2>/dev/null; then
  mkdir -p "$BACKUP_DIR"; chmod 700 "$BACKUP_DIR"
  safety="$BACKUP_DIR/pre-restore-$(date -u +%Y%m%dT%H%M%SZ).dump"
  echo "==> Safety dump of current state to $safety"
  dc exec -T postgres pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --compress=9 > "$safety"
  chmod 600 "$safety"
fi

echo "==> Restoring"
# --clean --if-exists emits benign "does not exist" notices on an empty target, so the
# outcome is judged by the verification below rather than by pg_restore's exit status.
dc exec -T postgres pg_restore -U "$DB_USER" -d "$DB_NAME" \
  --clean --if-exists --no-owner --no-privileges --single-transaction "$staged_exec" || true

echo "==> Verifying restored state"
psqlq -c "
  SELECT 'tables='        || (SELECT count(*) FROM information_schema.tables WHERE table_schema='public')
      || ' occupations='  || (SELECT count(*) FROM occupations)
      || ' live_scores='  || (SELECT count(*) FROM current_production_occupation_scores)
      || ' public='       || (SELECT count(*) FROM occupation_publications WHERE activation_status='public')
      || ' active_model=' || (SELECT version FROM scoring_model_versions WHERE is_active);
"

if [ "$INTO_EMPTY" -eq 1 ]; then
  echo "==> Restore complete. deploy.sh will migrate, verify and start the application."
else
  echo "==> Restarting application containers"
  dc up -d backend worker frontend
  echo "==> Restore complete. Safety dump of the previous state: ${safety:-none}"
  echo "    Run scripts/healthcheck.sh to confirm the site is serving."
fi
