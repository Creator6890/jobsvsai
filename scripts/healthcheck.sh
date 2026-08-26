#!/usr/bin/env bash
# End-to-end health check: containers, datastores, worker, API and public routes.
# Exit 0 only if every check passes, so it is usable from cron or a deploy gate.
#
#   scripts/healthcheck.sh            checks the live domains from .env
#   scripts/healthcheck.sh --local    checks over the compose network instead of DNS/TLS
#
# Beyond liveness, this script guards the three faults that reached production during the
# Search V2 + Preliminary Estimates release. Each was invisible to a liveness check: search
# returned a confidently wrong occupation, a page took eight seconds and timed out, and the
# AdSense verification tag silently disappeared. All three passed "is it up?".
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml}"
DB_USER="${POSTGRES_USER:-jobsvsai}"
DB_NAME="${POSTGRES_DB:-jobsvsai}"
LOCAL_ONLY=0
[ "${1:-}" = "--local" ] && LOCAL_ONLY=1

# Expected cohort shape. Overridable the way deploy.sh does it, because these move when a
# promotion or an estimate run legitimately changes them — a health check that cannot be
# updated without editing it gets commented out the first time it is inconvenient.
EXPECT_VERIFIED="${EXPECT_VERIFIED:-507}"
EXPECT_ESTIMATES="${EXPECT_ESTIMATES:-390}"
EXPECT_E1="${EXPECT_E1:-59}"
EXPECT_E2="${EXPECT_E2:-293}"
EXPECT_E3="${EXPECT_E3:-38}"
EXPECT_INSUFFICIENT="${EXPECT_INSUFFICIENT:-15}"
ADSENSE_PUBLISHER="${ADSENSE_PUBLISHER:-ca-pub-7855774194309157}"
# Generous on purpose. The regression it catches took 8.3s; normal is under one second. A
# millisecond-tight bound in a health check produces flapping alerts and gets ignored.
OCCUPATION_LIST_BUDGET_S="${OCCUPATION_LIST_BUDGET_S:-6}"

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

echo "== Score classes =="
# Verified and preliminary are tracked separately and must never be collapsed into one
# number. 897 searchable pages is not 897 verified analyses, and a health check that reports
# a single total would hide exactly that distinction.
read -r est e1 e2 e3 overlap < <(dc exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -qtAX -F' ' -c \
  "SELECT (SELECT count(*) FROM current_published_occupation_estimates),
          (SELECT count(*) FROM current_published_occupation_estimates WHERE estimate_method='E1'),
          (SELECT count(*) FROM current_published_occupation_estimates WHERE estimate_method='E2'),
          (SELECT count(*) FROM current_published_occupation_estimates WHERE estimate_method='E3'),
          (SELECT count(*) FROM current_published_occupation_estimates e
             WHERE EXISTS (SELECT 1 FROM current_production_occupation_scores c
                           WHERE c.identity_id = e.identity_id));" 2>/dev/null || echo "0 0 0 0 0")
[ "$pub" = "$EXPECT_VERIFIED" ] && ok "verified occupations: $pub" || bad "verified occupations: $pub (expected $EXPECT_VERIFIED)"
# The relationship matters more than either number: a public occupation with no live score is
# a page publishing something the store cannot serve.
[ "$pub" = "$scores" ] && ok "verified scores match verified occupations ($scores)" \
  || bad "verified scores $scores != verified occupations $pub"
[ "$est" = "$EXPECT_ESTIMATES" ] && ok "preliminary estimates: $est" || bad "preliminary estimates: $est (expected $EXPECT_ESTIMATES)"
[ "$e1" = "$EXPECT_E1" ] && ok "E1: $e1" || bad "E1: $e1 (expected $EXPECT_E1)"
[ "$e2" = "$EXPECT_E2" ] && ok "E2: $e2" || bad "E2: $e2 (expected $EXPECT_E2)"
[ "$e3" = "$EXPECT_E3" ] && ok "E3: $e3" || bad "E3: $e3 (expected $EXPECT_E3)"
[ "$overlap" = "0" ] && ok "no occupation is both verified and estimated" \
  || bad "$overlap occupation(s) hold a verified score AND a published estimate"
echo "  ---- verified $pub  +  preliminary $est  =  $((pub + est)) searchable ----"

echo "== Product policy (V1: verified-only surfaces) =="
# Rankings, Career Fit and Compare all read through public_occupation_predicate, which gates
# on activation_status. Asserting at that gate covers all three at once and cannot drift the
# way three separate page scrapes would.
leaked="$(dc exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -qtAX -c \
  "SELECT count(*) FROM occupations o
   WHERE o.is_active
     AND EXISTS (SELECT 1 FROM canonical_occupation_identities gi
                 JOIN occupation_publications gp ON gp.identity_id=gi.id
                 WHERE gi.jobs_vs_ai_occupation_id=o.id AND gp.activation_status='public')
     AND EXISTS (SELECT 1 FROM canonical_occupation_identities ei
                 JOIN current_published_occupation_estimates e ON e.identity_id=ei.id
                 WHERE ei.jobs_vs_ai_occupation_id=o.id);" 2>/dev/null || echo 999)"
[ "$leaked" = "0" ] && ok "rankings / career fit / compare expose 0 estimated occupations" \
  || bad "$leaked estimated occupation(s) reachable through the verified publication gate"

insufficient="$(dc exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -qtAX -c \
  "SELECT count(*) FROM occupation_publications p
   JOIN canonical_occupation_identities ci ON ci.id=p.identity_id
   WHERE p.activation_status='staged'
     AND NOT EXISTS (SELECT 1 FROM current_published_occupation_estimates e
                     WHERE e.identity_id=ci.id);" 2>/dev/null || echo -1)"
[ "$insufficient" = "$EXPECT_INSUFFICIENT" ] && ok "staged without any analysis: $insufficient" \
  || bad "staged without any analysis: $insufficient (expected $EXPECT_INSUFFICIENT)"

echo "== Read-path indexes =="
# Migration 036. Every public occupation read hydrates related careers through a LATERAL that
# filters on identity_id and takes max(content_run_id); every other index on that table leads
# with content_run_id and cannot serve it. Without this one, /compare returned 500.
check "related-career lookup is indexed by identity" \
  "dc exec -T postgres psql -U $DB_USER -d $DB_NAME -qtAX -c \"SELECT 1 FROM pg_indexes WHERE indexname='public_content_related_identity_run_idx';\" | grep -q 1"

echo "== Worker =="
check "worker process alive" "dc exec -T worker python -c 'import os,redis;redis.from_url(os.environ[\"REDIS_URL\"]).ping()'"

echo "== Search semantics =="
# Three bounded smoke checks, not the 187-query benchmark — that belongs in the test suite,
# not in something cron runs. Each asserts a canonical slug rather than display text, because
# titles are editorial and change without the meaning changing.
#
# All three are regressions that actually shipped or nearly shipped: "soft eng" led with
# Etchers and Engravers (via the alternate title "Soft Metal Hand Engraver"), and "pen tester"
# reaching a physical-testing occupation is the failure Search V2 was built to end.
semantic() { # query, expected-first-slug, slug-that-must-not-lead
  local q="$1" want="$2" forbid="${3:-}" first
  first="$(dc exec -T backend python -c '
import json, sys, urllib.parse, urllib.request
url = "http://localhost:8000/api/v1/occupations/search/resolve?q=" + urllib.parse.quote(sys.argv[1])
try:
    with urllib.request.urlopen(url, timeout=15) as response:
        order = json.load(response).get("resultOrder") or []
    print(order[0] if order else "")
except Exception:
    print("")
' "$q" 2>/dev/null | tr -d '\r' | tail -1)"
  if [ "$first" = "$want" ]; then
    ok "\"$q\" -> $first"
  elif [ -n "$forbid" ] && [ "$first" = "$forbid" ]; then
    bad "\"$q\" -> $first, the documented wrong answer (expected $want)"
  else
    bad "\"$q\" -> '${first:-none}' (expected $want)"
  fi
}
semantic "soft eng"     "software-developer"    "etchers-and-engravers"
semantic "pen tester"   "cybersecurity-analyst" "non-destructive-testing-specialists"
semantic "data analyst" "data-scientists"

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

  echo "== AdSense =="
  # Two separate facts, deliberately reported as two lines. The account CONNECTION being live
  # is what Google's review needs; manual ad SERVING being off is the product decision. During
  # the Search V2 release an empty NEXT_PUBLIC_ADSENSE_CLIENT_ID was baked into the build, the
  # verification tag vanished mid-review, and every liveness check still passed — because the
  # page was fine, it simply no longer identified the publisher.
  home="$(curl -sS --max-time 20 "$site/" 2>/dev/null || echo "")"
  # Every extraction is `|| true`-guarded. `set -o pipefail` is on, and grep exits 1 when it
  # matches nothing, so an unguarded pipeline aborts the whole script the moment a tag is
  # missing — which is precisely the case this block exists to report.
  count() { printf '%s' "$home" | grep -c -- "$1" 2>/dev/null || true; }
  metas="$(count '<meta name="google-adsense-account"')"
  right_pub="$(count "google-adsense-account\" content=\"$ADSENSE_PUBLISHER")"
  loader="$(count "adsbygoogle.js?client=$ADSENSE_PUBLISHER")"
  units="$(count 'class="adsbygoogle"')"

  if [ "${metas:-0}" -ge 1 ] && [ "${right_pub:-0}" -ge 1 ] && [ "${loader:-0}" -ge 1 ]; then
    ok "ADSENSE CONNECTION: LIVE (verification meta + loader, $ADSENSE_PUBLISHER)"
  else
    bad "ADSENSE CONNECTION: meta=${metas:-0} publisher=${right_pub:-0} loader=${loader:-0} (each must be >=1)"
  fi
  if [ "${units:-0}" -eq 0 ]; then
    ok "MANUAL AD SERVING: OFF (0 ad units rendered)"
  else
    bad "MANUAL AD SERVING: ${units} ad unit(s) rendered while ads should be off"
  fi

  echo "== Hydration budget =="
  # Not a benchmark; a tripwire. The related-career LATERAL regression took this to 8.3s and
  # broke /compare, which loads every occupation to fill its selector.
  elapsed="$(curl -sS -o /dev/null -w '%{time_total}' --max-time 30 \
    "$api/api/v1/occupations?limit=500" 2>/dev/null || echo 99)"
  if awk -v t="$elapsed" -v b="$OCCUPATION_LIST_BUDGET_S" 'BEGIN{exit !(t+0 < b+0)}'; then
    ok "/api/v1/occupations?limit=500 in ${elapsed}s (budget ${OCCUPATION_LIST_BUDGET_S}s)"
  else
    bad "/api/v1/occupations?limit=500 took ${elapsed}s (budget ${OCCUPATION_LIST_BUDGET_S}s)"
  fi
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "$site/compare" || echo 000)"
  [ "$code" = "200" ] && ok "/compare -> $code (loads every occupation)" || bad "/compare -> $code"

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
