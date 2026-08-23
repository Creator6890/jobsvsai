#!/usr/bin/env bash
# First-time production bring-up.
#
#   ./scripts/deploy.sh --restore /var/backups/jobsvsai/jobsvsai.dump
#
# Order matters and is enforced, not merely documented:
#
#   1. validate .env and build images
#   2. start PostgreSQL and Redis ONLY
#   3. restore the transferred dump into the empty database
#   4. baseline migration history, then apply anything still pending
#   5. verify row counts and the active scoring model
#   6. start backend, worker, frontend and Caddy
#   7. full health check
#
# The application tier is not started until the database has been verified. A public site
# serving an empty database would publish zero occupations under a live domain, and search
# engines are quick to notice.
#
# For routine releases use scripts/update.sh instead; this script is for a new host.
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
export COMPOSE_FILES

# The verified state this deployment expects to find once the dump is restored. Override
# only when the source database has legitimately moved on.
EXPECT_PUBLIC="${EXPECT_PUBLIC:-507}"
EXPECT_SCORES="${EXPECT_SCORES:-507}"
EXPECT_ACTIVE_MODEL="${EXPECT_ACTIVE_MODEL:-JVS 1.0.3}"
EXPECT_INACTIVE_MODEL="${EXPECT_INACTIVE_MODEL:-JVS 2.0.0-phase4b}"

RESTORE_FROM=""
ALLOW_EMPTY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --restore) RESTORE_FROM="${2:?--restore needs a path}"; shift 2 ;;
    --allow-empty-database) ALLOW_EMPTY=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

# shellcheck disable=SC2086
dc() { docker compose $COMPOSE_FILES "$@"; }
psqlq() { dc exec -T postgres psql -U "${POSTGRES_USER:-jobsvsai}" -d "${POSTGRES_DB:-jobsvsai}" -qtAX "$@"; }

# ---------------------------------------------------------------- 1. configuration
[ -f .env ] || { echo "!! .env is missing. Copy .env.production.example to .env." >&2; exit 1; }
set -a && . ./.env && set +a

echo "==> Checking required settings"
missing=()
for var in SITE_DOMAIN API_DOMAIN LETSENCRYPT_EMAIL POSTGRES_PASSWORD DATABASE_URL \
           ADMIN_PASSWORD NEXT_PUBLIC_SITE_URL NEXT_PUBLIC_API_URL CORS_ORIGINS ENVIRONMENT; do
  [ -n "${!var:-}" ] || missing+=("$var")
done
[ "${#missing[@]}" -eq 0 ] || { printf '!! Missing in .env: %s\n' "${missing[*]}" >&2; exit 1; }
case "${POSTGRES_PASSWORD}${ADMIN_PASSWORD}" in
  *replace-with*|*change-me*) echo "!! Placeholder credentials still present in .env." >&2; exit 1 ;;
esac
[ "$ENVIRONMENT" = "production" ] || {
  echo "!! ENVIRONMENT must be 'production' or the data console runs without auth." >&2; exit 1; }

if [ -z "$RESTORE_FROM" ] && [ "$ALLOW_EMPTY" -eq 0 ]; then
  cat >&2 <<'NEED'
!! No database dump given.

   A new host starts with an empty database. Migrations create the schema and seed
   reference data, but the O*NET corpus, the scores and the published occupations are
   data, not code — restoring them is a required step, not an optional one.

     ./scripts/deploy.sh --restore /var/backups/jobsvsai/jobsvsai.dump

   To stand up an intentionally empty instance (no public site), pass
   --allow-empty-database.
NEED
  exit 1
fi
[ -z "$RESTORE_FROM" ] || [ -f "$RESTORE_FROM" ] || {
  echo "!! Dump not found: $RESTORE_FROM" >&2; exit 1; }

echo "==> Building images (NEXT_PUBLIC_* are compiled in at build time)"
dc build --pull

# ---------------------------------------------------------------- 2. datastores only
echo "==> Starting PostgreSQL and Redis only"
dc up -d postgres redis

echo "==> Waiting for PostgreSQL"
for _ in $(seq 1 60); do
  dc exec -T postgres pg_isready -U "${POSTGRES_USER:-jobsvsai}" >/dev/null 2>&1 && break
  sleep 2
done
dc exec -T postgres pg_isready -U "${POSTGRES_USER:-jobsvsai}" >/dev/null 2>&1 || {
  echo "!! PostgreSQL did not become ready." >&2; exit 1; }

# ---------------------------------------------------------------- 3. restore
table_count() {
  psqlq -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" \
    2>/dev/null | tr -d '\r ' || echo 0
}

if [ -n "$RESTORE_FROM" ]; then
  existing="$(table_count)"
  if [ "${existing:-0}" -gt 0 ] 2>/dev/null; then
    echo "!! Target database already has $existing tables; this script restores into an" >&2
    echo "   empty one. Use scripts/restore-db.sh, which handles a populated database." >&2
    exit 1
  fi
  echo "==> Restoring $RESTORE_FROM into the empty database"
  ./scripts/restore-db.sh --into-empty "$RESTORE_FROM"
fi

# ---------------------------------------------------------------- 4. migrations
echo "==> Reconciling migration history"
tables="$(table_count)"
tracked="$(psqlq -c "SELECT to_regclass('public.schema_migrations') IS NOT NULL;" 2>/dev/null | tr -d '\r ' || echo f)"
if [ "${tables:-0}" -gt 5 ] 2>/dev/null && [ "$tracked" != "t" ]; then
  echo "    Restored schema with no migration history: baselining, then applying any newer."
  ./scripts/migrate.sh --baseline
fi
./scripts/migrate.sh

# ---------------------------------------------------------------- 5. verify data
echo "==> Verifying database state before exposing it"
read -r pub scores active inactive_ok < <(psqlq -F' ' -c "
  SELECT (SELECT count(*) FROM occupation_publications WHERE activation_status='public'),
         (SELECT count(*) FROM current_production_occupation_scores),
         (SELECT version FROM scoring_model_versions WHERE is_active),
         (SELECT CASE WHEN EXISTS (SELECT 1 FROM scoring_model_versions
            WHERE version='${EXPECT_INACTIVE_MODEL}' AND is_active) THEN 'no' ELSE 'yes' END);
" 2>/dev/null | tr -d '\r' || echo "0 0 none no")

echo "    public occupations : $pub"
echo "    live scores        : $scores"
echo "    active model       : $active"
echo "    ${EXPECT_INACTIVE_MODEL} inactive : $inactive_ok"

fatal=0
if [ "$ALLOW_EMPTY" -eq 0 ]; then
  [ "${pub:-0}" = "$EXPECT_PUBLIC" ] || { echo "!! expected $EXPECT_PUBLIC public occupations" >&2; fatal=1; }
  [ "${scores:-0}" = "$EXPECT_SCORES" ] || { echo "!! expected $EXPECT_SCORES live scores" >&2; fatal=1; }
fi
[ "$active" = "$EXPECT_ACTIVE_MODEL" ] || {
  echo "!! active scoring model is '$active', expected '$EXPECT_ACTIVE_MODEL'" >&2; fatal=1; }
[ "$inactive_ok" = "yes" ] || {
  echo "!! ${EXPECT_INACTIVE_MODEL} must not be active" >&2; fatal=1; }

if [ "$fatal" -ne 0 ]; then
  echo "!! Refusing to start the public application against unexpected data." >&2
  echo "   Nothing beyond PostgreSQL and Redis is running; fix the data and re-run." >&2
  exit 1
fi

if [ "$ALLOW_EMPTY" -eq 1 ] && [ "${pub:-0}" -eq 0 ] 2>/dev/null; then
  echo "    (--allow-empty-database: starting with no public occupations, as requested)"
fi

# ---------------------------------------------------------------- 6. application
echo "==> Starting backend, worker, frontend and Caddy"
dc up -d

echo "==> Waiting for services to report healthy"
for _ in $(seq 1 60); do
  unhealthy="$(dc ps --format '{{.Service}} {{.Health}}' | awk '$2!="healthy" && $2!="" {print $1}' | xargs)"
  [ -z "$unhealthy" ] && break
  sleep 5
done
[ -n "${unhealthy:-}" ] && echo "    Still not healthy: $unhealthy"

# ---------------------------------------------------------------- 7. health check
echo "==> Health check"
./scripts/healthcheck.sh || {
  echo "!! Health check failed. Inspect: docker compose $COMPOSE_FILES logs --tail 100" >&2
  exit 1
}

cat <<DONE

==> Deployed. https://${SITE_DOMAIN}
    Certificates are issued on first request and may take ~30s.

    Schedule backups:
      15 3 * * * cd $(pwd) && ./scripts/backup-db.sh >> /var/log/jobsvsai-backup.log 2>&1
DONE
