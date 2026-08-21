# Phase 6 — Production score store design (Option B) and `occupation_scores` investigation

Date: 2026-08-20
Status: **design and investigation only.** No occupations activated, no Phase 5 rows copied,
`scoring_model_versions.is_active` unchanged, no formula touched, no migration applied.

---

## Part 1 — The 9-vs-11 `occupation_scores` discrepancy

### 1.1 What the repository determines without a database

There are exactly three writers of `occupation_scores` in the entire repository:

| Writer | Operation | Rows |
|---|---|---|
| `migrations/002_seed_demo_data.sql:27` | INSERT | 9, one per demo occupation |
| `migrations/004_phase1_audit_gates.sql:137,144` | UPDATE only | 0 new rows (backfills `task_exposure`, `ai_capability_proximity`) |
| `worker/jobs.py:84` (`recalculate_occupation`) | INSERT | 1 per invocation |

Nothing else — no admin endpoint (all eleven are `GET`), no phase runner, no ingestion path —
inserts into this table. **Therefore the two extra rows can only have come from
`worker/jobs.py`.**

The worker leaves an unambiguous fingerprint. Line 91:

```sql
CAST(:input_versions AS jsonb) || jsonb_build_object('reason', CAST(:reason AS TEXT))
```

Every worker-written row carries an `input_versions.reason` key. Migration 002 seeds
`{"occupation":"demo-2026-08","capability":"1.6.2"}` with no `reason` key. So
`input_versions ? 'reason'` separates the two origins exactly, with no heuristics.

The worker also writes `score_derivations` (1:1 with every score) and `score_history`
(**only** for worker-written scores — migration 004 backfills `score_derivations` for the seed
but never `score_history`). So `count(score_history)` is precisely the number of worker
recalculations.

### 1.2 Empirical reproduction

I applied all 24 migrations to a clean PostgreSQL instance and invoked
`worker.jobs._recalculate_occupation` twice. The resulting state matches the reported figures
exactly:

| Measure | Fresh migrations | After 2 worker runs | Reported in Phase 5 |
|---|---:|---:|---:|
| `occupation_scores` | 9 | **11** | **11** |
| `score_history` | 0 | **2** | — |
| `score_derivations` | 9 | 11 | — |
| `task_ai_scores` | 23 | 23 | **23** |

The production task-score count of 23 also matches on fresh migrations, confirming that the
legacy task scores are entirely seed-derived and were never touched by Phases 4A–5.

This is a hypothesis that fits every observed number, not a confirmed reading of your database.
`reports/investigate_occupation_scores.sql` confirms it against the real data.

### 1.3 Answers to the seven questions

Items 1–5 are answered by the script (validated against the reproduction above). Item 6 is
answered definitively from source. Item 7 is answered structurally.

**1. Which occupations own the 11 rows.** Expected: all 9 demo occupations own one row each;
two of them own a second. In the reproduction those two were the occupations I recalculated.
The script's section 4 names yours.

**2. Model version for every row.** All 11 will read `JVS 1.0.3`. There is only one row in
`scoring_model_versions`, it is `is_active = true`, and the worker selects
`WHERE is_active ORDER BY created_at DESC LIMIT 1`. No other model has ever existed in
production.

**3. Calculated timestamps.** Seeded rows share a single `calculated_at` — migration 002 runs in
one transaction and `now()` is transaction start time, so all 9 are identical to the microsecond.
Worker rows carry their own later timestamps.

**4. Multiple historical rows.** Expected: exactly two occupations with two rows each.

**5. What created them.** `worker/jobs.py::recalculate_occupation`. The script reports the
`reason` string each carries (`dependency_changed`, or whatever was passed) and cross-checks
`scoring_jobs` for the enqueue trail. Note that `scoring_jobs` will be empty if the worker was
invoked directly rather than through `enqueue_affected_occupations` — that was the case in my
reproduction, and its emptiness is not evidence against worker authorship.

**6. Do public readers use latest-row semantics? Yes — but inconsistently, and this is a latent
bug.**

| Reader | Ordering |
|---|---|
| `repositories/occupations.py:27` — list, detail, search | `ORDER BY calculated_at DESC LIMIT 1` |
| `repositories/occupations.py:71` — related careers | `ORDER BY calculated_at DESC LIMIT 1` |
| `api/rankings.py:17` | `ORDER BY calculated_at DESC LIMIT 1` |
| `api/careers.py:78,109` | `ORDER BY calculated_at DESC, id DESC LIMIT 1` |
| `api/admin.py:1264` — derivation | `ORDER BY calculated_at DESC, id DESC LIMIT 1` |
| `worker/jobs.py:31` — baseline read | `ORDER BY calculated_at DESC LIMIT 1` |

Three public readers have **no deterministic tiebreak**. `UNIQUE(occupation_id,
model_version_id, calculated_at)` prevents a tie only *within* one model version — it does not
prevent two rows for the same occupation under *different* model versions sharing a timestamp.
That is exactly what a promotion transaction would produce, since every row inserted in one
transaction gets the same `now()`.

Consequence if we had promoted into this table: the occupation page and the rankings could
resolve to a different row than the Career Finder and the admin derivation inspector, and
`test_score_consistency_across_public_and_admin_surfaces` would begin failing
non-deterministically. **This is an independent argument for Option B**, and the design below
removes the ambiguity by construction.

Section 6 of the script reports whether any tie exists in your data today. It should return zero
rows; if it does not, that needs attention before anything else.

**7. Can legacy rows be archived later? Yes, with two caveats.**

Structurally, any row whose recency rank is > 1 is never served by any reader and is safe to
archive — expected to be the two superseded seed rows. The caveats:

- `score_derivations.score_id` is a `UNIQUE NOT NULL` FK with `ON DELETE CASCADE`, and
  `score_history.source_score_id` is a nullable FK. Deleting a superseded score silently
  destroys its derivation. Archive means *copy out, then delete*, or better: leave in place.
- Once the publication gate is live and Option B is serving, **the entire legacy chain
  (`occupation_scores`, `score_derivations`, `score_history`, `task_ai_scores`,
  `occupation_tasks`, the 9 demo `occupations` rows) becomes dead weight rather than risk.**
  Per your instruction it stays for now. My recommendation is to leave all 11 rows untouched
  and retire the whole legacy chain in one deliberate step after Option B is serving, rather
  than trimming two rows now for no benefit.

---

## Part 2 — Option B production score store

### 2.1 Principles the schema encodes

1. **Snapshots are immutable.** There is no mutable "current score" column anywhere. Currency
   is *derived* from promotion-run status, so rollback never rewrites a score.
2. **Score existence ≠ publishability ≠ published.** Three separate states in three places.
3. **Nothing is recalculated.** Promotion copies persisted Phase 5 values and carries their
   `input_hash` verbatim, so a promoted score reconciles to its candidate by hash.
4. **Provenance is queryable, not buried.** `provisionalProxy` and `proxyModelVersion` become
   columns, so "which published occupations carry >20% provisional weight" is one SQL query.
5. **O\*NET task identity, not legacy task identity.** Task derivations reference
   `onet_task_id`; they never touch the legacy `tasks` table.

### 2.2 Tables

#### `production_promotion_runs` — the unit of promotion and rollback

```
id                        BIGSERIAL PK
run_key                   TEXT NOT NULL UNIQUE          -- 'phase6-promotion-2026q3-v1'
source_namespace_id       BIGINT NOT NULL REFERENCES phase5_candidate_namespaces(id)
source_calculation_run_id BIGINT NOT NULL REFERENCES phase5_calculation_runs(id)
scoring_model_version_id  BIGINT NOT NULL REFERENCES scoring_model_versions(id)
promotion_policy_version  TEXT NOT NULL
status                    TEXT NOT NULL CHECK (status IN
                            ('in_progress','completed','rolled_back','failed'))
occupation_count          INTEGER NOT NULL DEFAULT 0
input_version_bundle      JSONB NOT NULL   -- frontier index+track, proxy models, formula,
                                           -- taxonomy, rubric, evidence policy versions
selection_policy          JSONB NOT NULL   -- which candidates, and the rule that chose them
reconciliation            JSONB NOT NULL
input_hash                CHAR(64) NOT NULL
source_id                 BIGINT NOT NULL REFERENCES data_sources(id)
provenance                JSONB NOT NULL DEFAULT '{}'
created_by                TEXT NOT NULL
created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
rolled_back_at            TIMESTAMPTZ
rolled_back_by            TEXT
rolled_back_reason        TEXT
CHECK (status <> 'rolled_back' OR rolled_back_at IS NOT NULL)
```

This is the **only mutable table in the design**, and only its status/rollback columns move.

#### `production_occupation_score_snapshots` — immutable, append-only

```
id                            BIGSERIAL PK
promotion_run_id              BIGINT NOT NULL REFERENCES production_promotion_runs(id)
identity_id                   BIGINT NOT NULL REFERENCES canonical_occupation_identities(id)
occupation_id                 BIGINT REFERENCES occupations(id)   -- nullable, see 2.6
source_candidate_score_id     BIGINT NOT NULL REFERENCES phase5_occupation_scores(id)
scoring_model_version_id      BIGINT NOT NULL REFERENCES scoring_model_versions(id)

ai_exposure                   NUMERIC(7,4) NOT NULL CHECK (BETWEEN 0 AND 100)
replacement_risk              NUMERIC(7,4) NOT NULL CHECK (BETWEEN 0 AND 100)
augmentation_potential        NUMERIC(7,4)          CHECK (BETWEEN 0 AND 100)  -- see 2.5
confidence                    NUMERIC(7,4) NOT NULL CHECK (BETWEEN 0 AND 100)
weighted_task_coverage        NUMERIC(7,4) NOT NULL CHECK (BETWEEN 0 AND 100)

source_task_count             INTEGER NOT NULL
eligible_task_count           INTEGER NOT NULL
excluded_task_count           INTEGER NOT NULL
weighting_eligible_task_count INTEGER NOT NULL

coverage_gate_status          TEXT NOT NULL CHECK (IN ('passed','below_threshold','no_usable_evidence'))
confidence_gate_status        TEXT NOT NULL CHECK (IN ('passed','below_threshold'))
scoring_eligibility           TEXT NOT NULL CHECK (IN ('production_ready','blocked'))
publishable                   BOOLEAN NOT NULL DEFAULT false   -- "may be published", not "is"
CHECK (publishable = false OR (scoring_eligibility='production_ready'
        AND coverage_gate_status='passed' AND confidence_gate_status='passed'))

frontier_index_version        TEXT NOT NULL
frontier_track                TEXT NOT NULL
structural_proxy_model_version TEXT NOT NULL     -- phase4d-direct-structural-proxy-v2
base_proxy_model_version      TEXT NOT NULL      -- phase4b-occupation-proxy-v1
occupation_formula_version    TEXT NOT NULL
task_formula_versions         JSONB NOT NULL     -- capability_fit / automation / augmentation
capability_taxonomy_version   TEXT NOT NULL
mapping_rubric_version        TEXT NOT NULL
evidence_policy_version       TEXT NOT NULL

calculated_at                 TIMESTAMPTZ NOT NULL   -- Phase 5 calculation time, carried over
promoted_at                   TIMESTAMPTZ NOT NULL DEFAULT now()

exact_inputs                  JSONB NOT NULL
provisional_sensitivity       JSONB NOT NULL
warnings                      JSONB NOT NULL DEFAULT '[]'
blocking_reasons              JSONB NOT NULL DEFAULT '[]'
reconciliation                JSONB NOT NULL
input_hash                    CHAR(64) NOT NULL      -- equals the candidate's hash
source_id, provenance, created_by, created_at
UNIQUE (promotion_run_id, identity_id)
```

`calculated_at` and `promoted_at` are deliberately separate: the score was computed in Phase 5,
not at promotion time, and conflating them would falsify the "as of" date on public pages.

#### `production_score_factor_contributions` — normalized replacement-risk derivation

```
id                     BIGSERIAL PK
snapshot_id            BIGINT NOT NULL REFERENCES production_occupation_score_snapshots(id)
factor_key             TEXT NOT NULL       -- taskAutomationExposure, aiCapabilityProximity,
                                           -- humanDependencyResistance, physicalDependencyResistance,
                                           -- adoptionPressure, labourMarketResilienceResistance
factor_label           TEXT NOT NULL
value                  NUMERIC(9,4) NOT NULL   -- as persisted by Phase 5 (already transformed)
source_proxy_value     NUMERIC(9,4)            -- untransformed proxy where derivable
transformation         TEXT NOT NULL           -- 'identity' | 'inverse: 100 - raw'
weight                 NUMERIC(9,6) NOT NULL
weighted_contribution  NUMERIC(9,4) NOT NULL
is_provisional_proxy   BOOLEAN NOT NULL DEFAULT false
proxy_model_version    TEXT
placeholder            BOOLEAN NOT NULL DEFAULT false
display_order          SMALLINT NOT NULL
UNIQUE (snapshot_id, factor_key)
```

Six rows per snapshot. `is_provisional_proxy` and `proxy_model_version` are carried straight
from the Phase 5 payload — this is the requirement that makes the provisional-model exposure
auditable in SQL rather than by parsing JSON.

#### `production_score_task_contributions` — normalized task derivation

```
id                        BIGSERIAL PK
snapshot_id               BIGINT NOT NULL REFERENCES production_occupation_score_snapshots(id)
onet_task_id              BIGINT NOT NULL          -- O*NET identity, not legacy tasks.id
onet_soc_code             TEXT NOT NULL
task_statement            TEXT NOT NULL
task_statement_hash       TEXT NOT NULL
source_mapping_set_id     BIGINT
ai_capability_fit         NUMERIC(7,4) NOT NULL
automation_feasibility    NUMERIC(7,4) NOT NULL
augmentation_potential    NUMERIC(7,4) NOT NULL
task_ai_exposure          NUMERIC(7,4) NOT NULL
task_confidence           NUMERIC(7,4)
source_importance         NUMERIC(7,4)
source_frequency          NUMERIC(7,4)
source_weight             NUMERIC(12,4)
normalized_covered_weight NUMERIC(9,6) NOT NULL
exposure_contribution     NUMERIC(9,4) NOT NULL
weighting_eligible        BOOLEAN NOT NULL
UNIQUE (snapshot_id, onet_task_id)
```

At the recommended cohort size this is roughly 400 × 27 ≈ 11k rows per promotion run — trivial
for PostgreSQL, and it makes "show me the tasks driving this score" a normal indexed query.

#### One change to an existing table

```sql
ALTER TABLE occupation_publications
  ADD COLUMN approved_score_snapshot_id BIGINT
    REFERENCES production_occupation_score_snapshots(id);
```

Nullable, non-breaking, and it answers a question the current schema cannot: *which score did
editorial actually approve for this page?* Without it, a rollback could leave a page published
against a withdrawn snapshot with nothing recording the mismatch. Publication state itself stays
exactly where it is — this adds a pointer, not a control.

### 2.3 Currency without mutable state

```sql
CREATE VIEW current_production_occupation_scores AS
SELECT DISTINCT ON (snapshot.identity_id) snapshot.*, run.run_key
FROM production_occupation_score_snapshots snapshot
JOIN production_promotion_runs run ON run.id = snapshot.promotion_run_id
WHERE run.status = 'completed'
ORDER BY snapshot.identity_id, run.created_at DESC, snapshot.id DESC;
```

Every reader goes through this view. Nobody hand-writes a "latest" clause again, and the
`snapshot.id DESC` tiebreak removes the ambiguity documented in 1.3/6. Rolling a run back
changes `run.status`, and the view falls back to the previous completed run — or to nothing —
with no score row rewritten.

Immutability enforced by reusing the existing `prevent_ai_enrichment_history_mutation()` trigger
(BEFORE UPDATE OR DELETE) on all three snapshot/derivation tables. Because nothing is ever
deleted, the FK cascades are decorative; I'd omit `ON DELETE CASCADE` rather than imply a
deletion path that the triggers forbid.

### 2.4 The state chain

```
phase5_occupation_scores            candidate_status = 'review_ready'
  │                                 public_activation_eligible CHECK-pinned false
  │  promotion run (copy, no recalculation)
  ▼
production_occupation_score_snapshots   scoring_eligibility = 'production_ready'
  │                                     publishable = true|false
  │  editorial approval
  ▼
occupation_publications             editorial_review_status = 'approved'
  │                                 approved_score_snapshot_id → snapshot
  │  activation
  ▼
public                              activation_status = 'public'   ← the gate shipped earlier
```

Four independent states. A production-grade score never makes a page public on its own, which
is the property you asked for.

### 2.5 Augmentation summary — honest position

There is **no persisted occupation-level augmentation value** anywhere in Phase 5. What exists
is per-task `augmentation_potential` in `phase5_task_assessments`, plus a ranked
`augmentation_heavy_tasks` list per occupation.

An occupation-level figure is derivable by pure aggregation —
`Σ(normalized_covered_weight × augmentation_potential)` — with no recomputation and no new
model. But it has never been through Phase 4C/4D validation as a published output, and it does
not appear in any validation report.

Recommendation: include the column, populate it by aggregation at promotion time, and leave it
**internal/unpublished** until it has been validated the way Exposure and Replacement Risk were.
Publishing a third headline number that never went through the validation frame would break the
project's own rule.

### 2.6 `occupation_id` is nullable, deliberately

Snapshots key on `identity_id` (the canonical O\*NET-derived identity), because that is what
Phase 5 scored. The editorial `occupations` row — slug, category, summary, verdict — may not
exist yet for most of the 400. Making `occupation_id` nullable lets scores be promoted and
reviewed **before** the editorial content workstream completes, instead of blocking on it.
Publication requires both.

---

## Part 3 — Promotion transaction

One transaction. Aborts entirely on any check failure.

1. `INSERT production_promotion_runs (status='in_progress')`, capturing the version bundle read
   from `phase5_calculation_runs` — never hardcoded.
2. Select candidates: `phase5_occupation_scores` where `calculation_run_id` = the source run,
   `candidate_status='review_ready'`, and identity ∈ the approved cohort list.
3. Per candidate, assert before inserting:
   - `input_hash` matches the stored candidate hash;
   - `coverage_gate_status='passed'` and `confidence_gate_status='passed'`;
   - `weighted_task_coverage >= 70` and `confidence >= 70` (re-asserted, not assumed);
   - the candidate's `calculation_run_id` matches the run's declared source.
4. Insert the snapshot, its six factor rows and its task rows, copying values verbatim.
5. Reconcile in-transaction: `Σ weighted_contribution ≈ replacement_risk` and
   `Σ exposure_contribution ≈ ai_exposure`, both within 0.01. Any mismatch aborts.
6. Assert the promoted count equals the approved cohort size exactly.
7. `UPDATE production_promotion_runs SET status='completed', occupation_count=n`.

Touched: the three new tables only. Not touched: `occupation_scores`, `score_derivations`,
`score_history`, `occupations`, `occupation_publications`, every `phase5_*` table,
`scoring_model_versions.is_active`. External AI calls: zero. Recalculation: zero.

## Part 4 — Rollback

Two independent levers, matching your requirement.

**By promotion run** — `UPDATE production_promotion_runs SET status='rolled_back',
rolled_back_at=now(), rolled_back_reason=…`. The view immediately falls back to the previous
completed run or to nothing. No snapshot is modified or deleted; Phase 5 is not consulted.
Re-promotion later is a fresh run from the same persisted candidates.

One guard is required: a rollback must also demote any `occupation_publications` rows whose
`approved_score_snapshot_id` belongs to the rolled-back run — otherwise a live page keeps
serving a withdrawn snapshot. That should be part of the rollback procedure, not left to
discipline.

**By publication status** — `UPDATE occupation_publications SET activation_status='inactive'`.
The page disappears; the score snapshot is untouched. This is per-occupation and needs no
score-side action at all, which is the payoff from shipping the read-path gate first.

Neither lever recalculates anything.

## Part 5 — Changes required in existing public readers

| File | Change |
|---|---|
| `backend/app/repositories/occupations.py` | `BASE_SELECT` joins `current_production_occupation_scores` via `canonical_occupation_identities` instead of `LATERAL occupation_scores`; publication gate unchanged |
| `backend/app/repositories/occupations.py::_hydrate` | Tasks come from `production_score_task_contributions` (O\*NET identity), not `occupation_tasks` + `task_ai_scores` |
| `backend/app/api/rankings.py` | Same view swap; the `LATERAL … ORDER BY calculated_at` disappears |
| `backend/app/api/careers.py` | Two queries — **but see the blocker below** |
| `backend/app/api/admin.py` | New derivation endpoint reading the normalized tables; keep the legacy one while legacy data exists |
| `backend/app/schemas/occupation.py` | `confidence: str` → numeric (+ optional band); add `weighted_task_coverage`; rename `market_resilience` → labour-market resilience; extend `ScoreFactor` with `is_provisional_proxy` and `proxy_model_version`; `TaskContribution.task_id` → `onet_task_id` |
| `frontend/src/types/occupation.ts`, `OccupationDetail.tsx`, `ScoreCard.tsx` | Follow the schema; surface coverage and the provisional-proxy marker |
| `frontend/src/app/methodology/page.tsx` | Must describe the v2 factor set and the provisional inputs before launch |

### Blocker found while mapping the readers

`api/careers.py` ranks recommendations on `salary_potential` and `future_demand`, and
`_salary_fit()` compares the two occupations' `salary_potential` directly. **Neither value
exists anywhere in the Phase 5 engine.** They exist only as hand-authored demo columns on
`occupation_scores`.

So the Career Finder cannot be migrated to Option B as it stands. Three options, none of which
should be chosen silently:

1. Drop salary and demand from the ranking and reweight the remaining six components
   (`skillFit`, `aiResilience`, `locationDemand`, `retrainingFit`, `educationReadiness`,
   `experienceReadiness`) — changes recommendation behaviour and needs its own validation.
2. Source them properly (BLS wage/projection data is the obvious candidate) — a new ingestion
   workstream with its own provenance requirements.
3. Keep `/career-finder` out of the initial launch and ship occupation pages, rankings and
   comparisons first.

This is not in the Phase 6 brief and I'd flag it as a scoping decision, not an implementation
detail. `market_signals` (`location_demand`) has the same problem: it is seeded demo data.

---

## What I have not done

No migration written or applied. No Phase 5 row copied. No occupation activated.
`scoring_model_versions.is_active` untouched. No formula, mapping, Frontier value or proxy
changed. The legacy worker path is still unguarded — that guard belongs with the 7.2 activation
work, which remains pending your launch-quality review.
