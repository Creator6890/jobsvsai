# Phase 6 — Launch readiness report

Date: 2026-08-21
Status: **Nothing promoted. No occupation activated. `is_active` still JVS 1.0.3.**

## Read this first: what could not be executed

This session has file access to the repository but **no shell or database access** to the
machine running Postgres. Two requested items therefore could not be *run*:

- **Item 3 — the 11-row `occupation_scores` investigation.** The read-only script
  (`reports/investigate_occupation_scores.sql`) is delivered and unchanged. It has never been
  executed against real data.
- **Item 4 — triage across the 744 review-ready candidates.** The triage engine is built,
  unit-tested, and verified end-to-end against a synthetic Phase 5 run, but it has not seen
  the real corpus. **No cohort size is reported below, because inventing one would be worse
  than reporting none.**

Everything else is implemented and verified.

## Two findings that change the cohort question

Both are in `scoring/phase5_analysis.py`, and both bear directly on "do not target an
arbitrary cohort size":

1. `THRESHOLDS["launchTargetCount"] = 400`, and the recommendation is literally
   `launch_pool[:400]`. The ~400 figure in the Phase 5 report is a **truncation to a target**,
   not a quality boundary.
2. `launchMinimumCoverage` (80) and `launchMinimumConfidence` (75) exist in THRESHOLDS but are
   **never applied as filters** — only as sort keys, and described in the corpus report as
   "preferred". The sole hard exclusion was `severity == 'error'`.

The current recommendation is therefore "the 400 best-sorted non-error candidates". The new
triage inverts this: apply the gates, take everyone who passes, report the number.

---

## 1. Final recommended launch cohort size

**Not determined — the triage has not been run against the real corpus.**

To produce it:

```bash
docker compose run --rm worker python -m scoring.run_phase6_launch_triage \
    --run-version phase6-triage-2026q3-v1 --dry-run     # inspect first
docker compose run --rm worker python -m scoring.run_phase6_launch_triage \
    --run-version phase6-triage-2026q3-v1               # then persist
```

Read-only over every `phase5_*` table, no AI calls, no rescoring. It prints
`launchCohortSize`, `excludedCount`, `severityTotals` and `exclusionReasons`, and persists
per-occupation findings to `phase6_launch_triage_results`.

## 2. Excluded occupations and reasons — the policy that decides

`scoring/phase6_launch_triage.py`, policy version `phase6-launch-triage-v1`. Thresholds are
inherited verbatim from `phase5_analysis.THRESHOLDS` — these are the project's own declared
numbers; what changed is that they are now enforced.

**Critical — never launchable**

| Code | Why critical |
|---|---|
| `score_out_of_range` | Outside 0–100 is a calculation integrity failure. |
| `reconciliation_failed` | Stored contributions do not sum to the stored score. |
| `not_review_ready` | Did not clear the Phase 5 gates. |
| `high_replacement_despite_severe_constraints` | The surgeon case. The most reputationally damaging error available. |
| `low_replacement_despite_digital_routine_composition` | The inverse. Destroys credibility with the most AI-literate readers. |

**High — excluded from the initial cohort**

`weighted_coverage_below_launch_minimum` (<80) · `confidence_below_launch_minimum` (<75) ·
`provisional_input_sensitivity` (≥3-point swing when the provisional models are neutralised) ·
`single_factor_dependence` (>55% of the score from one factor) ·
`exposure_replacement_gap` (≥25 points) · `extreme_score` (≤5 or ≥95)

**Medium — launchable, flagged for editorial attention**

`single_task_dependence` (>25% of exposure from one task) ·
`related_soc_score_discontinuity` (SOC family spread >30) ·
`confidence_coverage_inconsistency` · `structural_proxy_missing_data`

**Low — informational, never excluding**

`provisional_models_in_use`. Recorded for every occupation: adoption pressure and
labour-market resilience are 25% of replacement weight for *all* of them. That is a
disclosure obligation, not a discriminator — the discriminator is the sensitivity measure.

**Cohort rule:** no critical and no high findings. Nothing else. No target size exists
anywhere in the module, and a test asserts its absence.

## 3. Warning severity counts

Not available — requires the run above. `severityTotals` and `exclusionReasons` are
persisted per run and surfaced in the admin console.

## 4. Editorial/content coverage for that cohort

The content pipeline is built and staged, not run:

- **Schema** — migration 028. `public_occupation_content_candidates` separates
  `source_*` columns (O*NET facts) from `jobsvsai_*` columns (interpretation) at the column
  level, with CHECK constraints binding a summary to its origin and a verdict to its snapshot.
- **Policy** — `ingestion/public_content_policy.py`, pure and unit-tested (11 tests).
  Title from O*NET preferred (editorial override always wins), deterministic ASCII slug, job
  family from the SOC major group with the source title retained, **summary = the O*NET
  description verbatim** with CC BY 4.0 attribution, verdict from a versioned template over
  persisted scores, aliases from source alternate titles.
- **Runner** — `ingestion/run_public_content.py`, smoke-tested against synthetic O*NET rows.
  Related occupations come from `onet_related_occupations`, not `career_relationships`.

Nothing factual is generated. A missing O*NET description stays NULL and the row is marked
`incomplete`; the database refuses to let it be called `complete`. Slug collisions abort the
run rather than being suffixed.

The verdict template keeps exposure and replacement distinct and names the dominant
structural constraint when a gap exists — the one sentence on the page most likely to be
quoted, so it is generated from numbers rather than written.

## 5. Related-career migration status

**Schema and pipeline ready; not yet serving.** `public_occupation_related_occupations` is
populated from O*NET. The public read path still uses `career_relationships` for *which*
careers are adjacent (it already takes their replacement risk from the production store).
Switching the reader over is a small change that should happen when the first content run
lands, not before — swapping to an empty table would silently empty the section.

## 6. v2 model registration status

**Done.** Migration 026 registers `JVS 2.0.0-phase4b`, `is_active = false`,
`methodology_family = 'jobsvsai-engine-v2'`. Weights copied verbatim from
`phase4b-occupation-score-v2-calibration` (migration 019):

```
taskAutomationExposure            0.35
aiCapabilityProximity             0.10
humanDependencyResistance         0.15
physicalDependencyResistance      0.15
adoptionPressure                  0.15   PROVISIONAL
labourMarketResilienceResistance  0.10   PROVISIONAL
```

Not harmonised with JVS 1.0.3 — different factor sets, different semantics, deliberately
different key names. The migration asserts at the end that JVS 1.0.3 is still active and
aborts if not. A test asserts the weights match migration 019 exactly.

`exposure_config` records the rest of the validated formula (task-exposure blend, 70%
coverage gate, confidence weights) so the registration is self-describing.

## 7. Worker guard status

**Guarded at three levels, all verified by execution.**

1. **Application** — `worker/jobs.py` raises `LegacyWorkerDisabled` if the active model's
   `methodology_family` is not `legacy-jvs-1`.
2. **Database** — `occupation_scores` and `score_derivations` reject any insert referencing a
   non-legacy model: *"occupation_scores holds legacy JVS 1.x arithmetic and cannot be
   written under model family jobsvsai-engine-v2."*
3. **Mirror guard** — `production_promotion_runs` and
   `production_occupation_score_snapshots` reject the legacy model, so the store cannot be
   fed legacy arithmetic either.

Cannot write production snapshots: the store is fed only by promotion runs and the worker has
no code path to them. Cannot alter Phase 5: every `phase5_*` table has carried an append-only
trigger since migration 024, asserted by test.

## 8. Methodology readiness

**Rewritten** (`frontend/src/app/methodology/page.tsx`). Now describes the actual engine: AI
Exposure vs Replacement Risk with the surgeon example, the three task-level metrics kept
separate, the six v2 factors with the two provisional ones visibly marked, the bottleneck
principle, the Frontier AI Capability Index (including the deliberately empty
technical-frontier track), the 70% coverage gate, numeric confidence, versioning and
reproducibility, limitations, and O*NET CC BY 4.0 attribution.

No occupation-level Augmentation headline. The page says explicitly that augmentation is
reported per task because the occupation-level figure has not been validated.

## 9. Admin inspector readiness

**Built and exercised.** `GET /admin/production-scores` and
`/admin/production-scores/{snapshot_id}`, plus pages at `/admin/production-scores`.
Read-only — it cannot promote, approve or activate.

Shows: candidate vs production snapshot side by side with deltas; exposure, replacement,
confidence, coverage; warnings and blocking reasons; provisional sensitivity; factor
contributions with per-factor provisional provenance; task contributions keyed to O*NET task
identity; all eight version fields plus input hash; publication/snapshot consistency;
approval eligibility; and an **independently recomputed reconciliation** — the inspector sums
the stored derivation itself rather than trusting the stored total.

The overview also surfaces the guardrails: active scoring model, and count of snapshots
promoted from real candidates (currently 0).

## 10. Exact blockers before score promotion

1. **Run the triage** (§1) and review the cohort and exclusions.
2. **Run the 11-row investigation** (`reports/investigate_occupation_scores.sql`).
3. **Approve an explicit identity list.** The schema deliberately has no "promote everything"
   path.
4. **Write the promotion transaction.** Still not written — correctly, since promotion is out
   of scope. Its shape is pinned by the schema and exercised by
   `backend/tests/production_fixtures.py::build_promotion_run`, including both reconciliation
   assertions.
5. **Run the content pipeline** for the approved cohort and review completeness.
6. **Create editorial `occupations` rows** from the staged content. Snapshots can be promoted
   before this; pages cannot be published without it.
7. **Switch related careers** to `public_occupation_related_occupations`.
8. **Career Finder decision** — still excluded, still on legacy data, still not fabricating
   salary/demand/location values.
9. **Truncation-bias experiment** (orientation finding 7.5) — still outstanding.

## Verification

PostgreSQL 16, all 28 migrations applied to a clean database.

- Control tree (original repo, migrations 001–024): **13 passed, 42 failed**
- Modified tree (migrations 001–028): **56 passed, 42 failed**
- **Identical failure sets.** The 42 are pre-existing phase-validation tests requiring the
  O*NET import and Phase 4/5 runs.
- Net: **43 new passing tests, zero regressions.**
- Frontend: `tsc --noEmit` and `eslint` both clean.

**End-to-end verification of the triage runner** against a synthetic Phase 5 run with three
deliberately-constructed candidates. It correctly excluded the nurse
(`high_replacement_despite_severe_constraints`, critical) and the clerk
(`low_replacement_despite_digital_routine_composition` plus three more, critical), and kept
the accountant. This caught a real bug: the runner queried `candidate.title`, which does not
exist — the column is `title_snapshot`. Fixed and re-verified.

**Guardrail assertions in the suite:** active model is still `JVS 1.0.3`; every production
snapshot has `source_candidate_score_id IS NULL`; no occupation is public; legacy arithmetic
cannot be stamped with the engine model; the production store rejects the legacy model;
Phase 5 data is immutable.
