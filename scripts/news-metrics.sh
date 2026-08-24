#!/usr/bin/env bash
# Scheduled AI News metrics. Read-only: reports what the pipeline already recorded.
#
# Writes nothing and calls nothing external. Safe to run whatever the feature flags say,
# which is why it has no enablement check.
#
# Cron (daily 04:00, log to file):
#   0 4 * * * cd /opt/jobsvsai && ./scripts/news-metrics.sh >> /var/log/jobsvsai-news.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."
# Load .env, but let an already-set environment variable win. `set -a; . ./.env` alone
# lets the file clobber the caller, which makes a one-off override impossible and — more
# quietly — makes these guards untestable from a shell. The file stays the default source
# of truth; an explicit override for a single run is respected.
_keep() { for _v in "$@"; do eval "_saved_$_v=\${$_v-}"; done; }
_restore() { for _v in "$@"; do eval "[ -n \"\$_saved_$_v\" ] && export $_v=\"\$_saved_$_v\"" || true; done; }
_keep NEWS_METRICS_WINDOW_DAYS
[ -f .env ] && set -a && . ./.env && set +a
_restore NEWS_METRICS_WINDOW_DAYS

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml}"
DAYS="${NEWS_METRICS_WINDOW_DAYS:-30}"

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
echo "==> [$(stamp)] news-metrics (last ${DAYS} days)"

# shellcheck disable=SC2086
if docker compose $COMPOSE_FILES run --rm -T backend \
      python -m app.news.cli metrics --days "$DAYS"; then
  echo "==> [$(stamp)] news-metrics completed"
else
  status=$?
  echo "!! [$(stamp)] news-metrics FAILED (exit $status)" >&2
  exit "$status"
fi
