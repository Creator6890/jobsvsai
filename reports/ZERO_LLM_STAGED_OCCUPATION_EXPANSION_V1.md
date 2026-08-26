# Zero-LLM Staged Occupation Expansion V1

**Date:** 2026-08-26 · **Scope:** triage only · **Nothing promoted, nothing written, nothing deployed**

## Result

**No occupation can be promoted without new model work. The zero-LLM promotion cohort is empty.**

This is not a shortfall in the search for candidates. It is a structural property of the corpus,
and the reconciliation is exact:

```
occupations whose coverage can ever reach the 80% launch gate    567   (corpus ceiling)
already public                                                   507
────────────────────────────────────────────────────────────────────
remaining headroom                                                60
  blocked solely by provisional_input_sensitivity                 59   (Step 2 forbids)
  blocked by a substantive scoring anomaly                         1   (Credit Counselors)
────────────────────────────────────────────────────────────────────
promotable with zero LLM calls                                     0
```

The Phase 6 promotion was **complete**, and that is provable rather than asserted. Two queries
settle it:

| Check | Result |
|---|---|
| Staged/review_required occupations the triage marked `launch_eligible` | **0** |
| Public occupations the triage marked **not** `launch_eligible` | **0** |

The mapping between "passes the launch gate" and "is public" is 1:1 with no gaps in either
direction. There is no occupation sitting in staging that already qualifies.

**External model calls made by this task: 0.** No Gemini, OpenAI or Anthropic call was issued.
No row was written to any table.

---

## 1. Triage of the 405 staged occupations

| Bucket | Count | Meaning |
|---|---|---|
| **A — zero-LLM promotable now** | **0** | nothing in staging already passes the gate |
| **B — zero-LLM minor remediation** | **0** | no occupation is blocked by a deterministic or metadata issue |
| **C — requires new model/mapping work** | **73** | could plausibly qualify once new evidence or validated models exist |
| **D — do not publish** | **332** | source-data limited; no amount of model work rescues them |
| | **405** | |

### How the 405 divide before bucketing

| | Count |
|---|---|
| Assessed by triage run 2 (`phase6-triage-postcoverage-2026q3-v1`) | 351 |
| Never assessed — outside the Phase 5 bounded corpus | 54 |

### The 351 assessed, by exact blocker signature

| Blocking codes | Count | Bucket |
|---|---|---|
| `weighted_coverage_below_launch_minimum` | 141 | D |
| `confidence` + `not_review_ready` + `weighted_coverage` | 96 | D |
| `provisional_input_sensitivity` | 57 | C |

| `confidence` + `not_review_ready` + `provisional_input_sensitivity` + `weighted_coverage` | 22 | D |
| `provisional_input_sensitivity` + `weighted_coverage` | 22 | D |
| `not_review_ready` + `weighted_coverage` | 9 | D |
| `confidence` + `weighted_coverage` | 2 | D |
| `confidence` + `provisional_input_sensitivity` + `weighted_coverage` | 1 | D |
| `high_replacement_despite_severe_constraints` | 1 | C |
| | **351** | |

### Why bucket B is empty — the load-bearing finding

Bucket B would contain occupations blocked only by something a deterministic recomputation,
snapshot regeneration, linkage repair or metadata fix could clear. **There are none**, and the
reason is visible in the single-blocker distribution. Only three codes ever appear alone:

| Sole blocker | Count | Deterministically fixable? |
|---|---|---|
| `weighted_coverage_below_launch_minimum` | 150 | **No** — needs task→capability mappings that do not exist |
| `provisional_input_sensitivity` | 59 | **No** — needs the two provisional replacement-risk factor models validated |
| `high_replacement_despite_severe_constraints` | 1 | **No** — a substantive scoring anomaly requiring analysis |

`not_review_ready` and `confidence_below_launch_minimum` — the two codes that *sound* like
metadata or recomputation problems — **never occur alone**. Every occurrence is accompanied by a
coverage or sensitivity blocker that binds first. So even if review-readiness were a flag one
could flip (it is not; it is derived from the candidate's own gate profile), flipping it would
promote nobody.

---

## 2. The 138 never in the Phase 5 corpus

54 are staged, 84 are `review_required`. The question Step 4 asks — *can any of these now be
scored entirely from existing data?* — has a clean answer, and it is a source-data answer.

| | Count |
|---|---|
| Never-assessed identities | 138 |
| With **zero** O\*NET task rows | 93 |
| With task rows but **zero weighting-eligible** tasks | 29 |
| With ≥1 weighting-eligible task | 16 |
| Ever a Phase 5 candidate | **0** |
| Carrying a genuine production score | **0** |

**Why they were excluded from Phase 5 is now established:** they have no weightable task base.
The methodology weights each task by importance × frequency; O\*NET publishes neither for these
occupations. The task rows carry `rating_status = 'missing_both'` and
`missing_rating_fields = {importance, frequency}`. A task with no importance and no frequency
cannot contribute weighted coverage at all, so no amount of task→capability mapping — LLM or
otherwise — produces a scoreable occupation. **This is a limit in the O\*NET source data, not an
engineering backlog.**

Of the 54 never-assessed staged occupations: **15** have weighting-eligible tasks (bucket C),
**39** do not (bucket D).

### The two staged identities that appear to carry production scores

A naive query suggests identities 8 and 9 have production snapshots. They do not. **Every one of
their snapshots belongs to a `rolled_back` pytest fixture run** (`pytest-promotion-base-…`,
`-restore-…`, `-currency-…`). This is exactly the trap CLAUDE.md documents: the production store
is append-only, rollback is a status change rather than a delete, and fixture runs accumulate
every time the suite runs. Neither identity has real scoring evidence.

---

## 3. Software Developers — the one case that looked promotable

Worth recording in full, because it is the highest-value consumer query in the corpus and it is
the only never-assessed occupation with existing task mappings.

| Property | Value |
|---|---|
| Identity | 8 · SOC **15-1252.00** · O\*NET "Software Developers" · editorial page "Software Developer" |
| Publication status | `staged` |
| O\*NET tasks | 17, **all weighting-eligible**, `rating_status = complete` |
| Existing task mappings | **17 — all 17 tasks mapped** |
| Mapping run | id 7, `phase4a-pilot-mapper-v1-2026q3`, status `completed` |

On its face this is a fully mapped, fully rated occupation that could be scored deterministically
today. **It cannot be promoted**, and the reason is written into the mapping run's own provenance:

```json
{ "phase": "4A", "pilotOnly": true, "scoreBlind": true,
  "activationAllowed": false, "productionScoreWritesAllowed": false }
```

The Phase 4A pilot mapper explicitly attests that its output may not be used for activation or
production score writes. Promoting Software Developers from these mappings would mean overriding
an attestation the run made about itself — precisely the kind of quiet quality erosion the
project's frozen decisions exist to prevent.

**Software Developers is one production-grade mapping run away from being publishable**, and it
is the single highest-value item in the deferred cohort. It needs 17 task assessments, not 17,000.

---

## 4. Compute budget

| | |
|---|---|
| Occupations evaluated | 405 staged (1,016-occupation taxonomy scanned) |
| Unmapped task rows examined | 4,559 |
| Mapping rows reused | 0 written; existing mappings read only |
| **New model assessments** | **0** |
| **External AI calls** | **0** (`"externalAiCalls": 0`, reported by the generator itself) |
| Deterministic coverage pass, wall clock | **1.3 s** |
| Rows written | **0** (`"persisted": false`) |
| Peak memory | negligible — the pass is streaming SQL plus rule evaluation |

The expansion analysis is genuinely cheap. That is worth stating plainly: **the cost of this
phase was not the obstacle. The evidence was.**

---

## 5. Remediation performed

**None.** Bucket B is empty, so there was nothing to remediate. No score was recomputed, no
snapshot regenerated, no publication metadata edited, no linkage altered.

## 6. Final promotion cohort

`ZERO_LLM_PROMOTION_COHORT` = **∅** (0 occupations).

No promotion write was performed. `occupation_publications` is untouched.

---

## 7. High-priority common jobs

| Occupation | Status | Reason |
|---|---|---|
| **Software Developers** | DEFERRED — NEEDS MODEL WORK | 17/17 tasks mapped, but only by the Phase 4A pilot mapper, which declares `activationAllowed: false`. Needs one production-grade mapping run. |
| **Data Scientists** | DO NOT PUBLISH | 16 tasks, **0 weighting-eligible** — O\*NET publishes no importance or frequency ratings. Not scoreable at any cost. |
| **Electricians** | DEFERRED — CURRENT GATE FAILURE | Coverage **100.0**, confidence **87.7**. Blocked *solely* by `provisional_input_sensitivity`. Step 2 forbids promoting on this basis. |
| **Cashiers** | DO NOT PUBLISH | Coverage 50.9, confidence 53.2 — fails coverage, confidence and review-readiness. |
| **Data Entry Keyers** | DO NOT PUBLISH | Coverage 64.6, confidence 70.3, plus sensitivity and review-readiness blockers. |
| **Waiters and Waitresses** | DO NOT PUBLISH | Coverage 71.5 — below the 80 gate, in the 311 cannot-reach set. |
| **Bakers** | DO NOT PUBLISH | Coverage 75.6 — below the gate, in the 311 cannot-reach set. |
| **Exercise Trainers and Group Fitness Instructors** | DO NOT PUBLISH | Coverage **79.3** — 0.7 points short. In the cannot-reach set: the remaining tasks are ambiguous text, not unmapped work. |
| **Project Management Specialists** | DO NOT PUBLISH | 20 tasks, **0 weighting-eligible** — `rating_status = missing_both`. |
| **Web and Digital Interface Designers** | DO NOT PUBLISH | 30 tasks, **0 weighting-eligible** — `rating_status = missing_both`. |

Exercise Trainers at 79.3 and the 22 occupations sitting between 79 and 80 are the sharpest
temptation in this dataset. They are not close-but-fixable; they are in the 311 for which zero
mappable tasks remain, and the shortfall is ambiguous O\*NET task text. Moving them would require
loosening the ambiguity rule, which CLAUDE.md prohibits and Step 2 reiterates.

---

## 8. Search-value impact

Because the promotion cohort is empty, the benchmark is **unchanged by construction**:

| | Current 507 | 507 + cohort (= 507) |
|---|---|---|
| Public top-3 | 95.7% (88/92) | 95.7% |
| Public misleading | 2.2% (2/92) | 2.2% |
| Non-public detection | 97.9% (93/95) | 97.9% |
| False substitution | 2.1% (2/95) | 2.1% |
| Critical queries | 21/21 | 21/21 |

No query changes state. No "analysis not available" panel becomes answerable, because no
occupation changed publication status.

### What the deferred cohorts would be worth (informational — not performed)

Recorded because it directly informs the next decision, and clearly marked as *not done*:

**If the 59 sensitivity-only occupations were published**, the public cohort would become 566 and
several ordinary consumer searches would resolve — most notably **Electricians** (coverage 100.0,
confidence 87.7). The 59 are concentrated in the trades: SOC 47 (construction) contributes 17,
SOC 51 and SOC 17 six each. Within the wider 106 that carry the sensitivity blocker, SOC 47
contributes 28, matching CLAUDE.md.

This is exactly the cohort whose scores depend on the two provisional replacement-risk factor
models carrying 25% of the weight. **Publishing them is a methodology decision, not an
engineering one**, and Step 2 explicitly withholds it.

---

## 9. Proposed public count

| | |
|---|---|
| Previous public | **507** |
| Newly promotable | **0** |
| Proposed public | **507** |
| Proposed live scores | **507** |

Unchanged, and deliberately not rounded toward any target.

## 10. Distribution and integrity check

The cohort is unchanged, so this is a health check on the existing 507 rather than a comparison.

| Metric | mean | median | SD | min | max |
|---|---|---|---|---|---|
| AI Exposure | 60.7 | 62.2 | 10.5 | 24.8 | 79.4 |
| Replacement Risk | 52.2 | 52.5 | 9.0 | 29.9 | 74.9 |

| Check | Result |
|---|---|
| Public publications | 507 |
| Rows in `current_production_occupation_scores` | 507 |
| Public **without** a live score | **0** |
| Live score **without** public status | **0** |
| Values outside 0–100 | **0** |
| Duplicate identities in live scores | **0** |

No impossible values, no orphans, no duplicate identities. Both distributions are unimodal and
neither saturates its bound — exposure tops out at 79.4 and replacement risk at 74.9, comfortably
inside the 95.0 `extremeHigh` gate, so no occupation is pinned at a clamp.

## 11. Search V2 interaction

Search V2 reads the public cohort through `current_production_occupation_scores` and the
publication gate at query time. **Nothing in it is pinned to 507.** Migration 034 deliberately
does not materialise publication status into `occupation_search_terms`; status is joined live
precisely so that promoting an occupation requires no view refresh and no code change. When a
future cohort is promoted, search picks it up automatically.

## 12. SEO

No occupation changed status, so no page changed indexability. Canonical URL rules are untouched,
no alias duplicate pages were created, and no directory page was added.

## 13. Privacy

Unchanged and preserved. `occupation_search_used` carries `query_result_count` and, on selection,
`selected_occupation_slug` — a published slug. No raw query text, no freeform string, and no
unpublished occupation title reaches GA4.

## 14. Deferred occupations

**Correction (2026-08-26).** An earlier revision of this report recorded C = 95 and D = 310,
splitting out 22 occupations as blocked by confidence, review-readiness and sensitivity but
*not* coverage. That was a transcription error: the signature string was truncated at 72
characters in the console and its trailing `+ weighted_coverage_below_launch_minimum` was lost.
Those 22 are coverage-blocked and belong in D. The corrected counts are **C = 73, D = 332**,
verified by direct cross-tab: 293 staged occupations carry the coverage blocker and 58 do not,
with no mismatches in either direction.

**Bucket C — 73 occupations, requiring new model work**

| Sub-cohort | Count | What unblocks it |
|---|---|---|
| Sensitivity-only | 57 | Validate the two provisional replacement-risk factor models (adoption pressure, labour-market resilience) |
| Never assessed, weighting-eligible tasks present | 15 | A production-grade task→capability mapping run |
| Credit Counselors (13-2071.00) | 1 | Investigate `high_replacement_despite_severe_constraints`: coverage 87.7, confidence 82.8, exposure 71.4, replacement risk 70.2 — the risk score crosses the 70.0 threshold while environmental constraints are severe |

**Bucket D — 310 occupations, do not publish**

| Sub-cohort | Count | Why no model work helps |
|---|---|---|
| Coverage-blocked | 293 | Part of the 311 for which zero mappable tasks remain; the shortfall is ambiguous O\*NET task text |
| Never assessed, no weighting-eligible task | 39 | O\*NET publishes no importance/frequency ratings — nothing to weight |

## 15. Recommended future model-work cohort, by value per unit of work

1. **Software Developers** — 17 tasks, all rated, all already mapped once. One production mapping
   run. Highest consumer value in the entire deferred set.
2. **The 15 never-assessed occupations with eligible tasks** — a bounded mapping run; the corpus
   ceiling rises by at most 15.
3. **The 59 sensitivity-only occupations** — no per-occupation mapping needed at all. What is
   needed is validation of two factor models. This is the best return on effort in the project:
   one methodology workstream unblocks 59 occupations including Electricians and much of the
   construction trades, and would also reduce the sensitivity exposure of the 507 already public.

The 311 coverage-blocked occupations should **not** appear on any roadmap as an engineering task.
They are a source-data limit.
