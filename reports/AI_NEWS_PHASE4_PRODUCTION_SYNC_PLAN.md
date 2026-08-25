# AI News Phase 4 — production sync plan

Date: 2026-08-25
Status: **READY FOR SAFE PRODUCTION SYNC.** Not deployed. No cron installed. Every AI News
capability remains off.

## 1. Verified git state

```
branch : main
HEAD   : 3469cb4   clean working tree, in sync with origin/main
```

## 2. Actual Phase 4 commit sequence

**Commit order differs from step order**, and the brief's listing does not match git. Step 6
was committed *before* Step 5, because Step 6 needed a metrics command and Step 5 had not
been done. This is the one place where reading the prompt instead of the repository would
have produced a wrong release note.

```
3469cb4  Step 5  cost and metrics analysis        <- newest
c399150  Step 6  controlled automation layer
5c98f8a  Step 4  generation validation (migration 033)
97fa3d5  Step 3  editorial controls (migration 032)
95c6b3f  Step 2  ingestion CLI + dry run
f1188f1  Step 1  feature flag separation
76200a3  ── production baseline (Phase 1-3, migrations 029-031)
```

Delta: **6 commits**, 26 runtime files, +1,962 / −85 lines.

## 3. Step 5 ↔ Step 6 compatibility

The material risk in this release: Step 5 rewrote the very CLI command Step 6's script calls.
Verified by execution, not inspection.

| Check | Result |
|---|---|
| `news-metrics.sh` calls a valid command | yes — `metrics --days N`, both flags still accepted |
| Step 5 output reaches the script | yes — all 7 Step 5 sections present in script stdout |
| Insufficient-sample guard fires through the script | yes |
| `news-ingest.sh` / `news-generate.sh` unaffected | yes, exit 0 |
| Exit-code matrix intact | disabled → 0, auto-publish → **2**, broken compose → 1 |
| Env precedence intact | `_keep` / `_restore` present in all three scripts |
| Caps resolve through one source | `generations_per_run` / `generations_per_day` properties |
| Optional `NEWS_*` empty strings parse | yes — validator covers all 7 nullable fields |

`news-metrics.sh` writes to stderr while exiting 0; inspected and confirmed to be Docker
Compose container-progress output, not error output.

**No compatibility bug was found.** No fix was required.

## 4. Runtime files changed

| Area | Files |
|---|---|
| Configuration | `backend/app/core/config.py`, `docker-compose.yml`, `.env.example`, `.env.production.example` |
| News domain | `app/news/{cli,metrics,ingestion,generation_service,gemini}.py` |
| Repositories | `repositories/{news,news_ingest,news_metrics}.py` |
| API / schema | `api/admin_news.py`, `schemas/news.py` |
| Worker | `worker/news_jobs.py` |
| Migrations | `032_ai_news_phase4_editorial.sql`, `033_ai_news_phase4_generation_audit.sql` |
| Automation | `scripts/news-{ingest,generate,metrics}.sh`, `deploy/news-cron.example` |
| Admin UI | `admin/news/[articleId]/page.tsx`, `admin/news/incoming/page.tsx`, `admin/news/actions.ts`, `lib/api.ts` |
| Test harness | `scripts/run-tests.sh` (read-only mounts) |

## 5. Migration review

Both applied cleanly from scratch via `./scripts/create-test-db.sh --migrations`.

**032 — editorial.** `ALTER TABLE news_articles` only. Adds `archived` to the status CHECK
and five audit columns. Archiving preserves `published_at` where rejecting clears it, because
an article that was published genuinely was.

**033 — generation audit.** `ALTER TABLE news_ingest_items` only. Adds
`generation_latency_ms` and a `generation_error_kind` vocabulary, paired by CHECK with the
message.

**Isolation, verified by grep across both files:**

| Table | Occurrences |
|---|---|
| `occupations`, `occupation_scores`, `occupation_publications` | **0** |
| `production_occupation_score_snapshots`, `scoring_model_versions` | **0** |
| `canonical_occupation_identities`, `production_promotion_runs` | **0** |

The only DDL targets are `news_articles` and `news_ingest_items`.

**Backwards compatible.** Both are additive: new columns are nullable or defaulted, and every
new constraint is satisfied by existing rows unchanged. An older application image runs
against the migrated schema without error, which is what makes the rollback in §12 safe.

## 6. Environment variable migration

**OLD (production today):** `NEWS_ENABLED` — one flag gating both pipelines.

**NEW:** 18 variables, read from the `Settings` model rather than from documentation.

| Variable | Type | Default | Purpose |
|---|---|---|---|
| `NEWS_INGESTION_ENABLED` | bool\|None | unset → false | feed polling |
| `NEWS_GENERATION_ENABLED` | bool\|None | unset → false | provider calls |
| `NEWS_AUTO_PUBLISH` | bool | false | must stay false |
| `NEWS_ENABLED` | bool\|None | unset | **deprecated**, see precedence |
| `NEWS_LLM_PROVIDER` / `_MODEL` / `_API_KEY` | str | `null` / `''` / `''` | provider; key is a secret |
| `NEWS_LLM_TIMEOUT_SECONDS` | int | 45 | per request |
| `NEWS_GENERATION_BATCH_SIZE` | int | 2 | per-run cap |
| `NEWS_DAILY_GENERATION_LIMIT` | int | 5 | per-day cap |
| `NEWS_MAX_GENERATIONS_PER_RUN` / `_PER_DAY` | int\|None | unset | aliases; win when set |
| `NEWS_LOOKBACK_HOURS` | int | 48 | ingestion window |
| `NEWS_MAX_ENTRIES_PER_FEED` | int | 40 | per-feed cap |
| `NEWS_MAX_CANDIDATES_PER_RUN` | int | 60 | candidate ceiling |
| `NEWS_FETCH_INTERVAL_MINUTES` | int | 120 | cadence, read by automation |
| `NEWS_LLM_COST_PER_1M_INPUT` / `_OUTPUT` | float\|None | unset | optional pricing |

### `NEWS_ENABLED` precedence

1. An **explicitly set** new flag wins.
2. Otherwise `NEWS_ENABLED` applies to **both**, preserving old behaviour exactly.
3. Otherwise disabled.

Failing closed instead would have silently stopped any environment running with
`NEWS_ENABLED=true`. Production has it false, so **this release changes nothing there.**
`Settings.uses_legacy_news_flag` reports when the deprecated variable is still in play, and
admin surfaces it.

### A gap this review found and fixed

`.env.production.example` — the template production is provisioned from — contained **zero**
`NEWS_*` variables, while `.env.example` had twenty.

Not a functional defect: verified that a production `.env` with no `NEWS_` lines comes up
fully gated (`ingestion=False generation=False auto_publish=False`), because compose passes
unset variables as empty and every default is disabled. But for a release whose entire
purpose is landing safety controls, a production template that does not mention them is a
real documentation defect — an operator would have no way to learn the knobs exist.

Fixed, plus `NEWS_LLM_TIMEOUT_SECONDS` and the two aliases which were missing from
`.env.example`. Four regression tests now compare both templates against the `Settings` model
and the compose file, so a new setting cannot be added without the templates following, and
assert the production template ships all three flags as `false` with no live provider and no
key.

## 7. Feature flag matrix — verified

| Case | ingestion | generation | auto-publish | legacy |
|---|---|---|---|---|
| A: all unset (**intended post-deploy state**) | false | false | false | no |
| A: explicit false / false | false | false | false | no |
| B: ingestion true, generation false | **true** | **false** | false | no |
| C: generation explicitly false | false | false | false | no |
| legacy `NEWS_ENABLED=true` | true | true | false | **yes** |
| legacy true + generation explicitly false | true | **false** | false | yes |
| D: auto-publish forced true | false | false | true | no |

**Case C** — generation is gated at 7 independent points: 3 in the service (including inside
`generate_for_candidate` before the item is even loaded), 2 in the API, 1 in the worker, 1 in
the script. Every generation path funnels through the service check.

**Case D** — `decide_status()` can only return `draft` or `review_required`; there are **zero**
`publish()` call sites in the generation service and **zero** reads of `news_auto_publish` in
it. No value of that flag can create a publish path, which is why the script check is
described as a safety net rather than the enforcement point.

## 8. Test result

```
./scripts/run-tests.sh
400 passed
```

Guard confirmed: `database jobsvsai_test`, `environment test`, `TEST_DATABASE=true`.

**Baseline moved 395 → 400.** The five additions are the env-template drift tests from §6.
No existing test was changed or removed.

## 9. Frontend and image builds

`docker compose -f docker-compose.yml build frontend` — clean. `backend` and `worker` also
rebuilt, since Phase 4 changed backend dependencies (`google-genai`, `defusedxml`) and the
worker shares that image lineage. All three succeeded.

## 10. Scoring isolation

```
507 live   507 public   11 legacy   JVS 1.0.3   1 real promotion run
```

Verified read-only. The 6-commit delta touches **no** scoring module, promotion path, or
pre-029 migration — confirmed by filtering the changed-file list against
`scoring/`, `worker/jobs.py`, `repositories/{production_scores,publication,occupations}.py`
and migrations 001–028: zero matches. The `information_schema` isolation assertion runs in
the suite on every execution.

## 11. Deployment plan

Not executed. Assumes the existing artifact/tarball workflow, **not** a git checkout on the
VPS.

### Local — build the artifact

```bash
cd /Users/akshaychandra/Documents/jobsvsai
git status --porcelain          # must be empty
git rev-parse --short HEAD      # must read 3469cb4

git archive --format=tar.gz -o /tmp/jobsvsai-3469cb4.tar.gz HEAD
```

`git archive` is used deliberately: it exports **only tracked content at HEAD**, so `.git`,
`.env`, `node_modules`, `.next`, `__pycache__`, macOS metadata, old tarballs and local
backups are excluded by construction rather than by a fragile exclude list.

```bash
scp /tmp/jobsvsai-3469cb4.tar.gz <user>@<vps>:/tmp/
```

### On the VPS — stage beside the current release

```bash
sudo mkdir -p /opt/jobsvsai/releases/3469cb4
sudo tar -xzf /tmp/jobsvsai-3469cb4.tar.gz -C /opt/jobsvsai/releases/3469cb4

# Carry the existing environment across. Never printed, never copied into the artifact.
sudo cp -p /opt/jobsvsai/jobsvsai/.env /opt/jobsvsai/releases/3469cb4/.env
sudo chmod 600 /opt/jobsvsai/releases/3469cb4/.env
```

### Environment review — without printing secrets

```bash
cd /opt/jobsvsai/releases/3469cb4

# Names only, values redacted.
sed -E 's/=.*/=<set>/' .env | sort

# The three flags that must be false or absent. Absent is safe: defaults are disabled.
grep -E '^NEWS_(INGESTION_ENABLED|GENERATION_ENABLED|AUTO_PUBLISH|ENABLED)=' .env || \
  echo 'no NEWS_ flags set — defaults apply, all disabled'
```

**Do not proceed** unless all three read `false` or are absent. Append the AI News block from
`.env.production.example` if you want them explicit; the values there are already the safe
state.

### Backup, migrate, deploy

```bash
cd /opt/jobsvsai/jobsvsai && ./scripts/backup-db.sh          # verified dump before any DDL

cd /opt/jobsvsai/releases/3469cb4
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

docker compose $COMPOSE_FILES build                          # all three images
./scripts/migrate.sh --status                                # expect 032, 033 pending
./scripts/migrate.sh                                         # apply
./scripts/migrate.sh --status                                # expect none pending

sudo ln -sfn /opt/jobsvsai/releases/3469cb4 /opt/jobsvsai/jobsvsai
cd /opt/jobsvsai/jobsvsai
docker compose $COMPOSE_FILES up -d
./scripts/healthcheck.sh
```

If `migrate.sh` has no `--status` flag, substitute the project's equivalent; do not invent
one.

### Verification

```bash
# Flags off — the single most important check.
docker compose $COMPOSE_FILES run --rm -T backend python -m app.news.cli metrics --days 1
docker compose $COMPOSE_FILES exec -T backend python -c \
  "from app.core.config import get_settings as g; s=g(); \
   print(s.ingestion_enabled, s.generation_enabled, s.news_auto_publish)"
# expect: False False False

# Public news surface unchanged.
curl -sS -o /dev/null -w '%{http_code}\n' https://jobsvsai.com/news
curl -sS https://api.jobsvsai.com/api/v1/news | head -c 80        # expect []

# Scoring integrity — the release must not have moved any of these.
./scripts/psql-readonly.sh -qtAX -c "
  SELECT (SELECT count(*) FROM current_production_occupation_scores)
      ||' '||(SELECT count(*) FROM occupation_publications WHERE activation_status='public')
      ||' '||(SELECT version FROM scoring_model_versions WHERE is_active);"
# expect: 507 507 JVS 1.0.3

curl -sS 'https://api.jobsvsai.com/api/v1/rankings?limit=1000' | \
  python3 -c 'import json,sys; print(len(json.load(sys.stdin)))'   # expect 507
```

`cron` is **not** installed at any point.

## 12. Rollback plan

Migrations 032 and 033 are additive and backwards compatible, so **schema is not rolled back**
in any scenario below. The previous application image runs against the migrated schema
unchanged; dropping columns would be the riskier operation, not the safer one.

**A — application failure.** Repoint the symlink and restart:

```bash
sudo ln -sfn /opt/jobsvsai/releases/<previous> /opt/jobsvsai/jobsvsai
cd /opt/jobsvsai/jobsvsai && docker compose $COMPOSE_FILES up -d && ./scripts/healthcheck.sh
```

Seconds, no data loss. Leave 032/033 in place: the old code neither reads nor writes those
columns.

**B — migration failure.** `migrate.sh` runs each file in a transaction, so a failure leaves
the schema at the last successful migration. Nothing is half-applied. Fix forward, or restore
the pre-migration dump taken above with `./scripts/restore-db.sh` — only necessary if a
migration both succeeded and proved wrong, which for two additive ALTERs is unlikely.

**C — frontend failure.** The frontend is a separate image and carries no news write path.
`docker compose $COMPOSE_FILES up -d --no-deps frontend` after repointing, or roll back the
whole release via A.

**D — worker failure.** The worker runs no scheduled news job — nothing is scheduled. It can
be stopped outright (`docker compose $COMPOSE_FILES stop worker`) with no effect on the public
site or on AI News, which is entirely CLI- and admin-driven in this release.

**Rolling back the application does not reactivate anything**, because nothing was activated.

## 13. Expected post-deploy state

```
NEWS_INGESTION_ENABLED  = false
NEWS_GENERATION_ENABLED = false
NEWS_AUTO_PUBLISH       = false
cron                    = NOT installed
scheduled ingestion     = OFF
scheduled generation    = OFF
provider calls          = 0
published news articles = 0 (unchanged)
occupations             = 507 live / 507 public / JVS 1.0.3 (unchanged)
```

The purpose of this release is to land the safety controls **before** the pipeline is
activated. Nothing observable changes for a visitor.

## 14. Remaining blockers before activation

None block *this* release. All block *activation*, and none are code problems.

| Blocker | Detail |
|---|---|
| **Provider reliability** | Three consecutive Step 4 failures (timeout, 504, 503) on top of Phase 3's 503→429. The dominant operational risk. |
| **Generation sample of one** | One successful generation exists anywhere, at 2,248 tokens. Economics and content quality are both unanswerable, and `metrics` correctly withholds every projection. |
| **Pricing unset** | No currency figures until `NEWS_LLM_COST_PER_1M_*` are configured. |
| **Near-dedupe unvalidated** | Two live samples, zero same-event duplicates. The 0.55 threshold is still calibrated only against constructed cases. |
| **48h cold start** | A first scheduled ingestion at the default finds nothing. Use `--lookback 168` manually first. |
| **Failing calls are slow** | 80–140s each; a two-candidate all-failing batch took 258s. Any future cron must budget for it. |
| **No Atom source live-tested** | All nine feeds are RSS 2.0. |
| **Log rotation** | `/var/log/jobsvsai-news.log` unbounded once automation runs. |

## 15. Verdict

**READY FOR SAFE PRODUCTION SYNC.**

Six commits, two additive migrations, no scoring impact, 400 tests passing, all three images
building, every AI News capability off by default and verified off across the full flag
matrix. One documentation gap was found and fixed, with regression tests to stop it
recurring.

Deployment awaits explicit approval and has not been performed.
