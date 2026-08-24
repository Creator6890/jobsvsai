# JobsVsAI — working context

Career intelligence platform. Answers "how is AI likely to affect my job, and what should I
do about it?" using a proprietary interpretation layer over O\*NET 30.3.

**The 507-occupation cohort is promoted and public as of 2026-08-21.** Read
`reports/PHASE6_STATE_RECONCILIATION.md` first — it is the current state of play and lists
which reports are superseded. `reports/PHASE6_ACTIVATION_AUDIT.md` is the authoritative
detail on the promotion and the activation.

Most other Phase 6 reports open with "Nothing promoted. No occupation activated." That was
true when they were written and is false now; their methodology is still valid, only the
status banner is stale. `reports/PHASE6_LAUNCH_PLAN.md` in particular is **no longer the
current state of play** — its steps 3, 4, 5, 6, 9 and 10 are done.
`reports/PHASE6_POST_COVERAGE_TRIAGE_REPORT.md` is how the cohort was derived.
`reports/PHASE5B_COVERAGE_COMPLETION_REPORT.md` explains why the earlier 8-occupation cohort
was a pipeline artefact; `reports/PHASE5B_SCORE_DELTA_REPORT.md` shows what the added
evidence did to scores. `reports/PHASE6_LAUNCH_READINESS_REPORT.md` remains accurate on
schema, guards and admin surfaces.
`reports/PHASE6_OPTION_B_IMPLEMENTATION_REPORT.md` describes the production score store.
Earlier phase reports in `reports/` describe how the methodology was validated.

Stack: Next.js 16 + TypeScript, FastAPI + Python, PostgreSQL, Redis/RQ, Docker Compose.
Avoid adding infrastructure (Kubernetes, Kafka, Elasticsearch, microservices) without a
demonstrated need.

## Frozen methodological decisions

These were validated across Phases 4A–5. Do not casually revisit them; if evidence suggests
one is wrong, explain the problem before changing anything.

- **Exposure is not replacement.** AI Exposure and Replacement Risk are separate 0–100
  indices and must never collapse into one number. They are indices, not probabilities.
- **Task requirement is not current AI capability.** Task→capability mappings describe what
  the work requires and stay independent of the Frontier AI Capability Index, so capability
  updates do not force remapping.
- **Capability is not automation; automation is not augmentation.** Capability Fit,
  Automation Feasibility and Augmentation Potential are three separate task-level metrics.
- **The bottleneck principle.** Capability Fit uses a weighted geometric mean with an
  explicit cap on unmet critical requirements. Strength in one capability must not cancel
  weakness in another.
- **Archetype scoring stays disabled.** Phase 4C showed it does not improve calibration. It
  is useful for navigation and grouping only.
- **Missing data is not zero.** Never fill a gap with a default, a category average, or a
  plausible sentence. The 70% weighted coverage gate is not negotiable.
- **Do not tune scores to intuition.** If an occupation looks wrong, investigate the
  contributing data and formulas.
- **Determinism and versioning.** Same inputs + same versions must reproduce the same score.
  Reuse persisted mappings; avoid unnecessary AI calls.

## Standing constraints (as of 2026-08-23)

Until explicitly lifted by Akshay:

- **Do not promote or activate without explicit approval from Akshay.** The approved Phase 6
  cohort has been promoted and activated — that approval was given once, for those 507
  occupations, and does not carry forward. Any further promotion run, any change to the
  public cohort, and any re-activation still needs Akshay to say so.
- **Do not activate further occupations** (`occupation_publications.activation_status`). 507
  are `public`; the remaining 509 are `staged`/`review_required` with no approved snapshot.
  In particular, do not activate the 5 out-of-cohort editorial pages (`graphic-designer`,
  `software-developer`, `ux-researcher`, `cybersecurity-analyst`, `financial-advisor`) to
  round out the launch — they have no production score, and one of them would render a
  pytest fixture row as its related-occupations list.
- **Do not flip `scoring_model_versions.is_active`.** JVS 1.0.3 is active; the validated
  engine model `JVS 2.0.0-phase4b` is registered inactive.
- **Do not modify the 11 legacy `occupation_scores` rows** or the legacy score history.
- **Do not fabricate** `salary_potential`, `future_demand` or `location_demand`. Their
  absence is why `/career-finder` is excluded from the launch surface.
- **No occupation-level Augmentation headline score.** Task-level augmentation only; the
  occupation-level column exists but is CHECK-pinned unpublishable.
- **Never run pytest against the `jobsvsai` database.** Use `./scripts/run-tests.sh`, which
  targets `jobsvsai_test`. The suite writes; see *Databases* below.

## The two score stores — do not confuse them

| | Legacy | Production |
|---|---|---|
| Tables | `occupation_scores`, `score_derivations`, `score_history`, `task_ai_scores` | `production_occupation_score_snapshots` + factor/task contribution tables |
| Model family | `legacy-jvs-1` (JVS 1.0.3) | `jobsvsai-engine-v2` (JVS 2.0.0-phase4b) |
| Written by | `worker/jobs.py` | promotion runs only |
| Serves | `/career-finder`, `/admin/jobs/{slug}/derivation` | everything else public |

Database triggers enforce the split in both directions. `worker/jobs.py` also fails fast if
the active model is not the legacy family.

**All public score currency flows through `current_production_occupation_scores`, composed
via `backend/app/repositories/production_scores.py`.** Never write a bespoke "latest score"
clause — divergent ones previously let readers disagree about which row was live.

Publication is separate from score existence: a production score does not make an occupation
public. `backend/app/repositories/publication.py` holds the gate.

## Known traps

- `scoring/phase5_analysis.py` recommends `launch_pool[:400]` — a truncation to
  `THRESHOLDS["launchTargetCount"]`, not a quality boundary. Its `launchMinimumCoverage` (80)
  and `launchMinimumConfidence` (75) are **sort keys, not filters**. The "~400 recommended
  occupations" in the Phase 5 report means "the 400 best-sorted non-error candidates".
  `scoring/phase6_launch_triage.py` supersedes it and enforces those thresholds instead.
- Two of six replacement-risk factors are provisional models (adoption pressure,
  labour-market resilience) carrying 25% of the weight for **every** occupation. The triage
  excludes occupations *sensitive* to them; those that pass are ones where the weak model
  happened not to move the score, which is not the same as validation. **After Phase 5B this
  is the binding constraint**: 106 occupations fail the 3-point sensitivity rule and 59 are
  blocked by nothing else, 28 of them in SOC 47 (construction).
- **A coverage number can measure the mapper rather than the corpus.** Phase 5's mapper
  stopped at the 70% gate (`COVERAGE_THRESHOLD`, `generate_phase5_candidate_mappings.py`), so
  coverage clustered at 70–75 and the 80% launch gate rejected 868 of 878. Phase 5B mapped
  the skipped tasks to an 85% completion target and the cohort went 8 → 507 with no
  threshold changed. Before concluding that a distribution reflects data quality, check
  whether a stopping rule produced it. Three thresholds stay distinct and must never be
  conflated: **70** scoring eligibility (occupation formula `minimumWeightedCoverage`),
  **85** mapping completion (`phase5b-mapping-completion-v1`), **80** launch gate
  (`phase6_launch_triage`).
- 311 occupations cannot defensibly reach 80% — zero mappable tasks remain and 20–77% of
  their weighted total is ambiguous O\*NET task text. That is a source-data limit, not an
  engineering backlog. Do not loosen the ambiguity rule to recover them.
- 512 editorial `occupations` rows exist: the 507 cohort pages (503 created, 4 updated in
  place) plus 5 legacy pages outside the cohort. None are empty shells. The 4 pre-existing
  cohort pages moved category when the SOC-derived job families were adopted — see
  `PHASE6_ACTIVATION_AUDIT.md` §3.
- The production store holds **one** non-fixture run — `phase6-promotion-2026q3-v1`
  (id 30), `completed`, 507 snapshots — and `current_production_occupation_scores` returns
  those 507. Everything else in the store is a pytest architecture fixture: rolled-back
  `architecture_test_fixture` runs, whose count **grows every time the suite runs** (73 → 78
  during one reconciliation session). Fixtures are left behind deliberately — the store is
  append-only and rollback is a status change, not a delete. Never quote a raw row or run
  count as a fact; count non-fixture runs.
- **Public content cannot be completed before promotion**, because `jobsvsai_verdict` is
  generated from a promoted snapshot. This played out as expected: content run 1
  (`phase6-content-2026q3-v1`) staged 507 candidates all `incomplete`; content run 2
  (`phase6-content-postpromotion-2026q3-v1`) ran after promotion and completed all 507. Both
  runs staged their own 6,470 related-occupation rows, so that table holds 12,941 — the
  reader takes `max(content_run_id)` per identity, so per-run counts are what matter.
  `public_occupation_content_runs.promotion_run_id` is never written by
  `run_public_content.py`; recover the link through `verdict_snapshot_id` instead.
- Test baselines depend on database state, so compare failure *sets*, not counts. On a
  database without the O\*NET import and Phase 4/5 runs (`create-test-db.sh --migrations`),
  42 fail. On a `jobsvsai_test` cloned from the current dev database: **111 passed, 0
  failed**.
- `test_admin_phase5_exposes_filters_full_provenance_and_isolation` reads the ambient count
  of public occupations, which the session-scoped `published_occupations` fixture changes
  while it is alive. It asserts against the live count for that reason; the Phase 5
  guarantee it exists to protect is `runs_with_public_activations`, which stays pinned to 0.
- The backend image bakes in a stale copy of `backend/tests`; the compose file does not mount
  it. `scripts/run-tests.sh` mounts it for you — if you invoke pytest by hand you must add
  `-v "$PWD/backend/tests:/app/tests:ro"` or your test edits are invisible.
- **pytest writes.** It creates fixture promotion runs, snapshots, contributions and
  canonical identities, and it flips `occupation_publications` rows to exercise the gate.
  That is why it must never point at `jobsvsai`. See *Databases* below.

## Commands

Scoring and enrichment modules use a relative import with a bare-name fallback, so they need
their own directory on `PYTHONPATH`. `-m scoring.x` alone fails on the nested imports.

```bash
# Launch-quality triage (read-only, no AI calls). --source-run-version names the candidate
# run; without it the most recent bounded_corpus run is used.
docker compose run --rm worker python -m scoring.run_phase6_launch_triage \
    --run-version phase6-triage-postcoverage-2026q3-v1 \
    --source-run-version phase5b-coverage-completion-2026q3-v1 --dry-run

# Phase 5B coverage completion — deterministic, zero AI calls. --dry-run reports what it
# would map without writing. Creates a new namespace; never mutates Phase 5.
docker compose run --rm -e PYTHONPATH=/app/enrichment backend \
    python /app/enrichment/generate_phase5b_coverage_completion.py --dry-run

# Phase 5B scoring, and its deterministic replay
docker compose run --rm -e PYTHONPATH=/app/scoring worker \
    python -m scoring.run_phase5b_coverage_completion \
    --run-version phase5b-coverage-completion-2026q3-v1 --run-kind bounded_corpus

# Phase 5B vs Phase 5 analysis (read-only; every number in the 5B reports)
docker compose run --rm -e PYTHONPATH=/app/scoring worker \
    python -m scoring.report_phase5b_completion --out /tmp/phase5b.json

# Deterministic public content generation (staged; does not touch `occupations`).
# run_key is unique — phase6-content-2026q3-v1 and -postpromotion- are both taken.
docker compose run --rm worker python -m ingestion.run_public_content \
    --run-version <new-run-version> --dry-run

# Tests — ALWAYS via this script. It targets jobsvsai_test, never the dev database,
# and prints the resolved host/database/environment before pytest connects.
./scripts/run-tests.sh -q

# One-time (or whenever you want a clean slate): build the isolated test database.
./scripts/create-test-db.sh            # clone of the dev DB; full 111-test baseline
./scripts/create-test-db.sh --migrations  # schema only, no ingested data

# Any read-only look at the real database. Writes are rejected by the server.
./scripts/psql-readonly.sh -c "SELECT count(*) FROM occupation_publications;"
```

Current runs on the dev database: Phase 5 `phase5-bounded-corpus-v2-2026q3` (id 2), Phase 5B
`phase5b-coverage-completion-2026q3-v1` (id 4) and its replay (id 5); triage runs
`phase6-triage-2026q3-v1` (baseline, cohort 8) and `phase6-triage-postcoverage-2026q3-v1`
(cohort 507); promotion run `phase6-promotion-2026q3-v1` (id 30, completed, 507); content
runs `phase6-content-2026q3-v1` (id 1, pre-promotion, all incomplete) and
`phase6-content-postpromotion-2026q3-v1` (id 2, all 507 complete — this is the live one).
All phase5 and phase6 tables are append-only by trigger.

Admin console: `/admin/production-scores` inspects the production store read-only —
candidate vs snapshot, derivations, versions, publication consistency, approval eligibility.

## AI News — separate from occupation scoring

`reports/AI_NEWS_V1_ARCHITECTURE.md` is the full design. Migration `029_ai_news_v1.sql`.

**Jobs Impact is a news-significance indicator for one event. It is not AI Exposure and not
Replacement Risk.** No `news_*` table has a foreign key into `occupations`,
`canonical_occupation_identities`, `occupation_publications`,
`production_occupation_score_snapshots` or `scoring_model_versions`, and a test asserts that
by querying `information_schema`. `job_area` is free editorial text, never a SOC code —
linking the two is the one change that would create the coupling this design prevents.

- `news-impact-v1` lives in `backend/app/news/impact_policy.py` and nowhere else. Weights
  30/25/20/15/10, `ROUND_HALF_UP` to two decimals, bands `<=34` low / `35-69` medium /
  `>=70` high. Scores carry two decimals, so 34.01-34.99 is medium under the literal rule.
- A provider returns five factors and a confidence, never a level. Confidence below 0.80
  forces `review_required`.
- The numeric score is **internal for V1**; the public payload omits it entirely rather than
  hiding it in the UI.
- Publication has one entry point, `repositories.news.publish()`, which refuses with every
  blocker at once. `set_status()` refuses `published` and `archived` outright — archiving
  needs an actor, which a status-string helper cannot supply.
- **Archive is not reject** (migration 032). Rejecting clears `published_at`; archiving
  preserves it, because an article that was published genuinely was. Neither is public.
  Restore returns to `review_required`, never straight to public.
- **Regenerate rewrites in place**, never creating a second article — the "one candidate, one
  article" rule has no exception. Refused for published articles, when generation is
  disabled, at the daily cap, and for hand-written articles; every refusal costs zero quota.
- Overrides never overwrite `automated_impact_score` / `automated_impact_level`.
- No LLM provider is implemented. `NullGenerationProvider` refuses rather than returning
  placeholder prose. `NEWS_AUTO_PUBLISH` must stay false.

## AI News Phase 2 — ingestion

`reports/AI_NEWS_PHASE2_INGESTION.md`. Migration `030_ai_news_phase2_ingestion.sql`.
Disabled by default; no schedule is active.

**Ingestion and generation are gated separately** (Phase 4 Step 1):
`NEWS_INGESTION_ENABLED` and `NEWS_GENERATION_ENABLED`, both defaulting to false. The single
`NEWS_ENABLED` is deprecated but still honoured — an explicitly set new flag wins, otherwise
the legacy flag applies to both, otherwise disabled. The fields are `bool | None` precisely so
"explicitly set" stays distinguishable from "left at default". Never read `news_enabled`
directly; use `settings.ingestion_enabled` / `settings.generation_enabled`.

Compose passes the new flags as `${...:-}` (empty), **not** as an explicit `false`: an
explicit false would outrank `NEWS_ENABLED` and silently disable an environment running on
it. A `field_validator` maps a blank string to None, because compose interpolates an unset
variable to `""` and pydantic cannot parse that as a bool.

- Nine **verified** free RSS feeds seeded as data. Anthropic and Meta AI are deliberately
  absent — no public feed exists, and Phase 2 does not scrape. Adding a source is an INSERT.
- `news-relevance-v1` (`backend/app/news/relevance.py`) is **presence-based, not
  count-based**: counting hits rewarded keyword-stuffed corporate posts over real headlines.
  Thresholds 40 candidate / 60 confident. The **source floor** lets an opaque first-party
  headline through but requires a positive signal, so origin alone never rescues a funding
  or appointment post.
- `news-dedupe-v1` (`backend/app/news/dedupe.py`) — Jaccard over tokens and 2-word shingles,
  threshold **0.55**, 48h window. Genuine restatements score 0.58-1.00, different events
  0.00-0.38. **Biased toward false negatives on purpose**: a wrong merge destroys a candidate
  nothing downstream can recover.
- Feed XML is parsed by `defusedxml`, not stdlib — stdlib ElementTree expands internal
  entities (billion laughs), which was verified, not assumed.
- Feed HTML is reduced to plain text at ingestion with **decode-then-strip** order. The
  obvious order is wrong: stripping first leaves `&lt;script&gt;`, which the later decode
  turns into a live tag.
- Lookback window and per-feed cap exist because the OpenAI feed alone holds 1,143 entries
  (Hugging Face 846) — confirmed by the live run, not estimated.
- **A 48h lookback yields nothing on a normal day.** First-party labs publish every few days,
  so a cold start ingests almost zero; the closest live item missed the window by 5 hours.
  The default is correct for 2-hourly steady-state polling. **The first production run should
  pass a wider one-off window** via `run_ingestion(lookback_hours=...)`.
- Near-dedupe is still calibrated only against constructed cases: the live sample contained
  zero same-event duplicates, so the 0.55 threshold is unvalidated on real data.
- **Operator CLI**: `python -m app.news.cli {ingest|candidates|sources|runs}`. `ingest
  --dry-run` runs the whole pipeline and writes nothing — no items, no run row, no source
  health. It imports neither the generation service nor a provider, so it *cannot* generate
  or publish; a test asserts that by inspecting its imports.
- A dry run tracks fingerprints accepted **within the same run**. Without that it missed
  in-batch near-duplicates (a live run sees them because each insert is committed) and
  over-reported candidates. A test asserts dry and live reach identical decisions.
- `processed` means converted into an article. Admin triage cannot set it.
- Ingest items have **no public route and no public schema**. They are internal triage
  material.

## AI News Phase 3 — Gemini generation

`reports/AI_NEWS_PHASE3_GEMINI.md`. Migration 031. Disabled by default; no scheduler,
`NEWS_AUTO_PUBLISH=false`.

- **Use `client.models.generate_content`, not `client.interactions.create`.** The docs
  feature Interactions, but it is flagged experimental by the SDK and changed incompatibly in
  May 2026 — it now requires google-genai >= 2.0.0 and 400s earlier callers. This was found by
  the live run failing all five calls. `google-genai` is pinned `>=1.40,<2` for that reason.
- The model returns five factors and a semantic verdict. It never returns an impact level and
  the response schema gives it no field for one; `news-impact-v1` computes score and level.
- Validation refuses rather than coerces — an out-of-range factor is an error, not something
  to clamp. Unknown tags are dropped so one invented tag cannot cost a good brief.
- Rejections are kept: no article, item becomes `ignored`, and the verdict, confidence and
  reason are retained. That record is the best input for calibrating the prompt.
- Retries cover 429/5xx/timeout only, bounded at 3. Schema-invalid and safety refusals are not
  retried — they fail identically and only burn quota.
- **The free tier sustained roughly 3 generation calls per session** before 429s. Defaults
  are now sized to that: `NEWS_DAILY_GENERATION_LIMIT=5`, `NEWS_GENERATION_BATCH_SIZE=2`.
  Raise them only on a paid tier.
- **The test suite blanks NEWS_LLM_PROVIDER and NEWS_LLM_API_KEY for every test** (autouse
  fixture in `conftest.py`). The suite runs with the developer's real environment, so without
  it a test that forgot to inject a fake provider would call the live API. Same idea as the
  test-database guard.
- The 0.70 semantic-confidence threshold is still unexercised — every live verdict came back
  at 0.95.
- `NEWS_*` must be listed in the compose `environment` blocks: `.env` is in `.dockerignore`
  and is not mounted, so pydantic's `env_file` never sees it inside a container.

## Databases — development vs test

Two databases on the same local PostgreSQL server. They must never be confused.

| | Development (`jobsvsai`) | Test (`jobsvsai_test`) |
|---|---|---|
| Holds | the promoted Phase 6 state — 507 public occupations, 1 real promotion run | a disposable clone |
| Used by | the running stack (backend, worker, frontend) | pytest, and nothing else |
| Writes allowed | only by deliberate, approved runs | freely; recreate whenever |
| Carries `test_database_marker` | **no** | yes |

**Never run pytest against `jobsvsai`.** The suite is not a read-only observer: it creates
fixture promotion runs, production snapshots, factor and task contributions and canonical
identities, and it flips `occupation_publications` rows to exercise the publication gate.
Before the guard existed, `docker compose run backend pytest` inherited the development
`DATABASE_URL` from `.env` and left rolled-back fixture runs in the real database.

### Mac development workflow

```bash
docker compose up --build          # dev stack on jobsvsai; app at :3000, API at :8000
./scripts/psql-readonly.sh         # inspect the dev database; server rejects any write
```

Use `psql-readonly.sh` for every verification or investigation pass. It sets
`default_transaction_read_only=on`, so a mistyped statement fails instead of writing.

### Test workflow

```bash
./scripts/create-test-db.sh        # build jobsvsai_test (clone of dev; full baseline)
./scripts/run-tests.sh -q          # run the suite against it
./scripts/run-tests.sh tests/test_integration.py -x   # extra args pass through to pytest
```

`create-test-db.sh` briefly stops backend/worker/frontend, because `CREATE DATABASE ...
TEMPLATE` needs the source to have no connections, then restarts them. It only ever reads
the development database. Use `--migrations` for a schema-only test database built from
`migrations/*.sql` with no data copied at all.

### Verifying which database a test run targets

`run-tests.sh` prints the host, database name and environment before pytest opens a
connection, and pytest's own header repeats the resolved target. Passwords are never
printed. To check by hand:

```bash
./scripts/run-tests.sh --collect-only -q | head -5
```

### The four guards

`backend/tests/db_guard.py` refuses to start unless all four pass. They are independent, so
defeating one does not get you to the database:

1. `TEST_DATABASE=true` must be set — an explicit opt-in no service sets.
2. `ENVIRONMENT` must not be production/prod/live/staging.
3. The database name must match `^test_|_test$|_test_` and must not be `jobsvsai`,
   `postgres`, or a template.
4. The connected database must contain `test_database_marker`, which only
   `create-test-db.sh` writes. **This is the check the environment cannot fake** — a URL can
   claim any name, but the table exists only in a database created as a test database.

Checks 1-3 run at conftest import, before an engine is built. Check 4 runs in a session-scoped
autouse fixture. `ingestion/tests/conftest.py` applies the same guard, because those tests
connect with asyncpg directly and would otherwise bypass the backend conftest.

## Next steps

The launch sequence is complete. The provisional-sensitivity disclosure was decided **yes,
per page** (`phase6-provisional-disclosure-v1`), promotion and activation both ran on
2026-08-21, content run 2 filled every verdict, the 512 editorial rows exist, and the related
read path now uses `public_occupation_related_occupations`. See
`reports/PHASE6_STATE_RECONCILIATION.md` for the verified state. What remains:

1. Career Finder decision — still excluded, still on legacy data, still not fabricating
   salary/demand/location values. `education_requirement` defaulted to 2 on the 503 new
   editorial rows and is read only by career-finder; it is not a real value.
2. Run `reports/investigate_occupation_scores.sql` (the 11 legacy rows; still never executed).
3. Confirm the SOC-derived category taxonomy, which replaced the legacy 7 categories for
   cohort pages and moved 4 pre-existing pages between categories
   (`PHASE6_ACTIVATION_AUDIT.md` §3). Reverting is a re-run, not a rebuild.
4. Decide what to do about the 38 activated publications carrying an O\*NET title-review flag
   (`PHASE6_ACTIVATION_AUDIT.md` §11) — wording only, no score or evidence problem.
5. Consider recording activation at run level. Promotion writes a full audit row; activation
   leaves only `updated_at` timestamps, so it cannot be reconstructed from the database alone.

The truncation-bias experiment (orientation finding 7.5) is partly answered: across 70→85,
the bias term is small and unsigned (signed mean +0.07 vs absolute 0.86, correlation 0.02).

## Working style

Prefer small, reversible changes. Maintain provenance. Protect production data. Do not weaken
quality gates to improve metrics, and do not publish uncertain scores to increase page count.
The sophistication belongs in the intelligence engine, not in an overloaded interface. Mobile
(360–430px) matters; do not regress responsive behaviour.
