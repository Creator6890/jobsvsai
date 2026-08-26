#!/usr/bin/env bash
# Apply pending SQL migrations to a live database, safely and idempotently.
#
# Why this exists: migrations were previously applied only by PostgreSQL's
# docker-entrypoint-initdb.d hook, which runs *once*, when the data directory is first
# created. On any database that already holds data — which is every production database
# after day one — there was no path to apply a new migration at all. Locally this had
# already gone wrong: 025-028 existed in the repository but had never been applied.
#
# Guarantees:
#   * every migration runs at most once, tracked in schema_migrations
#   * files are applied in lexical order (001_, 002_, ...)
#   * a file that declares its own BEGIN/COMMIT manages its own transaction; one that does
#     not is wrapped in a single transaction so a mid-file failure rolls back cleanly
#   * a checksum change on an already-applied migration is reported and refuses to proceed,
#     because editing applied history silently is how environments drift apart
#   * nothing is ever dropped, truncated or re-run
#
# Usage:
#   scripts/migrate.sh                 apply pending migrations
#   scripts/migrate.sh --dry-run       list what would be applied, change nothing
#   scripts/migrate.sh --baseline      record every migration as applied WITHOUT running it
#                                      (use once, on a database whose schema is already
#                                       current — e.g. one built by the old initdb hook)
#   scripts/migrate.sh --status        show applied vs pending
#
# COMPOSE_FILES may be overridden to target production:
#   COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" scripts/migrate.sh
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml}"
DB_USER="${POSTGRES_USER:-jobsvsai}"
DB_NAME="${POSTGRES_DB:-jobsvsai}"
MIGRATIONS_DIR="migrations"
MODE="apply"

case "${1:-}" in
  --dry-run) MODE="dry-run" ;;
  --baseline) MODE="baseline" ;;
  --status) MODE="status" ;;
  "") ;;
  *) echo "Unknown option: $1" >&2; exit 2 ;;
esac

# shellcheck disable=SC2086
psql_run() { docker compose $COMPOSE_FILES exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" "$@"; }

psql_quiet() { psql_run -v ON_ERROR_STOP=1 -qtAX "$@"; }

echo "==> Ensuring schema_migrations exists"
psql_quiet -c "
  CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   TEXT PRIMARY KEY,
    checksum   TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_by TEXT NOT NULL DEFAULT current_user
  );
  COMMENT ON TABLE schema_migrations IS
    'One row per applied SQL migration. Written by scripts/migrate.sh; never edit by hand.';
" >/dev/null

applied_list="$(psql_quiet -c "SELECT filename FROM schema_migrations ORDER BY filename;")"
is_applied() { printf '%s\n' "$applied_list" | grep -Fxq "$1"; }
recorded_checksum() {
  psql_quiet -c "SELECT checksum FROM schema_migrations WHERE filename = '$1';"
}

pending=()
drifted=()
for path in "$MIGRATIONS_DIR"/*.sql; do
  file="$(basename "$path")"
  sum="$(sha256sum "$path" | cut -d' ' -f1)"
  if is_applied "$file"; then
    if [ "$(recorded_checksum "$file")" != "$sum" ]; then drifted+=("$file"); fi
  else
    pending+=("$file")
  fi
done

if [ "${#drifted[@]}" -gt 0 ]; then
  echo "!! These migrations changed after being applied:" >&2
  printf '   %s\n' "${drifted[@]}" >&2
  echo "   Applied migrations are history. Add a new migration instead of editing one." >&2
  echo "   Refusing to continue." >&2
  exit 1
fi

if [ "$MODE" = "status" ]; then
  echo "Applied: $(printf '%s\n' "$applied_list" | grep -c . || true)"
  echo "Pending: ${#pending[@]}"
  [ "${#pending[@]}" -gt 0 ] && printf '   %s\n' "${pending[@]}"
  exit 0
fi

if [ "${#pending[@]}" -eq 0 ]; then
  echo "==> Database is up to date; nothing to apply."
  exit 0
fi

echo "==> ${#pending[@]} pending migration(s):"
printf '   %s\n' "${pending[@]}"

if [ "$MODE" = "dry-run" ]; then
  echo "==> Dry run; nothing was applied."
  exit 0
fi

if [ "$MODE" = "baseline" ]; then
  echo "==> Baseline: recording as applied WITHOUT executing."
  for file in "${pending[@]}"; do
    sum="$(sha256sum "$MIGRATIONS_DIR/$file" | cut -d' ' -f1)"
    psql_quiet -c "INSERT INTO schema_migrations (filename, checksum) VALUES ('$file','$sum')
                   ON CONFLICT (filename) DO NOTHING;" >/dev/null
    echo "   baselined $file"
  done
  echo "==> Baseline complete."
  exit 0
fi

for file in "${pending[@]}"; do
  path="$MIGRATIONS_DIR/$file"
  sum="$(sha256sum "$path" | cut -d' ' -f1)"
  # A file that opens its own transaction must not be wrapped in another: psql's
  # --single-transaction would leave the inner COMMIT ending the outer one early.
  if grep -qiE '^[[:space:]]*BEGIN[[:space:]]*;' "$path"; then
    wrap=()
  else
    wrap=(--single-transaction)
  fi
  echo "==> Applying $file"
  # shellcheck disable=SC2086
  if ! docker compose $COMPOSE_FILES exec -T postgres \
        psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 ${wrap[@]+"${wrap[@]}"} -q < "$path"; then
    echo "!! $file failed. Database left as the migration itself determined." >&2
    echo "   Not recorded as applied; fix the migration and re-run." >&2
    exit 1
  fi
  psql_quiet -c "INSERT INTO schema_migrations (filename, checksum) VALUES ('$file','$sum');" >/dev/null
  echo "   applied $file"
done

echo "==> All migrations applied."
