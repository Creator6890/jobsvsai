#!/usr/bin/env bash
# End-to-end health check: containers, datastores, worker, API and public routes.
# Exit 0 only if every check passes, so it is usable from cron or a deploy gate.
#
#   scripts/healthcheck.sh            checks the live domains from .env
#   scripts/healthcheck.sh --local    checks over the compose network instead of DNS/TLS
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml}"
DB_USER="${POSTGRES_USER:-jobsvsai}"
DB_NAME="${POSTGRES_DB:-jobsvsai}"
LOCAL_ONLY=0
[ "${1:-}" = "--local" ] && LOCAL_ONLY=1

pass=0; fail=0
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=$((fail+1)); }
check(){ if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }

# shellcheck disable=SC2086
dc() { docker compose $COMPOSE_FILES "$@"; }

echo "== Containers =="
# Derived from the compose files in use, so this script is equally valid against the dev
# stack (no caddy) and production (with it).
services="$(dc config --services 2>/dev/null | xargs)"
for svc in $services; do
  state="$(dc ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk -v s="$svc" '$1==s{print $2}')"
  if [ "$state" = "running" ]; then ok "$svc running"; else bad "$svc (${state:-absent})"; fi
done

echo "== Datastores =="
check "postgres accepting connections" "dc exec -T postgres pg_isready -U $DB_USER -d $DB_NAME"
check "redis responding to PING"       "dc exec -T redis redis-cli ping"

echo "== Data integrity =="
read -r pub scores model < <(dc exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -qtAX -F' ' -c \
  "SELECT (SELECT count(*) FROM occupation_publications WHERE activation_status='public'),
          (SELECT count(*) FROM current_production_occupation_scores),
          (SELECT version FROM scoring_model_versions WHERE is_active);" 2>/dev/null || echo "0 0 none")
[ "$pub" -gt 0 ] 2>/dev/null && ok "public occupations: $pub" || bad "public occupations: $pub"
[ "$scores" -gt 0 ] 2>/dev/null && ok "live production scores: $scores" || bad "live production scores: $scores"
# The legacy worker writes under whatever model is active; JVS 2.0 must stay inactive.
[ "$model" = "JVS 1.0.3" ] && ok "active scoring model is $model" || bad "active scoring model is '$model' (expected JVS 1.0.3)"

echo "== Worker =="
check "worker process alive" "dc exec -T worker python -c 'import os,redis;redis.from_url(os.environ[\"REDIS_URL\"]).ping()'"

echo "== API (internal) =="
check "backend /health" "dc exec -T backend python -c \"import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)\""

if [ "$LOCAL_ONLY" -eq 1 ]; then
  echo "== Frontend (internal) =="
  check "frontend /api/health" "dc exec -T frontend wget -qO- http://127.0.0.1:3000/api/health"
else
  site="https://${SITE_DOMAIN:?SITE_DOMAIN not set}"
  api="https://${API_DOMAIN:?API_DOMAIN not set}"
  echo "== Public routes ($site) =="
  for path in / /rankings /compare /methodology /about /sitemap.xml; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$site$path" 2>/dev/null || echo 000)"
    [ "$code" = "200" ] && ok "$path -> $code" || bad "$path -> $code"
  done
  # A published occupation page, chosen from the database so the check is never stale.
  slug="$(dc exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -qtAX -c \
    "SELECT o.slug FROM occupations o
     JOIN canonical_occupation_identities i ON i.jobs_vs_ai_occupation_id=o.id
     JOIN occupation_publications p ON p.identity_id=i.id AND p.activation_status='public'
     ORDER BY o.slug LIMIT 1;" 2>/dev/null | tr -d '\r')"
  if [ -n "$slug" ]; then
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$site/jobs/$slug" || echo 000)"
    [ "$code" = "200" ] && ok "/jobs/$slug -> $code" || bad "/jobs/$slug -> $code"
  fi

  echo "== API ($api) =="
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$api/health" || echo 000)"
  [ "$code" = "200" ] && ok "/health -> $code" || bad "/health -> $code"
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$api/api/v1/occupations?limit=1" || echo 000)"
  [ "$code" = "200" ] && ok "/api/v1/occupations -> $code" || bad "/api/v1/occupations -> $code"

  echo "== Ingress hygiene =="
  redirect="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "http://${SITE_DOMAIN}" || echo 000)"
  [ "$redirect" = "308" ] || [ "$redirect" = "301" ] || [ "$redirect" = "302" ] \
    && ok "http -> https redirect ($redirect)" || bad "http redirect returned $redirect"
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$api/admin" || echo 000)"
  [ "$code" = "404" ] && ok "data console not exposed on API host (404)" || bad "$api/admin -> $code (expected 404)"
fi

echo
echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
