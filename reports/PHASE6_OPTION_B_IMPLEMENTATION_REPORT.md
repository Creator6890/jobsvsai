# Phase 6 — Option B production score store: implementation report

Date: 2026-08-20
Status: **schema and read-path plumbing complete. Nothing promoted, nothing activated,
`scoring_model_versions.is_active` unchanged, no formula touched.**

## 1. Final schema

Migration `025_production_score_store.sql`. Four tables, two views, one nullable column
added to an existing table.

**`production_promotion_runs`** — the unit of promotion and rollback, and the only table
whose rows ever change. `source_kind` is `phase5_candidate` or `architecture_test_fixture`
(the same convention migration 008 uses for its seeded mapping sets); a `phase5_candidate`
run must name both `source_namespace_id` and `source_calculation_run_id`. Carries
`input_version_bundle`, `selection_policy`, `reconciliation`, `input_hash`, status, counts
and rollback bookkeeping.

**`production_occupation_score_snapshots`** — immutable, keyed `(promotion_run_id,
identity_id)`. Holds AI Exposure, Replacement Risk, numeric confidence, weighted task
coverage, the four task counts, both gate statuses, `scoring_eligibility`, `publishable`,
the eight version fields (frontier index + track, structural proxy model, base proxy model,
occupation formula, task formulas, taxonomy, rubric, evidence policy), `calculated_at` and
`promoted_at` separately, `exact_inputs`, `provisional_sensitivity`, `warnings`,
`blocking_reasons`, `reconciliation` and `input_hash`.

`occupation_id` is nullable so scores can be promoted and reviewed before the editorial
`occupations` row exists. `augmentation_potential` is nullable and paired with
`augmentation_publishable BOOLEAN NOT NULL DEFAULT false CHECK (augmentation_publishable =
false)` — the column exists for future use and the database currently forbids marking it
publishable at all.

Two CHECK constraints restate the validated gates rather than trusting the promoter:
`publishable` requires `production_ready` + both gates passed + coverage ≥ 70 + confidence
≥ 70; `scoring_eligibility='production_ready'` requires both gates passed.

**`production_score_factor_contributions`** — six rows per snapshot. `factor_key`,
`factor_label`, `value`, `source_proxy_value`, `transformation`, `weight`,
`weighted_contribution`, `is_provisional_proxy`, `proxy_model_version`, `placeholder`,
`display_order`. A partial index on `is_provisional_proxy` makes provisional exposure a
one-line query. `CHECK (is_provisional_proxy = false OR proxy_model_version IS NOT NULL)`
prevents an unattributed provisional factor.

**`production_score_task_contributions`** — keyed `(snapshot_id, onet_task_id)`. Carries
`onet_soc_code`, statement + hash, `source_mapping_set_id`, the three task metrics plus task
AI exposure and confidence, source importance/frequency/weight, normalized covered weight
and exposure contribution. **No FK to the legacy `tasks` table**, by design.

**`current_production_occupation_scores`** — `DISTINCT ON (identity_id) … WHERE run.status =
'completed' ORDER BY identity_id, run.created_at DESC, run.id DESC, snapshot.id DESC`. Fully
deterministic; no ambiguity is possible.

**`publication_snapshot_consistency`** — reports every publication as `consistent`,
`no_approved_snapshot`, `approved_snapshot_withdrawn` or `approved_snapshot_superseded`.

**`occupation_publications.approved_score_snapshot_id`** — nullable FK, plus a partial
index. Publication state itself is unchanged.

## 2. Snapshot immutability guarantees

Verified by execution against PostgreSQL, not by inspection:

| Attempted | Result |
|---|---|
| `UPDATE` a snapshot | rejected — *"…is append-only"* |
| `DELETE` a snapshot | rejected |
| `UPDATE`/`DELETE` a factor contribution | rejected |
| `UPDATE`/`DELETE` a task contribution | rejected |
| `DELETE` a promotion run | rejected — *"roll a run back instead of deleting it"* |
| Change a run's `input_hash`, source, model, policy, bundle or `created_at` | rejected — *"definition columns are immutable"* |
| Move a settled run back to `in_progress` | rejected — *"a settled promotion run cannot return to in_progress"* |
| `UPDATE` a run's status to `rolled_back` | **allowed** — this is the rollback lever |
| Insert `publishable=true` while a gate fails | rejected by CHECK |

Snapshots and derivations reuse the existing `prevent_ai_enrichment_history_mutation()`
trigger. Runs use a new `prevent_promotion_run_redefinition()` trigger that permits only
status and rollback bookkeeping. Because nothing is ever deleted, no FK cascade is declared —
a cascade would imply a deletion path the triggers forbid.

Covered by `tests/test_production_score_store.py`:
`test_snapshots_reject_update_and_delete`, `test_derivation_rows_reject_update_and_delete`,
`test_promotion_run_definition_is_frozen_but_status_may_move`,
`test_publishable_requires_the_validated_gates`.

## 3. Promotion transaction

Not yet written as production code — deliberately, since promotion is out of scope for this
phase. The shape is fixed by the schema and is exercised end-to-end by
`tests/production_fixtures.py::build_promotion_run`, which writes a complete run the way a
real promotion must:

1. `INSERT production_promotion_runs (status='in_progress')` with the version bundle read
   from the source run, never hardcoded.
2. Select candidates: `phase5_occupation_scores` for the declared `calculation_run_id`,
   `candidate_status='review_ready'`, identity in the approved cohort.
3. Per candidate, assert before insert: `input_hash` matches; both gate statuses are
   `passed`; coverage ≥ 70 and confidence ≥ 70 re-asserted rather than assumed; the
   candidate's `calculation_run_id` matches the run's declared source.
4. Insert snapshot + six factor rows + task rows, copying values and `input_hash` verbatim.
5. Reconcile in-transaction: `Σ weighted_contribution ≈ replacement_risk` and
   `Σ exposure_contribution ≈ ai_exposure`, both within 0.01. Any mismatch aborts everything.
6. Assert the promoted count equals the approved cohort size.
7. `UPDATE … SET status='completed', completed_at=now(), occupation_count=n`.

Steps 5 and 6 are enforced today by
`test_factor_contributions_reconcile_to_replacement_risk` and
`test_task_contributions_reconcile_to_ai_exposure`, which compute the sums from persisted
rows rather than restating a constant.

## 4. Rollback procedure

Two independent levers, both verified.

**By promotion run.** `UPDATE production_promotion_runs SET status='rolled_back',
rolled_back_at=now(), rolled_back_by=…, rolled_back_reason=…`. The currency view falls back
to the previous completed run, or returns nothing. No snapshot is modified or deleted, and
Phase 5 is never consulted. A rolled-back run cannot be revived — a correction is a new run.

Verified by `test_rollback_restores_the_previous_run_without_touching_snapshots` (snapshot
count identical before and after; currency falls back; revival rejected) and, at API level,
by `test_public_surfaces_require_a_promoted_score` (rolling the run back empties
`/occupations` and `/rankings` and 404s the detail route, while every snapshot survives).

**By publication status.** `UPDATE occupation_publications SET
activation_status='inactive'`. Per-occupation, no score-side action. Verified by
`test_public_surfaces_require_an_active_publication`.

**Required guard:** a run rollback must also demote publications whose
`approved_score_snapshot_id` belongs to that run. `publication_snapshot_consistency` reports
exactly those rows.

## 5. Publication / snapshot consistency behaviour

`publication_snapshot_consistency` classifies every publication row:

- `consistent` — approved snapshot is the current one for that identity
- `no_approved_snapshot` — published without a recorded approval
- `approved_snapshot_withdrawn` — the approving run was rolled back
- `approved_snapshot_superseded` — a newer completed run has replaced it

`test_publication_snapshot_consistency_flags_withdrawn_approvals` approves a page against a
run, confirms `consistent`, rolls the run back, and confirms the state flips to
`approved_snapshot_withdrawn`.

The core separation holds and is tested: an occupation with a `publishable` production
snapshot is still invisible until `activation_status='public'`, and a published occupation
with no completed promotion run is invisible too. Both conditions are required.

## 6. Public readers migrated

All score currency now resolves through `current_production_occupation_scores`, composed via
`backend/app/repositories/production_scores.py`. No caller writes its own "latest" clause.

| Reader | Before | After |
|---|---|---|
| `/occupations` list | `LATERAL occupation_scores ORDER BY calculated_at DESC` (no tiebreak) | shared join to the view |
| `/occupations/{slug}` | same | shared join |
| `/occupations/search` | same | shared join |
| occupation task evidence | `occupation_tasks` + `task_ai_scores` | `production_score_task_contributions`, O\*NET identity |
| related careers | `LATERAL occupation_scores` (no tiebreak) | `production_replacement_risk_scalar()` through the view |
| `/rankings` | `LATERAL occupation_scores` (no tiebreak) | shared join |
| `/careers/recommendations` | legacy | **unchanged — legacy, by decision** |
| `/admin/jobs/{slug}/derivation` | legacy | **unchanged — legacy, still reconciles** |

The three divergent latest-row selections are gone from the migrated readers.

API payload changes: `confidence` is numeric 0–100 (was `High|Medium|Low`);
`weightedTaskCoverage` and `provisionalWeightShare` added; `marketResilience` →
`labourMarketResilience`; `resilientTasks` → `hardestToAutomateTasks` (lowest automation
feasibility — using a validated metric for what it actually means rather than inventing a
resilience claim); tasks carry `onetTaskId`, `automationFeasibility`, `augmentationPotential`.
`trend`, `salaryPotential` and `futureDemand` are **removed**: the engine produces none of
them and they were not fabricated. `ScoreFactor` gained optional `isProvisionalProxy` and
`proxyModelVersion` so provisional provenance survives the translation into the API shape.

Career Finder is excluded from the launch surface: removed from `SiteHeader` navigation and
from `sitemap.ts`, and `/career-finder` added to the `robots.ts` disallow list. The route
still works, still runs on legacy data, and still enforces the publication gate.

## 7. Remaining legacy dependencies

1. **`/careers/recommendations`** ranks on `salary_potential`, `future_demand` (legacy
   hand-authored columns) and `market_signals.location_demand` (seeded demo data). None
   exists in the engine. This is the reason the feature is out of launch.
2. **`career_relationships`** — hand-seeded adjacency. Related careers now take their
   replacement risk from the production store, but *which* careers are adjacent is still
   legacy data. Real adjacency should come from O\*NET `related_occupations`.
3. **`/admin/jobs/{slug}/derivation`** reads `occupation_scores` + `score_derivations`. Left
   intact deliberately; there is no admin inspector for the production store yet.
4. **The editorial `occupations` table** still supplies slug, category, summary and verdict.
   Only 9 rows exist. This is the content workstream, unchanged.
5. **`scoring_model_versions`** holds only `JVS 1.0.3`, still `is_active`. The v2 model has
   **not** been registered — registering it is part of the 7.2 activation work, which is
   pending your launch-quality review.
6. **`worker/jobs.py`** is still unguarded and still writes `occupation_scores` under
   whichever model is active. Harmless today; must be guarded or retired before any flip.
7. All 11 legacy `occupation_scores` rows, `score_derivations`, `score_history` and
   `task_ai_scores` are untouched, as instructed.

## 8. Still required before Phase 5 candidate promotion

1. **Run the 11-row investigation** (`reports/investigate_occupation_scores.sql`) and confirm
   the attribution on the live database.
2. **Anomaly triage → approved cohort.** Promotion needs an explicit approved identity list;
   the schema deliberately has no "promote everything" path.
3. **Write the promotion transaction** as production code with the assertions in §3, plus a
   rollback procedure that demotes affected publications.
4. **Register the v2 scoring model** (`is_active=false`) so snapshots can reference something
   truthful. Snapshots currently reference `JVS 1.0.3`, which is wrong for engine scores and
   must be corrected before any real promotion.
5. **Guard or retire `worker/jobs.py`** so it can never stamp legacy arithmetic with a v2
   model id.
6. **Admin inspector** for the production store — there is currently no UI for it.
7. **Editorial content** for the cohort: slug, category, summary, verdict, and an adjacency
   source. Snapshots can be promoted before this, but pages cannot be published.
8. **Methodology page** rewrite: the v2 factor set, numeric confidence, coverage, and an
   honest description of the provisional inputs now surfaced as `provisionalWeightShare`.
9. **Truncation-bias experiment** (orientation finding 7.5), still outstanding.
10. **Career Finder scoping decision** (§7.1).

## Verification

PostgreSQL 16, all 25 migrations applied to a clean database.

- Control tree (original repository, migrations 001–024): **13 passed, 42 failed**.
- Modified tree (migrations 001–025): **28 passed, 42 failed**.
- The failure sets are **identical**. The 42 are pre-existing phase-validation tests that
  require the O\*NET import and Phase 4/5 runs, absent from a throwaway database.
- Net: 15 new passing tests, zero regressions.
- Frontend: `tsc --noEmit` clean across all 43 source files (after `next typegen`);
  `eslint` clean.
- `test_legacy_occupation_scores_are_untouched` asserts the active model is still
  `JVS 1.0.3`; `test_no_phase5_candidate_was_promoted` asserts every snapshot in the database
  belongs to an explicitly flagged architecture fixture and that
  `source_candidate_score_id IS NULL` everywhere.
