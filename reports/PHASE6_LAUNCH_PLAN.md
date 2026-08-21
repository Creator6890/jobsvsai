# Phase 6 — Launch plan

Date: 2026-08-21
Status: **Nothing promoted. No occupation activated. `is_active` still JVS 1.0.3.**

## 1. Launch policy

**The Phase 6 quality-derived cohort is the launch cohort.** 507 occupations, derived by
`phase6-launch-triage-v1` over `phase5b-coverage-completion-2026q3-v1` and recorded in
`reports/PHASE6_POST_COVERAGE_LAUNCH_COHORT.json`. All 507 remain eligible.

This replaces the earlier posture of treating the cohort as provisional. The quality
question has been answered: every one of the 507 clears the validated coverage, confidence
and structural gates, with no critical or high finding. From here the burden of proof
inverts — an occupation ships unless something concrete stops it.

**An occupation is held back only for a concrete readiness reason:**

1. fails a validated scoring, coverage or confidence gate
2. carries an unresolved critical or high Phase 6 finding
3. required public content is incomplete
4. identity or publication linkage is broken
5. production snapshot is missing
6. reconciliation failed
7. a technical or publication error blocks it

Anything else — a preference, an abundance of caution, an unexamined worry — is not a
hold-back reason. Occupations removed for a reason above must be recorded with that reason,
not silently dropped.

**Target: 507, subject only to actual production and content readiness checks.**

Nothing in this plan changes scoring formulas, coverage thresholds, confidence thresholds,
Frontier AI values, task mappings, or Phase 6 triage rules. Historical runs, provenance,
production isolation, rollback guarantees and deterministic replay are preserved.

## 2. Status

| # | Step | Status |
|---|---|---|
| 1 | Apply and verify migrations 025, 026, 028 | **Done** |
| 2 | Verify production score store and inactive JVS 2.0 registration | **Done** |
| 3 | Resolve the provisional-sensitivity launch decision | **Open — needs a decision** |
| 4 | Generate and stage public content for the 507 | **Partial** — staged; verdicts blocked on step 9 |
| 5 | Populate editorial occupation records | **Blocked** by step 4 completion |
| 6 | Populate and validate related occupations | **Partial** — 6,470 rows staged; validation pending |
| 7 | Build the real promotion transaction | **Done** |
| 8 | Review the promotion dry-run | **Done — clean** |
| 9 | Promote approved snapshots | **Awaiting explicit approval** |
| 10 | Activate publications | **Awaiting explicit approval** |
| 11 | Final public QA and deployment checks | Not started |

## 3. What was completed

### Steps 1–2: migrations and store verification

Migrations 025, 026 and 028 applied to the live database, which had been at 024 (plus 027,
applied during Phase 5B). All three are additive: new tables, views and triggers, one
nullable column on `occupation_publications`, and one defaulted column on
`scoring_model_versions`.

Post-migration state:

| Check | Result |
|---|---|
| Active scoring model | JVS 1.0.3 (`legacy-jvs-1`) — unchanged |
| Engine model | JVS 2.0.0-phase4b (`jobsvsai-engine-v2`), `is_active = false` |
| Production snapshots (non-fixture) | 0 |
| `current_production_occupation_scores` | 0 rows |
| Public occupations | 0 |
| Legacy `occupation_scores` / `task_ai_scores` | 11 / 23 — unchanged |
| Editorial `occupations` | 9 — unchanged |

**Test suite: 108 passed, 0 failed** (with `backend/tests` mounted; the backend image carries
a stale baked-in copy). This is the first fully green run — the 24 errors reported during
Phase 5B were all the missing migrations, and they are gone.

The production store's own guards now execute and pass: v2 registered but not active, legacy
arithmetic cannot be stamped with the engine model, the store rejects the legacy model,
Phase 5 candidate data is immutable, provisional-proxy provenance survives promotion, and
publication-snapshot consistency flags withdrawn approvals.

The store is not empty — it holds 171 snapshots across 19 promotion runs. **Every one is a
pytest architecture fixture** (`source_kind='architecture_test_fixture'`, all `rolled_back`).
Zero non-fixture runs exist, which is why the currency view returns nothing. The fixtures
are left behind deliberately: the store is append-only and rollback is a status change, not
a delete.

### Steps 7–8: the promotion transaction

`scoring/run_production_promotion.py`. One promotion run, one transaction, all-or-nothing.

Refusals built in, each stated rather than assumed:

- refuses if the model it would stamp is the **active** model — promotion must not change
  what the legacy worker writes
- refuses without an explicit approval: either `--approved-codes-file`, or
  `--approve-full-cohort` against a named triage run. There is no "promote everything" path,
  and an approved code that is not launch-eligible is an error, not a silent skip
- refuses if any approved occupation fails either reconciliation
- refuses if any approved occupation does not clear the validated gates — promotion does not
  override gates
- refuses if the candidate run cannot state its full dependency manifest
- never writes occupation-level augmentation; the write is verified to have promoted none
- compares an isolation snapshot before and after inside the transaction and aborts on any
  drift

Verification is done against what was **written**, not what was intended: after inserting,
it re-queries the database and aborts unless every snapshot's persisted factor contributions
sum to its replacement risk and every snapshot's persisted task contributions sum to its AI
exposure, within 0.01.

**Dry-run result (writes nothing):**

| | |
|---|---:|
| Approved occupations | 507 |
| Snapshots to write | 507 |
| Factor rows | 3,042 (507 × 6 exactly) |
| Task rows | 8,218 |
| Publishable | 507 |
| Reconciliation failures | **0** |
| Snapshots without an editorial `occupations` row | 503 |
| Model | JVS 2.0.0-phase4b, inactive |

**The write path has also been executed and rolled back.** `--verify-then-rollback` runs the
complete transaction — all 507 snapshots, 3,042 factor rows, 8,218 task rows, both
post-write reconciliation queries, the isolation comparison — then discards it. It passed,
and the database was confirmed unchanged afterwards. The first real promotion will therefore
not be the first time this code has run.

### Steps 4 and 6: staged content

`public_occupation_content_runs` id 1: 507 candidates and 6,470 related-occupation rows,
generated deterministically from O\*NET source facts against triage run 2.

**Zero slug collisions** across all 507 — the pipeline raises on any collision, and it did
not. That was the check the earlier plan wanted surfaced early.

## 4. The sequencing correction

The priority order asks for content (4) and editorial records (5) before promotion (9). They
cannot fully complete in that order.

Every one of the 507 staged content candidates is `incomplete` on exactly one field:
`jobsvsai_verdict`. The verdict is generated from a promoted score snapshot
(`verdict_snapshot_id`), and no snapshot exists. Everything else — canonical title, slug,
job family, source summary, attribution, search aliases, related occupations — is complete
and staged now.

Likewise, editorial `occupations` rows can technically be created before verdicts exist
(`verdict` is `NOT NULL DEFAULT ''`), but creating 503 rows as empty shells and filling them
later means editing every public record twice.

**Corrected order:**

```
  3. provisional-sensitivity decision   ─┐
                                         ├─> 9. promote snapshots (needs approval)
  8. promotion dry-run reviewed  ────────┘
                                              │
                        4b. re-run content ───┤  verdicts now derivable
                                              │
                        5. editorial rows ────┤  created once, complete
                                              │
                        6. validate related ──┤
                                              │
                       10. activate publications (needs approval)
                                              │
                       11. public QA and deployment checks
```

Step 4 has been taken as far as it can go without snapshots. It will need one further
content run after promotion, under a new run version, to fill the verdicts.

## 5. The one open decision — step 3

Provisional sensitivity is the only remaining item that is a judgement rather than a task,
and it cannot be resolved by changing anything: the 3-point rule is a Phase 6 triage rule,
and those are frozen for this work.

The facts:

- 106 occupations fail the rule; **59 are blocked by nothing else**, 28 of them in SOC 47.
  Under the frozen rules they stay out of the launch cohort. That is the status quo and
  requires no action.
- The live question is about the **507 that are in**. Every one of them carries adoption
  pressure and labour-market resilience as 25% of its replacement-risk weight. Passing the
  3-point sensitivity test means the provisional models did not happen to move that
  particular score much — it is not evidence that the models are right.

So the decision is not "who ships" but **"what does the page say"**. Three options, none of
which touch a formula or a threshold:

| Option | What it means | Cost |
|---|---|---|
| **A. Disclose per page (recommended)** | Every published occupation states that 25% of its replacement-risk weight comes from two provisional models, and names them. The data is already columnar — `production_score_factor_contributions.is_provisional_proxy` and `proxy_model_version` — and the promotion carries it. | A content/UI change in the verdict template before step 4b |
| **B. Ship silent** | Publish the 507 with no provisional disclosure. | The first informed reader who inspects the methodology finds 25% of the headline unvalidated and undisclosed |
| **C. Hold the launch** | Validate both models before publishing anything. | Blocks all 507 on work of unknown duration |

Recommendation: **A**. It is honest, it is cheap, the provenance is already stored for it,
and it does not delay the cohort. B trades a small content cost now for a credibility cost
later. C fails the stated policy of shipping the maximum currently defensible cohort.

This needs your decision before step 4b, because the verdict template is generated during
the content run.

## 6. Ready for approval

Steps 9 and 10 are the approval gate and have not been taken.

To promote, once approved:

```bash
docker compose run --rm -e PYTHONPATH=/app/scoring worker \
    python -m scoring.run_production_promotion \
    --run-key phase6-promotion-2026q3-v1 \
    --triage-run-key phase6-triage-postcoverage-2026q3-v1 \
    --approve-full-cohort
```

Rollback, if ever needed, is a status change on `production_promotion_runs` — no score row
is rewritten, and `current_production_occupation_scores` falls back to the previous
completed run.

Publication activation remains separate and is not part of promotion.
