#!/usr/bin/env bash
# Run the test suite against the isolated test database, never the development database.
#
# Prints the resolved host, database name and environment before pytest opens a connection,
# so the target is visible in the log of every run. Credentials are never printed.
set -euo pipefail
cd "$(dirname "$0")/.."

TEST_DB="${TEST_POSTGRES_DB:-jobsvsai_test}"
DB_USER="${POSTGRES_USER:-jobsvsai}"
DB_PASSWORD="${POSTGRES_PASSWORD:-}"
if [ -z "$DB_PASSWORD" ] && [ -f .env ]; then
  DB_PASSWORD="$(grep -E '^POSTGRES_PASSWORD=' .env | head -1 | cut -d= -f2-)"
fi

TEST_DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/${TEST_DB}"

echo "=============================================="
echo " pytest target verification"
echo "=============================================="
echo " hostname    : postgres"
echo " database    : ${TEST_DB}"
echo " environment : test"
echo " marker      : TEST_DATABASE=true"
echo "=============================================="

# The guard's own checks, run standalone before pytest so an unsafe target is reported
# plainly rather than as a collection error.
docker compose run --rm --no-deps \
  -e DATABASE_URL="$TEST_DATABASE_URL" \
  -e ENVIRONMENT=test \
  -e TEST_DATABASE=true \
  -v "$PWD/backend/tests:/app/tests:ro" \
  backend python -c "
from tests.db_guard import resolve_target
target = resolve_target()
print('guard: accepted ->', target.describe())
"

docker compose run --rm \
  -e DATABASE_URL="$TEST_DATABASE_URL" \
  -e ENVIRONMENT=test \
  -e TEST_DATABASE=true \
  -v "$PWD/backend/tests:/app/tests:ro" \
  backend python -m pytest tests "$@"
