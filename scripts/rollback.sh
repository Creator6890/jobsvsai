#!/usr/bin/env bash
# Roll the application back to the images recorded by the last scripts/update.sh run.
#
#   ./scripts/rollback.sh          ask for confirmation
#   ./scripts/rollback.sh --auto   no prompt (used by update.sh when health fails)
#
# Scope, stated plainly: this rolls back CODE, not the database. Schema migrations are
# forward-only by design — a migration that has been applied stays applied, because
# reversing DDL against live data loses information. If a release shipped a bad migration,
# roll the code back with this script and then restore the pre-update backup that
# update.sh took, using scripts/restore-db.sh.
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
export COMPOSE_FILES
STATE_FILE=".deploy-state"

[ -f .env ] && set -a && . ./.env && set +a

if [ ! -f "$STATE_FILE" ]; then
  echo "!! No $STATE_FILE — nothing recorded to roll back to." >&2
  echo "   Recover by checking out the previous revision and running ./scripts/deploy.sh" >&2
  exit 1
fi

echo "==> Rollback target:"
sed 's/^/    /' "$STATE_FILE"

missing=0
while read -r svc image_id; do
  [ "$svc" = "revision" ] && continue
  if ! docker image inspect "$image_id" >/dev/null 2>&1; then
    echo "!! Image for $svc ($image_id) is no longer on disk." >&2
    missing=1
  fi
done < "$STATE_FILE"
[ "$missing" -eq 1 ] && { echo "   Rebuild from the previous git revision instead." >&2; exit 1; }

if [ "${1:-}" != "--auto" ]; then
  read -r -p "Roll back to these images? [y/N] " reply
  case "$reply" in [yY]*) ;; *) echo "Aborted."; exit 1 ;; esac
fi

# Re-tag the recorded image IDs to the names compose expects, then recreate the containers
# so they pick the retagged images up.
while read -r svc image_id; do
  [ "$svc" = "revision" ] && continue
  echo "==> Restoring $svc -> $image_id"
  docker tag "$image_id" "jobsvsai-$svc:latest"
done < "$STATE_FILE"

# shellcheck disable=SC2086
docker compose $COMPOSE_FILES up -d --force-recreate --no-build backend worker frontend

echo "==> Waiting for health"
sleep 10
for _ in $(seq 1 36); do
  unhealthy="$(docker compose $COMPOSE_FILES ps --format '{{.Service}} {{.Health}}' \
    | awk '$2!="healthy" && $2!="" {print $1}' | tr '\n' ' ')"
  [ -z "$unhealthy" ] && break
  sleep 5
done

if ./scripts/healthcheck.sh; then
  echo
  echo "==> Rolled back to $(awk '/^revision/{print $2}' "$STATE_FILE")."
  echo "    If the failed release included a migration, restore the pre-update backup:"
  echo "      ./scripts/restore-db.sh \$(ls -1t \${BACKUP_DIR:-/var/backups/jobsvsai}/jobsvsai-*.dump | head -1)"
else
  echo "!! Rollback did not restore health. Check: docker compose $COMPOSE_FILES logs --tail 200" >&2
  exit 1
fi
