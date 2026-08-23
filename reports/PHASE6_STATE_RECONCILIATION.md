# Phase 6 — State reconciliation

Date: 2026-08-23
Status: **Promoted and activated.** 507 occupations are public and serving JVS 2.0.0-phase4b
production snapshots. `scoring_model_versions.is_active` is still **JVS 1.0.3**.

## Why this document exists

Most Phase 6 reports carry the banner *"Nothing promoted. No occupation activated."* That
banner was true when those reports were written and is false now. Promotion ran on
2026-08-21 at 04:10 UTC and activation at 08:00 UTC. Anyone reading `PHASE6_LAUNCH_PLAN.md`
first — as `CLAUDE.md` instructed until this document landed — would form an incorrect
picture of the system.

This is a reconciliation, not a new audit. Every figure below was re-derived directly from
the dev database in a read-only session (`default_transaction_read_only=on`) and from the
running API, without relying on any existing report. **No data was changed.**

**`PHASE6_ACTIVATION_AUDIT.md` is not stale.** It already records the promotion and the
activation accurately and in more detail than this document, including the per-surface live
verification. It is the authoritative post-promotion record; this document exists to say so
and to mark which of its neighbours are out of date.

## 1. Verified current state

| Check | Value | Source |
|---|---|---|
| Non-fixture promotion runs | **1** | `production_promotion_runs` |
| Run key | `phase6-promotion-2026q3-v1` (id 30) | |
| Status / completed | `completed`, 2026-08-21 04:10:25 UTC | |
| Actor | `system:phase6-promoter` | |
| Promotion policy | `phase6-production-promotion-v1` | |
| Occupation count | **507** | |
| Input hash | `3b54f231…b75072` | |
| Snapshots on the run | **507** | `production_occupation_score_snapshots` |
| `current_production_occupation_scores` | **507** | view |
| Factor contribution rows | 3,042 | `production_score_factor_contributions` |
| Task contribution rows | 8,218 | `production_score_task_contributions` |
| Provisional factor rows | 1,014 (507 × 2) | |
| Public publications | **507** | `occupation_publications` |
| Activated at | 2026-08-21 08:00:19.732369 UTC, single transaction | |
| Publication consistency | **507 / 507 `consistent`** | `publication_snapshot_consistency` |
| Public rows outside the phase6 run | **0** | |
| Editorial `occupations` rows | 512 (507 cohort + 5 legacy out-of-cohort) | |
| Occupations passing the publication gate | **507** | |
| `/api/v1/rankings?limit=1000` | **507** | live API |
| Test suite | **111 passed, 0 failed** | `backend/tests` mounted |

### Provenance chain, re-derived

The promotion's `input_version_bundle` resolves as: source namespace
`phase5b-candidate-2026q3-v1` (id 2) → source calculation run
`phase5b-coverage-completion-2026q3-v1` (id 4) → occupation formula
`phase4b-occupation-score-v2-calibration`, structural proxy
`phase4d-direct-structural-proxy-v2`, base proxy `phase4b-occupation-proxy-v1`, frontier
index `frontier-ai-index-v1` on track `commercially_deployable`, mapping scope
`phase5b-mapping-completion-v1`.

Selection was `approval: explicit_code_list`, not a live re-selection. The 507 codes in
`reports/PHASE6_APPROVED_LAUNCH_COHORT.codes` (approved by Akshay 2026-08-21) were diffed
against the promoted set: **identical, zero symmetric difference**. The promoted set also
matches the launch-eligible set of triage run `phase6-triage-postcoverage-2026q3-v1` exactly
(507 / 507, nothing promoted outside it, nothing eligible left behind).

All 507 snapshots are `publishable`, `production_ready`, with coverage and confidence gates
`passed`. Cohort ranges: exposure 24.8–79.4 (mean 60.7), replacement risk 29.9–74.9 (mean
52.2), confidence ≥ 75.8, weighted coverage ≥ 80.1.

### Frozen constraints — still honoured

| Constraint | State |
|---|---|
| `scoring_model_versions.is_active` | **JVS 1.0.3**, unchanged. JVS 2.0.0-phase4b remains registered inactive and is what production snapshots reference. |
| Legacy `occupation_scores` | **11 rows**, all on model version 1. `score_derivations` 11, `score_history` 2. Untouched. |
| Occupation-level augmentation | `augmentation_publishable` false on **every** snapshot in the store. |
| Phase 5 / 5B history | 5 calculation runs, `public_activations` still CHECK-pinned to 0 on all of them. |
| Fabricated `salary_potential` / `future_demand` / `location_demand` | None. Career-finder still reads legacy scores and is still absent from public navigation. |

### The provisional-sensitivity disclosure question is decided

`CLAUDE.md` listed this as the open decision blocking the content re-run. It was resolved
**yes, per page**, as `phase6-provisional-disclosure-v1`, and is baked into content run 2
under `phase6-verdict-template-v2`. All 507 candidates carry it. It is computed per
occupation from that snapshot's own factor rows rather than hard-coded, and resolves to
0.25 / 25% for all 507. It surfaces on the API as `provisionalWeightShare: 25.0`. See
`PHASE6_ACTIVATION_AUDIT.md` §2 for the wording and the reasoning.

## 2. Report status

### Current — do not mark superseded

| Report | Why |
|---|---|
| `PHASE6_ACTIVATION_AUDIT.md` | Records the promotion (§1), content (§2), editorial rows (§3), related occupations (§4), the frontend rebuild (§10) and the activation with live verification (§11). Accurate as of this reconciliation. **Read this first.** |

### Superseded on their status claims only

These were written before promotion and open with a banner that is now false. **Their
methodology, derivations and findings remain valid** — only the "nothing promoted / nothing
activated" framing is stale. They are kept as the record of how the cohort was derived.

| Report | Stale claim |
|---|---|
| `PHASE6_LAUNCH_PLAN.md` | *"Nothing promoted. No occupation activated."* Steps 3, 4, 5, 6, 9 and 10 are all now done. This file is no longer the current state of play. |
| `PHASE6_LAUNCH_READINESS_REPORT.md` | Same banner. Its schema, guard and admin-surface content is still accurate. |
| `PHASE6_POST_COVERAGE_TRIAGE_REPORT.md` | Same banner. Still the correct account of how the 507 cohort was derived. |
| `PHASE6_OPTION_B_IMPLEMENTATION_REPORT.md` | *"Nothing promoted, nothing activated."* Still the correct description of the production score store design. |
| `PHASE6_PRODUCTION_SCORE_STORE_DESIGN.md` | *"design and investigation only. No occupations activated."* |
| `PHASE5B_COVERAGE_COMPLETION_REPORT.md` | Same banner. Still the correct account of the 8 → 507 coverage completion. |
| `PHASE5_BOUNDED_CORPUS_SCORING_REPORT.md` | *"public and production activation remain prohibited."* |

Phase 4A–4D reports and `PHASE5B_SCORE_DELTA_REPORT.md` make no promotion-state claim and
need no annotation.

## 3. Observations from this reconciliation

None of these block anything. They were found while re-deriving the state and are recorded
because they are not covered elsewhere.

1. **A pytest fixture row sits in the public related-occupations table.** Content run 3
   (`pytest-related-5f1d2b61435c`) left one row on identity 8 (`software-developer`). The
   public reader in `backend/app/repositories/occupations.py:86` picks each occupation's
   relations from `max(content_run_id)` *for that identity*, and identity 8 has rows from no
   other run — so if `software-developer` were ever activated, its entire related list would
   be that single fixture row. It is invisible today because identity 8 is `staged`, not
   public, and its target (identity 6) is staged too. This reinforces
   `PHASE6_ACTIVATION_AUDIT.md` §8.2: do not activate the 5 out-of-cohort editorial pages to
   round out the launch. If one is ever activated, re-run content for it first.

2. **`public_occupation_content_runs.promotion_run_id` is NULL on both real content runs.**
   The column exists and `run_public_content.py` never writes it. The chain is not broken —
   it is recoverable per candidate via `verdict_snapshot_id → snapshot.promotion_run_id`, and
   that resolves to `phase6-promotion-2026q3-v1` for all 507 — but the run-level link that
   would make it a one-join question is unrecorded.

3. **`occupation_publications.seo_slug` and `occupations.slug` diverge for 503 of the 507.**
   Publications carry SOC-suffixed slugs (`general-and-operations-managers-11-1021-00`) while
   editorial rows and every public URL use the bare slug
   (`general-and-operations-managers`). Only the 9 original editorial rows agree. This is
   harmless today: no backend code reads `seo_slug`, and the publication gate joins on
   `canonical_occupation_identities.jobs_vs_ai_occupation_id`, never on slug. It is worth
   knowing before anything is built on `seo_slug`.

4. **The fixture promotion-run count is not stable and should never be quoted as a fact.**
   It was 73 rolled-back fixture runs when this reconciliation began and 78 when it ended,
   because running the test suite appends about five more. `CLAUDE.md`'s figure of "19 runs /
   171 snapshots" drifted for exactly this reason. Count non-fixture runs; that number is 1.

5. **One staged publication was touched after activation.** Identity 6
   (`cybersecurity-analyst`) has `updated_at` 2026-08-21 17:25 UTC, nine hours after the
   activation transaction, while the other 404 staged rows still carry their 2026-08-20
   timestamp. It is still `staged` with no approved snapshot, so nothing about the public
   surface is affected, and no run recorded in the database accounts for the change.

6. **Activation has no run-level audit table.** Promotion writes a
   `production_promotion_runs` row with policy, actor, input hash and reconciliation
   counters. Activation leaves only 507 identical `updated_at` timestamps and a NULL
   `reviewed_by`; the policy name (`phase6-public-activation-v1`), the actor and the prior
   statuses survive only in `PHASE6_ACTIVATION_AUDIT.md` §11 and the script's console output.
   Reconstructing the activation from the database alone is not possible.

## 4. Method

Read-only psql against the running `postgres` service with
`PGOPTIONS=-c default_transaction_read_only=on`, so any write would have failed rather than
succeeded quietly. Live checks against the API on :8000. The one thing that did write to the
database was the test suite (`111 passed, 0 failed`), which appends rolled-back
`architecture_test_fixture` promotion runs by design — see observation 4. It changed no
production, publication, editorial or legacy row: the 507/507/507 figures above were
re-checked after it ran and were identical.
