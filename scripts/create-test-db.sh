#!/usr/bin/env bash
# Create (or recreate) the isolated pytest database.
#
# The test suite writes: fixture promotion runs, production snapshots, factor and task
# contributions, canonical identities, and it flips publication rows to exercise the
# publication gate. None of that may touch the development database, which holds the
# promoted Phase 6 state. This script builds a disposable database and stamps it with the
# marker table that backend/tests/db_guard.py insists on seeing.
#
# Two modes:
#   --template    (default) file-level copy of the development database. Fast, and the
#                 suite's full baseline passes because the O*NET import and the Phase 4/5/6
#                 runs come along. Requires no client connected to the source database, so
#                 the script stops the app services and restarts them afterwards.
#   --migrations  apply migrations/*.sql to an empty database. No source data, nothing read
#                 from the development database at all. Expect the documented subset of
#                 failures for tests that need ingested O*NET and phase runs.
#
# The development database is only ever READ by this script (and not even read in
# --migrations mode). It is never written.
set -euo pipefail

MODE="template"
case "${1:-}" in
  --template) MODE="template" ;;
  --migrations) MODE="migrations" ;;
  "") ;;
  *) echo "usage: $0 [--template|--migrations]" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."

SOURCE_DB="${POSTGRES_DB:-jobsvsai}"
TEST_DB="${TEST_POSTGRES_DB:-jobsvsai_test}"
DB_USER="${POSTGRES_USER:-jobsvsai}"

case "$TEST_DB" in
  *_test|test_*|*_test_*) ;;
  *) echo "refusing: TEST_POSTGRES_DB='$TEST_DB' does not identify itself as a test database" >&2
     exit 1 ;;
esac
if [ "$TEST_DB" = "$SOURCE_DB" ]; then
  echo "refusing: test database and source database are both '$TEST_DB'" >&2
  exit 1
fi

psql_super() {
  docker compose exec -T postgres psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 "$@"
}
psql_test() {
  docker compose exec -T postgres psql -U "$DB_USER" -d "$TEST_DB" -v ON_ERROR_STOP=1 "$@"
}

echo "==> target test database: $TEST_DB (source: $SOURCE_DB, mode: $MODE)"

# Drop any previous test database. FORCE terminates its own connections only; the source
# database is untouched by this.
echo "==> dropping $TEST_DB if it exists"
psql_super -c "DROP DATABASE IF EXISTS ${TEST_DB} WITH (FORCE);"

if [ "$MODE" = "template" ]; then
  # CREATE DATABASE ... TEMPLATE requires zero other sessions on the source. Stop the
  # services that hold pools; they are restarted at the end. This disconnects clients, it
  # does not modify data.
  echo "==> stopping app services so the source database has no connections"
  docker compose stop backend worker frontend >/dev/null 2>&1 || true

  # Anything left over (a stray psql, a previous run) is terminated - again, source data is
  # not modified by dropping a connection.
  psql_super -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                 WHERE datname='${SOURCE_DB}' AND pid <> pg_backend_pid();" >/dev/null

  echo "==> cloning $SOURCE_DB -> $TEST_DB (read-only on the source)"
  psql_super -c "CREATE DATABASE ${TEST_DB} TEMPLATE ${SOURCE_DB} OWNER ${DB_USER};"

  echo "==> restarting app services"
  docker compose start backend worker frontend >/dev/null
else
  echo "==> creating empty $TEST_DB and applying migrations"
  psql_super -c "CREATE DATABASE ${TEST_DB} OWNER ${DB_USER};"
  for file in migrations/*.sql; do
    echo "    $file"
    docker compose exec -T postgres psql -U "$DB_USER" -d "$TEST_DB" -v ON_ERROR_STOP=1 \
      -q -f "/docker-entrypoint-initdb.d/$(basename "$file")"
  done
fi

# The marker. db_guard.py check 4 reads this and it is the only check an environment
# variable cannot fake.
echo "==> stamping the test-database marker"
psql_test <<SQL
CREATE TABLE IF NOT EXISTS test_database_marker (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  label      text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE test_database_marker IS
  'Present only in a disposable pytest database. backend/tests/db_guard.py refuses to run against a database without it.';
INSERT INTO test_database_marker (label)
VALUES ('${TEST_DB} created by scripts/create-test-db.sh mode=${MODE}');
SQL

echo
echo "==> done. $TEST_DB is ready."
psql_test -c "SELECT label, created_at FROM test_database_marker ORDER BY created_at DESC LIMIT 1;"
echo "Run the suite with:  ./scripts/run-tests.sh"
