# Phase 6 — Post-coverage launch triage report

Date: 2026-08-21
Status: **Nothing promoted. No occupation activated. `is_active` still JVS 1.0.3.**

Policy `phase6-launch-triage-v1`, unchanged. No threshold was modified, no cohort was
truncated to a target, and the cohort is derived rather than chosen.

| | Baseline | Post-coverage |
|---|---|---|
| Triage run key | `phase6-triage-2026q3-v1` (id 1) | `phase6-triage-postcoverage-2026q3-v1` (id 2) |
| Source calculation run | `phase5-bounded-corpus-v2-2026q3` (id 2) | `phase5b-coverage-completion-2026q3-v1` (id 4) |
| Policy version | `phase6-launch-triage-v1` | `phase6-launch-triage-v1` |

The baseline was persisted first, before any Phase 5B work, and is immutable — the
append-only trigger rejects modification. It records the 8-occupation cohort as an audit
artefact, not as a launch recommendation.

## 1. Result

| | Baseline | Post-coverage | Change |
|---|---:|---:|---:|
| Candidates assessed | 878 | 878 | — |
| **Launch cohort** | **8** | **507** | **+499** |
| Excluded | 870 | 371 | −499 |
| Clean candidates (no findings above `low`) | 6 | **503** | +497 |
| Cohort carrying a medium finding | 2 | 4 | +2 |

| Severity totals | Baseline | Post-coverage |
|---|---:|---:|
| critical | 135 | 135 |
| high | 1,126 | 545 |
| medium | 48 | 33 |
| low | 878 | 878 |

| Exclusion reason | Baseline | Post-coverage |
|---|---:|---:|
| `weighted_coverage_below_launch_minimum` | 868 | **311** |
| `confidence_below_launch_minimum` | 150 | 128 |
| `not_review_ready` | 134 | 134 |
| `provisional_input_sensitivity` | 106 | 106 |
| `exposure_replacement_gap` | 2 | **0** |
| `high_replacement_despite_severe_constraints` | 1 | 1 |

**Occupations newly eligible: 499. Baseline occupations no longer eligible: 0.** All 8
baseline occupations retained eligibility. The cohort grew strictly by addition.

The four cohort members carrying a medium finding, all `single_task_dependence`:
45-4022.00, 47-2072.00, 53-1041.00, 53-7051.00. Medium findings do not block; they are an
editorial check on task mix.

## 2. Cohort profile

Coverage 80.1 – 100.0 (min at the gate, as expected). Confidence 75.8 – 88.7.
AI Exposure 24.8 – 79.4. Replacement Risk 29.9 – 74.9. 22 SOC major groups represented.

| SOC | Major group | Cohort |
|---|---|---:|
| 51 | Production | 72 |
| 29 | Healthcare Practitioners | 55 |
| 19 | Life, Physical and Social Science | 43 |
| 17 | Architecture and Engineering | 40 |
| 11 | Management | 38 |
| 25 | Education | 36 |
| 53 | Transportation | 30 |
| 13 | Business and Financial | 28 |
| 49 | Installation and Repair | 26 |
| 43 | Office and Administrative | 24 |
| 27 | Arts and Media | 22 |
| 47 | Construction | 19 |
| 15 | Computer and Mathematical | 14 |
| 21 | Community and Social Service | 12 |
| 31 | Healthcare Support | 10 |
| 33 | Protective Service | 10 |
| 41 | Sales | 7 |
| 39 | Personal Care | 6 |
| 45 | Farming, Fishing and Forestry | 6 |
| 23 | Legal | 3 |
| 35 | Food Preparation | 3 |
| 37 | Building and Grounds | 3 |

Full list: `reports/PHASE6_POST_COVERAGE_LAUNCH_COHORT.json`.

## 3. Remaining coverage failures — classified

311 candidates still fail `weighted_coverage_below_launch_minimum`. Every one has **zero
remaining defensibly mappable tasks**: the completion pass exhausted them.

| Classification | Occupations |
|---|---:|
| Genuinely ambiguous or insufficient task descriptions | **311** |
| Mappable weight still unmapped | 0 |
| Missing task importance/frequency as sole cause | 0 |
| No valid capability mapping available | 0 |
| Other | 0 |

Residual unmapped weight is 20% – 77% of each occupation's weighted total (median 28%,
median 6 ambiguous tasks per occupation). 17 of the 311 additionally carry at least one task
with no importance or frequency.

By coverage band: 134 below 70 (also below the scoring-eligibility gate), 76 at 70–74.99,
101 at 75–79.99.

**These are not engineering failures.** O\*NET's statements for this work are too thin to map
without inventing scope, and the rubric correctly refuses. They should remain unpublished
until the source data improves. Recovering them by loosening the ambiguity rule would be
buying page count with fabricated evidence.

## 4. Provisional sensitivity after coverage completion

Rerun because new task evidence changes downstream scores. It barely moved.

| | Phase 5 | Phase 5B |
|---|---:|---:|
| mean | 1.780 | 1.779 |
| p50 | 1.568 | 1.569 |
| p75 | 2.314 | 2.312 |
| p90 | 3.199 | 3.192 |
| p95 | 4.016 | 4.066 |
| max | 7.429 | 7.253 |

| | Count |
|---|---:|
| Failing the 3.0 rule | **106** |
| Between 3.0 and 4.0 | 60 |
| Above 5.0 | 21 |
| **Blocked by this rule alone** | **59** |

The 3-point rule was not changed. This section is observation only.

59 occupations now clear coverage, confidence and every structural check and are excluded
*solely* because the two provisional models (adoption pressure, labour-market resilience)
move their replacement score by more than 3 points. Before coverage completion this rule was
one of five things wrong with most candidates; now it is the last thing wrong with 59 of
them. **It has become the binding constraint on the next tranche of the cohort.**

Concentration by SOC major group, occupations failing the rule:

| SOC | Failing | SOC | Failing |
|---|---:|---|---:|
| 47 Construction | 28 | 27 Arts and Media | 4 |
| 49 Installation and Repair | 9 | 33 Protective Service | 4 |
| 51 Production | 9 | 41 Sales | 4 |
| 17 Architecture and Engineering | 8 | 35 Food Preparation | 3 |
| 39 Personal Care | 8 | 37 Building and Grounds | 3 |
| 15 Computer and Mathematical | 7 | 43 Office and Administrative | 2 |
| 53 Transportation | 5 | 11, 19, 21, 23, 25, 29, 31, 45 | 1 each |
| 13 Business and Financial | 4 | | |

Construction is a quarter of all failures. That is a property of the provisional models, not
of construction work, and it is worth investigating before those models are relied on
further.

## 5. Structural anomaly recheck

| Anomaly | Phase 5 | Phase 5B | Change |
|---|---:|---:|---|
| `high_replacement_despite_severe_constraints` | 1 | 1 | unchanged |
| `low_replacement_despite_digital_routine_composition` | 0 | 0 | none in either run |
| `exposure_replacement_gap` | 2 | **0** | both resolved |
| `single_factor_dependence` | 0 | 0 | none in either run |
| `single_task_dependence` | 15 | 14 | 1 resolved |
| `related_soc_score_discontinuity` | 176 | 170 | 6 resolved |

**No anomaly of any type was introduced.** Six related-SOC discontinuities, one single-task
dependence and both exposure/replacement gaps resolved — consistent with occupations being
measured on fuller task sets.

One methodological note: the Phase 5 anomaly checker reports 170 related-SOC discontinuities
while the Phase 6 triage reports zero. They are not in conflict — the triage groups by the
7-character detailed-occupation prefix (`13-2011`), so it only compares `.XX` variants of the
same occupation, while the Phase 5 checker groups more broadly. Neither is wrong, but the
triage's related-SOC check is much weaker than its name suggests and should not be read as
clearing the corpus on that dimension.

### The one critical anomaly, in full

**13-2071.00 Credit Counselors** — `high_replacement_despite_severe_constraints`, and the
sole reason it is excluded.

Coverage 87.75, confidence 82.81, 18 eligible tasks, AI Exposure 71.43, Replacement Risk
70.16 — just over the 70.0 high-replacement line — against a human-dependency signal of
72.85, just over the 70.0 severe-constraint line.

| Factor | Value | Weight | Contribution | Provisional |
|---|---:|---:|---:|---|
| taskAutomationExposure | 78.28 | 0.35 | 27.397 | no |
| physicalDependencyResistance | 75.90 | 0.15 | 11.386 | no |
| adoptionPressure | 69.09 | 0.15 | 10.363 | **yes** |
| humanDependencyResistance | 54.98 | 0.15 | 8.247 | no |
| aiCapabilityProximity | 79.03 | 0.10 | 7.903 | no |
| labourMarketResilienceResistance | 48.65 | 0.10 | 4.865 | **yes** |
| **Replacement Risk** | | | **70.160** | |

Contributions reconcile exactly. The flag is a genuine tension, not an arithmetic fault: the
occupation's task mix is highly automatable while its human-dependency signal is high — a
counselling occupation whose *procedural* work dominates the weighted mean. It sits 0.16
points over the threshold, and 15.2 of its 70.16 points come from the two provisional
models. It should stay excluded, and it is a good test case for whether the human-dependency
factor is weighted correctly for advisory occupations.

**No score was repaired manually.**

## 6. Safety confirmation

| Protected state | Status |
|---|---|
| Phase 5 run `phase5-bounded-corpus-v2-2026q3` | unchanged, still readable |
| Phase 4 data | unchanged |
| Legacy `occupation_scores` (11 rows), `task_ai_scores` (23 rows) | unchanged |
| Public occupations | 0 |
| Production candidate snapshots / publications | none created |
| Active scoring model | JVS 1.0.3 |
| Archetype scoring | disabled |
| Methodology, formulas, thresholds | unchanged |

New state created, all additive and versioned: the persisted Phase 6 baseline triage, the
`phase5b-mapping-completion-v1` scope and its namespace, the Phase 5B candidate run and its
replay, and the post-coverage triage results.

## 6a. Test verification

`docker compose run --rm backend python -m pytest tests -q`, with the repository's
`backend/tests` mounted (the backend image carries a stale baked-in copy that predates
`test_production_score_store.py`):

**84 passed, 0 failed, 24 errors.**

All 24 errors are the same environmental cause as blocker 1 — `methodology_family` and the
`production_*` tables do not exist because migrations 025 and 026 are unapplied. 14 are
`test_production_score_store.py`, 10 are `test_integration.py`. None relate to Phase 5B.

Three tests were updated because Phase 5B legitimately changed the corpus counts they had
frozen:

- `test_phase5_bounded.py` asserted that exactly two calculation runs use
  `phase5-corpus-anomaly-policy-v2`. Phase 5B reuses that policy, so the assertion is now
  **scoped to the Phase 5 namespace** — a strictly tighter guard that checks what it
  intended to check.
- `test_mvp_mapping_policy.py` asserted `ai_mapping_runs == 3` and `ai_task_mappings ==
  10752`; updated to 4 and 13,099 for the completion mapper's 2,347 new mappings.
- The same file's isolation test asserted `persisted_ai_mappings == 10752` and
  `eligible_ai_mappings == 10660`; updated to 13,099 and 13,007. The fields this test exists
  to guard — legacy `occupation_scores`, `task_ai_scores`, active scoring jobs, frontier
  values — are zero-valued or unchanged and were not touched.

No assertion was removed, and no gate was loosened.

## 7. Answers

1. **Did raising the mapping target solve the artificial coverage bottleneck?** Yes. Median
   coverage 71.6 → 84.9; the pile-up above 70 is gone and was not recreated above 80.
2. **How many occupations now reach ≥80% coverage?** 567.
3. **How many are now Phase 6 launch eligible?** **507** (503 with no finding above `low`).
4. **How many remain blocked by genuine evidence limitations?** 311, all with zero
   defensibly mappable tasks remaining.
5. **Did additional evidence materially change scores?** No. Mean absolute Exposure change
   0.86, mean absolute Replacement change 0.29, five occupations over 5 points, none over
   10, and no directional drift (signed mean +0.07, correlation with coverage gain 0.02).
6. **Did provisional sensitivity become a significant remaining bottleneck?** Yes. 106 fail
   the rule and **59 are now blocked by nothing else**, concentrated in construction (28).
7. **Did any systemic scoring anomaly appear?** No. None introduced; nine resolved.
8. **Are we ready to move to production-promotion review?**

## Verdict

**NOT READY FOR PROMOTION REVIEW**

The cohort is sound and the methodology held. The blockers are environmental and procedural,
not analytical. Smallest specific blockers:

1. **Migrations 025, 026 and 028 are not applied to this database.** The production score
   store, the v2 model registration and the public-content tables do not exist here — only
   001–024 plus 027, which was applied during this phase to persist the baseline triage.
   Promotion has nowhere to write. This is the hard blocker.
2. **No promotion transaction exists.** Still unwritten, correctly — its shape is pinned by
   migration 025 and exercised by
   `backend/tests/production_fixtures.py::build_promotion_run`.
3. **No approved identity list.** The schema deliberately has no "promote everything" path.
   507 is a triage result, not an approval; someone has to approve identities.
4. **Editorial content does not exist for the cohort.** 9 editorial `occupations` rows
   against a 507-occupation cohort. Snapshots may be promoted before this, but no page can
   be published without it. The content pipeline has not been run.
5. **The provisional-model decision is now unavoidable.** 59 occupations turn on adoption
   pressure and labour-market resilience alone, and those two models still carry 25% of
   replacement weight for *every* occupation in the cohort — including the 507. Passing the
   3-point sensitivity rule means the weak model did not happen to move that score; it is
   not validation of the model. This should be settled before, not after, publication.

None of these are reasons to revisit Phase 5B. They are the work that follows it.
