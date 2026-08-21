# Phase 5B — Coverage completion report

Date: 2026-08-21
Status: **Nothing promoted. No occupation activated. `is_active` still JVS 1.0.3.**

Phase 5B adds task-mapping evidence and nothing else. No formula, weight, threshold,
taxonomy or rubric changed. The scoring engine, the 70% scoring-eligibility rule and the
80% launch gate are all untouched.

## 1. Why this phase exists

The live Phase 6 triage over `phase5-bounded-corpus-v2-2026q3` returned a launch cohort of
**8 out of 878**, with 868 candidates blocked by `weighted_coverage_below_launch_minimum`.

That was not a quality result. `enrichment/generate_phase5_candidate_mappings.py:294` stops
mapping an occupation the moment weighted coverage crosses 70:

```python
if total_weight > 0 and 100.0 * covered_weight / total_weight >= COVERAGE_THRESHOLD:
    break
```

Tasks are walked in descending source weight, so each occupation was mapped down to roughly
the 70% line and abandoned. Corpus coverage was therefore p25 70.4 / median 71.6 / p75 73.0,
and only 10 of 878 candidates reached 80 at all. The Phase 6 launch gate of 80 was being
applied to a corpus deliberately constructed to stop at 70. A pipeline-coverage mismatch,
not a corpus quality ceiling.

The 8 survivors were not better-evidenced occupations. They were occupations that overshot
the 70 line incidentally — few tasks, or heavy mapping reuse.

## 2. The three thresholds, kept separate

| Threshold | Purpose | Where enforced | Changed by 5B |
|---|---|---|---|
| **70** | scoring eligibility — may a score exist at all | occupation formula `minimumWeightedCoverage` | no |
| **85** | mapping completion — when does mapping work stop | `phase5b-mapping-completion-v1` | new |
| **80** | public launch coverage — may a score be published | `phase6_launch_triage` GATES | no |

85 was chosen over 80 deliberately. Stopping at the publication threshold would have
recreated the same artefact one gate higher — a corpus piled up just above 80 instead of
just above 70. Stopping at 85 leaves the launch gate measuring evidence rather than
measuring the stopping rule.

The completion target is **not a quota**. An occupation that exhausts its defensibly
mappable tasks at 74% is recorded at 74%.

## 3. What was run

New, versioned, additive. The Phase 5 namespace and run are untouched and remain readable.

| Artefact | Version | Notes |
|---|---|---|
| Mapping policy | `phase5b-mapping-completion-v1` | new scope version |
| Namespace | `phase5b-candidate-2026q3-v1` | completes `phase5-candidate-2026q3-v1` |
| Mapping run | `phase5b-completion-mapper-v1-2026q3` | run id 34 |
| Calculation run | `phase5b-coverage-completion-2026q3-v1` | run id 4 |
| Replay | `phase5b-coverage-completion-2026q3-replay-v1` | run id 5, matched |

The Phase 5B namespace records `coverage_threshold = 85`. That column is a record of the
mapping-completion target only; the scoring gate is read from the occupation formula, so
raising it cannot and did not move the 70% eligibility rule.

Population is byte-identical to Phase 5 — the generator refuses to run otherwise, because a
different population would make the score comparison meaningless:

```
populationHash 0ac3b97fdf0a8f857251e053ccc626d2a1709a74ef4ad3240e460a32c52e7fec
```

## 4. Compute discipline

**Zero external AI calls. Zero tokens.** The mapper is deterministic term-matching over the
O\*NET task statement — `disposition`, `capability_payload` and `constraint_payload` in
`enrichment/generate_phase4a_pilot_mappings.py` are pure functions with no network path.
`inferenceBeyondTaskText` is recorded `false` on every requirement and constraint written.

| | |
|---|---|
| Mapping pass local compute | 7.2 s |
| Scoring pass local compute | 17.7 s |
| External AI calls | 0 |
| Estimated tokens | 0 |

No existing mapping was regenerated. Every mapping Phase 5 produced was reused by task id or
statement hash.

## 5. Mapping pass — what happened to every task

Source occupations attempted: **878**. Source tasks in scope: **17,843**.

| Scope decision | Phase 5 | Phase 5B |
|---|---:|---:|
| `generated` | 10,253 | 2,347 |
| `reused_exact_task` | 393 | 10,646 |
| `reused_task_hash` | 169 | 343 |
| `unmapped_insufficient_evidence` | 2,264 | 2,996 |
| `unmapped_after_gate` / after target | 4,559 | 1,309 |
| `source_weight_ineligible` | 205 | 202 |
| **Mapped total** | **10,815** | **13,336** |

Where every Phase 5 decision ended up:

| Phase 5 → Phase 5B | Tasks | Meaning |
|---|---:|---|
| `generated` → `reused_exact_task` | 10,253 | every Phase 5 mapping reused, none regenerated |
| `reused_exact_task` → `reused_exact_task` | 393 | prior reuse preserved |
| `reused_task_hash` → `reused_task_hash` | 169 | prior reuse preserved |
| `unmapped_after_gate` → `generated` | **2,347** | the completion work |
| `unmapped_after_gate` → `reused_task_hash` | 171 | mappable by an existing statement match |
| `unmapped_after_gate` → `unmapped_insufficient_evidence` | 735 | examined for the first time, judged too thin |
| `unmapped_after_gate` → `unmapped_after_gate` | 1,306 | occupation reached 85% before reaching them |
| `unmapped_insufficient_evidence` → same | 2,261 | rubric decision unchanged |
| `unmapped_insufficient_evidence` → `unmapped_after_gate` | 3 | reordering under the higher target |
| `source_weight_ineligible` → same | 202 | no importance/frequency; never imputed |
| `source_weight_ineligible` → `reused_task_hash` | 3 | statement match existed |

**4,559 `unmapped_after_gate` tasks examined. 2,518 became mapped evidence (2,347 newly
generated, 171 by hash reuse). 735 were judged ambiguous under the unchanged rubric. 1,306
remain unmapped because their occupation had already reached the completion target.**

Tasks still unmapped in Phase 5B, with the exact reason:

| Reason | Tasks |
|---|---:|
| Ambiguous or insufficient task description under the approved rubric | 2,996 |
| Occupation reached the 85% completion target before this task | 1,309 |
| Source importance or frequency missing; excluded from weighted coverage | 202 |

Nothing was invented to close any of these.

## 6. Coverage, before and after

| Statistic | Phase 5 | Phase 5B |
|---|---:|---:|
| mean | 70.55 | **79.82** |
| sd | 6.24 | 10.29 |
| min | 23.27 | 23.27 |
| p10 | 66.18 | 66.18 |
| p25 | 70.40 | 75.52 |
| p50 | 71.61 | **84.85** |
| p75 | 72.98 | 86.34 |
| p90 | 74.22 | 87.74 |
| p95 | 75.29 | 88.83 |
| max | 100.00 | 100.00 |

The rising standard deviation is the point. Phase 5's tight 6.2 spread around 71.6 was the
stopping rule reporting itself; Phase 5B's 10.3 spread is occupations differing in how much
evidence they actually have.

| Coverage band | Phase 5 | Phase 5B |
|---|---:|---:|
| ≥ 90% | 3 | 17 |
| 85 – 89.99% | 2 | 415 |
| 80 – 84.99% | 5 | 135 |
| 75 – 79.99% | 42 | 101 |
| 70 – 74.99% | 692 | 76 |
| < 70% | 134 | 134 |

**Occupations at or above the 80% launch gate: 10 → 567.**

Confidence followed, as expected — it is 0.5 × coverage plus a near-constant residual:
mean 74.78 → 78.49, median 76.40 → 81.31.

The 134 occupations below the 70% scoring-eligibility threshold did not move. They have no
mappable evidence left to add; their shortfall is ambiguity, not truncation.

## 7. Occupations that cannot defensibly reach 80%

**311.** Every one of them has **zero** remaining mappable tasks — the completion pass
exhausted them. Their residual unmapped weight is ambiguous or insufficient task text,
between 20% and 77% of their weighted total (median 28%, median 6 ambiguous tasks each).

| Coverage band | Occupations | What blocks them |
|---|---:|---|
| < 70% | 134 | ambiguous/insufficient task descriptions; also below the scoring gate |
| 70 – 74.99% | 76 | ambiguous/insufficient task descriptions |
| 75 – 79.99% | 101 | ambiguous/insufficient task descriptions |

17 of the 311 additionally carry at least one task with missing importance or frequency.

These are **not engineering failures**. O\*NET's statements for this work are too thin to map
without inventing scope. They should remain unpublished until the source improves. Nothing
in this phase should be read as a reason to relax the rubric to recover them.

## 8. Isolation and safety

Verified unchanged after every step:

- Phase 5 run `phase5-bounded-corpus-v2-2026q3` (id 2) and its namespace — untouched, still readable
- Legacy `occupation_scores`: 11 rows; `task_ai_scores`: 23 rows — unchanged
- Public occupations: 0 — unchanged
- Archetype scoring: disabled — unchanged
- Active scoring model: JVS 1.0.3 — unchanged
- No production score writes, no promotions, no activations

The Phase 5 runner asserts production isolation itself and would have aborted the
transaction on any drift; it did not fire.

Migration 027 was applied to this database to persist the Phase 6 baseline triage — it was
present in the repository but had never been applied here. It creates two new tables and
changes no existing data. Migrations 025, 026 and 028 remain unapplied.

## 9. Answers

1. **Did raising the mapping target solve the artificial coverage bottleneck?** Yes. Median
   coverage 71.6 → 84.9, and occupations at or above the launch gate 10 → 567. The
   concentration just above 70 is gone and was not recreated above 80.
2. **How many occupations now reach ≥80% coverage?** 567.
3. **How many remain blocked by genuine evidence limitations?** 311, all with zero
   defensibly mappable tasks remaining.

Score impact is in `PHASE5B_SCORE_DELTA_REPORT.md`; the re-triage is in
`PHASE6_POST_COVERAGE_TRIAGE_REPORT.md`.
