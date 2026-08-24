#!/usr/bin/env bash
# Scheduled AI News generation. Turns candidates into review-ready drafts.
#
# This is the only scheduled job that spends money. It is bounded three ways:
#   NEWS_GENERATION_ENABLED   must be true, or this exits without calling anything
#   NEWS_GENERATION_BATCH_SIZE   candidates per run
#   NEWS_DAILY_GENERATION_LIMIT  attempts per day, counted across all runs
#
# It CANNOT publish. Every article it produces is draft or review_required, because the
# generation service has no path to 'published'.
#
# Cron (daily 02:00, log to file):
#   0 2 * * * cd /opt/jobsvsai && ./scripts/news-generate.sh >> /var/log/jobsvsai-news.log 2>&1
#
# Timeout note: a FAILING provider call occupies 80-140 seconds, because the 45s request
# timeout is multiplied by up to three attempts plus backoff. A batch of two all-failing
# candidates was measured at 258 seconds. Budget accordingly before shortening any timeout.
set -euo pipefail

cd "$(dirname "$0")/.."
# Load .env, but let an already-set environment variable win. `set -a; . ./.env` alone
# lets the file clobber the caller, which makes a one-off override impossible and — more
# quietly — makes these guards untestable from a shell. The file stays the default source
# of truth; an explicit override for a single run is respected.
_keep() { for _v in "$@"; do eval "_saved_$_v=\${$_v-}"; done; }
_restore() { for _v in "$@"; do eval "[ -n \"\$_saved_$_v\" ] && export $_v=\"\$_saved_$_v\"" || true; done; }
_keep NEWS_GENERATION_ENABLED NEWS_AUTO_PUBLISH NEWS_GENERATION_BATCH_SIZE NEWS_DAILY_GENERATION_LIMIT
[ -f .env ] && set -a && . ./.env && set +a
_restore NEWS_GENERATION_ENABLED NEWS_AUTO_PUBLISH NEWS_GENERATION_BATCH_SIZE NEWS_DAILY_GENERATION_LIMIT

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml}"

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
echo "==> [$(stamp)] news-generate starting"

if [ "${NEWS_GENERATION_ENABLED:-false}" != "true" ]; then
  echo "==> NEWS_GENERATION_ENABLED is not true; no provider call will be made."
  exit 0
fi

# A safety net, not the enforcement point: the service refuses to publish regardless. This
# exists so a misconfiguration is caught before spending anything, not after.
if [ "${NEWS_AUTO_PUBLISH:-false}" = "true" ]; then
  echo "!! NEWS_AUTO_PUBLISH is true. Refusing to run scheduled generation." >&2
  echo "!! Publication must stay editorially controlled. Set it to false." >&2
  exit 2
fi

echo "==> batch=${NEWS_GENERATION_BATCH_SIZE:-2} daily_cap=${NEWS_DAILY_GENERATION_LIMIT:-5}"

# shellcheck disable=SC2086
if docker compose $COMPOSE_FILES run --rm -T backend \
      python -m app.news.cli generate --triggered-by cron; then
  echo "==> [$(stamp)] news-generate completed. Drafts await review at /admin/news."
else
  status=$?
  echo "!! [$(stamp)] news-generate FAILED (exit $status)" >&2
  # Candidates are left recoverable by design; the next run picks them up.
  exit "$status"
fi
