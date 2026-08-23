#!/usr/bin/env bash
# Open a psql session against the development/production database with writes disabled.
#
# Use this for every verification, audit or investigation pass over the real database.
# `default_transaction_read_only=on` makes the server reject INSERT/UPDATE/DELETE/DDL for
# the whole session, so a mistyped query fails loudly instead of modifying the Phase 6
# state. It is a server-side guarantee, not a convention.
#
# For the test database use scripts/run-tests.sh; this script deliberately points at the
# real one and deliberately cannot write to it.
set -euo pipefail
cd "$(dirname "$0")/.."

DB_NAME="${POSTGRES_DB:-jobsvsai}"
DB_USER="${POSTGRES_USER:-jobsvsai}"

echo "read-only session -> database=${DB_NAME} (writes will be rejected by the server)" >&2
exec docker compose exec -T -e PGOPTIONS='-c default_transaction_read_only=on' postgres \
  psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 "$@"
