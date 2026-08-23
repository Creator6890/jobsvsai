#!/usr/bin/env bash
# Routine release: back up, record the current images, rebuild, migrate, restart, verify.
# If verification fails it rolls back automatically to the images recorded at the start.
#
#   ./scripts/update.sh            build and deploy the working tree as-is
#   ./scripts/update.sh --pull     git pull first, then build and deploy
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
export COMPOSE_FILES
STATE_FILE=".deploy-state"
SERVICES="backend worker frontend"

[ -f .env ] || { echo "!! .env is missing." >&2; exit 1; }
set -a && . ./.env && set +a

if [ "${1:-}" = "--pull" ]; then
  echo "==> Pulling latest revision"
  git pull --ff-only
fi
revision="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

echo "==> Backing up the database before changing anything"
./scripts/backup-db.sh

echo "==> Recording current images for rollback"
: > "$STATE_FILE"
for svc in $SERVICES; do
  # shellcheck disable=SC2086
  image_id="$(docker compose $COMPOSE_FILES images -q "$svc" 2>/dev/null | head -1)"
  [ -n "$image_id" ] && echo "$svc $image_id" >> "$STATE_FILE"
done
echo "revision $revision" >> "$STATE_FILE"
cat "$STATE_FILE" | sed 's/^/    /'

echo "==> Building $revision"
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES build --pull

echo "==> Applying database migrations"
./scripts/migrate.sh

echo "==> Restarting services"
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES up -d --remove-orphans

echo "==> Waiting for health"
sleep 10
for _ in $(seq 1 48); do
  unhealthy="$(docker compose $COMPOSE_FILES ps --format '{{.Service}} {{.Health}}' \
    | awk '$2!="healthy" && $2!="" {print $1}' | tr '\n' ' ')"
  [ -z "$unhealthy" ] && break
  sleep 5
done

if ./scripts/healthcheck.sh; then
  echo
  echo "==> Update to $revision complete."
  echo "    Previous images are still on disk; scripts/rollback.sh can restore them."
else
  echo
  echo "!! Health check failed after update. Rolling back." >&2
  ./scripts/rollback.sh --auto
  exit 1
fi
