# JobsVsAI — working context

Career intelligence platform. Answers "how is AI likely to affect my job, and what should I
do about it?" using a proprietary interpretation layer over O\*NET 30.3.

**Read `reports/PHASE6_LAUNCH_PLAN.md` first.** It is the current state of play: the
507-occupation cohort is the launch cohort, an occupation is held back only for a concrete
readiness reason, and the plan tracks all 11 launch steps.
`reports/PHASE6_POST_COVERAGE_TRIAGE_REPORT.md` is how that cohort was derived.
`reports/PHASE5B_COVERAGE_COMPLETION_REPORT.md` explains why the earlier 8-occupation cohort
was a pipeline artefact; `reports/PHASE5B_SCORE_DELTA_REPORT.md` shows what the added
evidence did to scores. `reports/PHASE6_LAUNCH_READINESS_REPORT.md` remains accurate on
schema, guards and admin surfaces, but its cohort question is superseded.
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

## Standing constraints (as of 2026-08-21)

Until explicitly lifted by Akshay:

- **Do not promote or activate without explicit approval from Akshay.** The launch policy
  is settled — the 507-occupation Phase 6 cohort *is* the launch cohort, and an occupation
  is held back only for a concrete readiness reason (see `PHASE6_LAUNCH_PLAN.md` §1) — but
  running the promotion and activating publications are still gated on saying so.
- **Do not activate occupations** (`occupation_publications.activation_status`).
- **Do not flip `scoring_model_versions.is_active`.** JVS 1.0.3 is active; the validated
  engine model `JVS 2.0.0-phase4b` is registered inactive.
- **Do not modify the 11 legacy `occupation_scores` rows** or the legacy score history.
- **Do not fabricate** `salary_potential`, `future_demand` or `location_demand`. Their
  absence is why `/career-finder` is excluded from the launch surface.
- **No occupation-level Augmentation headline score.** Task-level augmentation only; the
  occupation-level column exists but is CHECK-pinned unpublishable.

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
- Only 9 editorial `occupations` rows exist. A launch cohort needs hundreds — see the content
  pipeline below.
- The production store is **not empty**, but every row in it is a pytest architecture
  fixture: 171 snapshots across 19 `architecture_test_fixture` promotion runs, all
  `rolled_back`, which is why `current_production_occupation_scores` returns nothing. Zero
  non-fixture runs exist. Fixtures are left behind deliberately — the store is append-only
  and rollback is a status change, not a delete. Count non-fixture runs, not rows.
- **Public content cannot be completed before promotion.** Every staged content candidate is
  `incomplete` on `jobsvsai_verdict`, which is generated from a promoted snapshot. Content
  needs a second run after promotion; editorial `occupations` rows should be created once,
  after that, rather than as empty shells beforehand.
- Test baselines depend on database state, so compare failure *sets*, not counts. On a
  database without the O\*NET import and Phase 4/5 runs, 42 fail. On the current dev database
  with all migrations applied and `backend/tests` mounted: **108 passed, 0 failed**.
- `test_admin_phase5_exposes_filters_full_provenance_and_isolation` reads the ambient count
  of public occupations, which the session-scoped `published_occupations` fixture changes
  while it is alive. It asserts against the live count for that reason; the Phase 5
  guarantee it exists to protect is `runs_with_public_activations`, which stays pinned to 0.
- The backend image bakes in a stale copy of `backend/tests`; the compose file does not mount
  it. Mount it or test edits are invisible:
  `-v "$PWD/backend/tests:/app/tests:ro"`.

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

# Deterministic public content generation (staged; does not touch `occupations`)
docker compose run --rm worker python -m ingestion.run_public_content \
    --run-version phase6-content-2026q3-v1 --dry-run

# Tests — mount backend/tests or you are running the image's stale copy
docker compose run --rm -v "$PWD/backend/tests:/app/tests:ro" \
    backend python -m pytest tests -q
```

Current runs on the dev database: Phase 5 `phase5-bounded-corpus-v2-2026q3` (id 2), Phase 5B
`phase5b-coverage-completion-2026q3-v1` (id 4) and its replay (id 5); triage runs
`phase6-triage-2026q3-v1` (baseline, cohort 8) and `phase6-triage-postcoverage-2026q3-v1`
(cohort 507). All phase5 and phase6 tables are append-only by trigger.

Admin console: `/admin/production-scores` inspects the production store read-only —
candidate vs snapshot, derivations, versions, publication consistency, approval eligibility.

## Next steps

Tracked in `reports/PHASE6_LAUNCH_PLAN.md` §2. Steps 1, 2, 7 and 8 are done; 4 and 6 are
staged as far as they can go pre-promotion. What remains:

1. **Decide the provisional-sensitivity disclosure question** (plan §5). The 3-point rule
   itself is frozen; the live question is whether public pages disclose that 25% of
   replacement-risk weight is provisional. Recommended: yes, per page. Needed before the
   post-promotion content run, because it changes the verdict template.
2. **Promote** — approval gate. Command in §6 of the plan; dry-run and a full
   write-then-rollback have both passed.
3. Re-run the content pipeline under a new run version to fill `jobsvsai_verdict`.
4. Create editorial `occupations` rows from the completed content — once, not as shells.
5. Validate the 6,470 staged related-occupation rows and switch the read path to
   `public_occupation_related_occupations`.
6. **Activate publications** — approval gate.
7. Final public QA and deployment checks.
8. Career Finder decision — still excluded, still on legacy data, still not fabricating
   salary/demand/location values.
9. Run `reports/investigate_occupation_scores.sql` (the 11 legacy rows; still never executed).

The truncation-bias experiment (orientation finding 7.5) is partly answered: across 70→85,
the bias term is small and unsigned (signed mean +0.07 vs absolute 0.86, correlation 0.02).

## Working style

Prefer small, reversible changes. Maintain provenance. Protect production data. Do not weaken
quality gates to improve metrics, and do not publish uncertain scores to increase page count.
The sophistication belongs in the intelligence engine, not in an overloaded interface. Mobile
(360–430px) matters; do not regress responsive behaviour.
