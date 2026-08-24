#!/usr/bin/env bash
# Scheduled AI News ingestion. Fetch feeds, deduplicate, score, store candidates.
#
# Calls no language model and creates no article: the ingest CLI imports neither the
# generation service nor a provider.
#
# Cron (every 6 hours, log to file):
#   0 */6 * * * cd /opt/jobsvsai && ./scripts/news-ingest.sh >> /var/log/jobsvsai-news.log 2>&1
#
# Exits non-zero on failure so cron reports it. Refusing because ingestion is disabled is
# NOT a failure - it is the configured state - and exits 0.
set -euo pipefail

cd "$(dirname "$0")/.."
# Load .env, but let an already-set environment variable win. `set -a; . ./.env` alone
# lets the file clobber the caller, which makes a one-off override impossible and — more
# quietly — makes these guards untestable from a shell. The file stays the default source
# of truth; an explicit override for a single run is respected.
_keep() { for _v in "$@"; do eval "_saved_$_v=\${$_v-}"; done; }
_restore() { for _v in "$@"; do eval "[ -n \"\$_saved_$_v\" ] && export $_v=\"\$_saved_$_v\"" || true; done; }
_keep NEWS_INGESTION_ENABLED NEWS_LOOKBACK_HOURS
[ -f .env ] && set -a && . ./.env && set +a
_restore NEWS_INGESTION_ENABLED NEWS_LOOKBACK_HOURS

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml}"
LOOKBACK="${NEWS_LOOKBACK_HOURS:-48}"

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
echo "==> [$(stamp)] news-ingest starting (lookback ${LOOKBACK}h)"

if [ "${NEWS_INGESTION_ENABLED:-false}" != "true" ]; then
  # Deliberately exit 0. A disabled pipeline is a configuration choice, and reporting it as
  # a cron failure would train the operator to ignore this job's alerts.
  echo "==> NEWS_INGESTION_ENABLED is not true; nothing to do."
  exit 0
fi

# shellcheck disable=SC2086
if docker compose $COMPOSE_FILES run --rm -T backend \
      python -m app.news.cli ingest --triggered-by cron; then
  echo "==> [$(stamp)] news-ingest completed"
else
  status=$?
  echo "!! [$(stamp)] news-ingest FAILED (exit $status)" >&2
  exit "$status"
fi
