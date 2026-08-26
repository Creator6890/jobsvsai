# Preliminary Occupation Estimates V1

**Date:** 2026-08-26 · **Not deployed** · **Verified cohort unchanged at 507**

## Result

| | |
|---|---|
| **Verified occupations** | **507** (unchanged) |
| **Estimated occupations** | **390** |
| **Total public / searchable** | **897** |
| Insufficient evidence, not published | **15** |
| External model calls | **0** |

`data scientist`, `electrician`, `cashier` and `software engineer` now return an answer instead
of "we don't analyse that yet" — labelled, bounded, and never mistakable for a verified score.

---

## 1. Architecture

Two score classes, kept apart by the schema rather than by convention.

| | Verified | Estimated |
|---|---|---|
| Table | `production_occupation_score_snapshots` | `occupation_score_estimates` |
| Live read | `current_production_occupation_scores` | `current_published_occupation_estimates` |
| Publication recorded on | `occupation_publications.activation_status` | `occupation_score_estimates.is_published` |
| API field | `results` | `estimatedResults` |
| Schema | `Occupation` | `EstimatedOccupation` |

**`activation_status` still means exactly what it always meant.** 507 occupations are `public`;
405 are `staged`; 104 are `review_required`. The estimate layer does not touch that column, so
"verified count" and "public page count" are now two different numbers held in two different
tables rather than one number that quietly changed meaning.

Four guarantees are enforced by the database, and all four were tested by trying to violate
them:

| Attempted violation | Result |
|---|---|
| Store `score_status = 'verified'` in the estimate table | rejected — CHECK constraint |
| Publish an estimate for an identity holding a verified score | rejected — trigger |
| Change a published estimate's value | rejected — append-only trigger |
| Delete an estimate | rejected — append-only trigger |

A fifth case appeared during testing and is worth recording, because the test found it rather
than the design anticipating it. The insert trigger stops an estimate being published for an
*already*-verified occupation, but it cannot see the reverse: an occupation being promoted
later while its estimate sits published. That is the normal upgrade path, so it would have
happened eventually. `current_published_occupation_estimates` now excludes any identity that
has a verified score, which settles it structurally regardless of write order — a promotion run
does not have to remember to withdraw estimates.

## 1a. Reconciliation: the "80" that never existed

An earlier audit reported ~80 staged occupations as not coverage-blocked; E1 holds 58. These
are **the same set**, and the 80 was a transcription error of mine, not a second definition.

**E1's rule, as implemented** (`scoring/preliminary_estimates.py`,
`estimate_from_task_evidence`): the occupation has an engine-computed score from triage run 2
**and** `weighted_task_coverage >= FULL_COVERAGE_GATE (80.0)`. Nothing else. E2 is the same
rule with coverage below 80.

| Set | Definition | n |
|---|---|---|
| A | staged, assessed, **without** `weighted_coverage_below_launch_minimum` | **58** |
| B | current E1 | **58** |
| A ∩ B | | **58** |
| A − B | | **0** |
| B − A | | **0** |

Zero occupations in either difference, so there is nothing to explain occupation-by-occupation.
The coverage cross-tab confirms it independently: 58 staged occupations have coverage ≥ 80 and
no coverage blocker; 293 have coverage < 80 and a coverage blocker; **no occupation sits in
either off-diagonal cell**.

**Where 80 came from.** I summed a console-printed table of blocker signatures whose lines were
truncated at 72 characters. Two signatures are longer than that:

```
n= 22  len=123  confidence_below_launch_minimum + not_review_ready + provisional_input_s <<CUT
n=  1  len=104  confidence_below_launch_minimum + provisional_input_sensitivity + weight <<CUT
```

Both end in `+ weighted_coverage_below_launch_minimum`. Reading the 22-row line as though it
terminated at `provisional_input_s` put those 22 coverage-blocked occupations on the wrong side
of the ledger: 58 + 22 = 80. The error was corrected in the expansion report before this work
began; E1 was never built on it.

## 1b. Zero-LLM scoring salvage

The 138 occupations that never entered Phase 5 were audited for reusable evidence:

| Bucket | n | Meaning |
|---|---|---|
| **A — scoreable now, zero LLM** | **1** | every weighting-eligible task already carries a mapping |
| B — eligible tasks, no mappings | 15 | needs a mapping run |
| C — no weighting-eligible task | 122 | O\*NET publishes no importance/frequency ratings |

Bucket A contains exactly one occupation: **Software Developers**, 17 of 17 eligible tasks
mapped. `scoring/probe_occupation_score.py` was written to answer what the engine would say
about it — read-only, calling the same `calculate()` the pipeline calls, writing nothing. The
Phase 5 runners are namespace-driven and have no dry-run mode, so an occupation outside every
namespace cannot be scored by them without first creating a namespace, which is a write to
append-only methodological history and a decision that should rest on evidence rather than be
required in order to obtain it.

**Result — Software Developers, from its own mappings, zero model calls:**

| | |
|---|---|
| Weighting-eligible tasks | 17 |
| Mapped | 17 |
| Scoring-eligible after the ambiguity rule | 14 (3 excluded) |
| **Weighted task coverage** | **85.98%** (gate 80) ✅ |
| **Confidence** | **82.84** (gate 75) ✅ |
| **AI Exposure** | **75.49** |
| **Replacement Risk** | **71.95** |
| Provisional sensitivity (max absolute impact) | **1.886** (gate < 3.0) ✅ |
| **Launch gates** | **passed — zero blocking findings** |
| Findings | `provisional_models_in_use` (low) — carried by all 507 verified occupations |

The gates were evaluated by the real assessor, `phase6_launch_triage.triage_occupation`, not a
reimplementation.

**Two gates cannot be evaluated for one occupation in isolation, and the probe says so rather
than implying a clean sweep.** Review-readiness is a property of a candidate row that does not
exist, so the probe asserts it; related-SOC discontinuity is a corpus-level comparison against
sibling occupations. A real scoring run would evaluate both.

**What was done with this, and what was not.** Software Developers now has its own engine
evidence, so it is **E1**, not E3 — own evidence always outranks a related-occupation proxy,
and leaving it on borrowed numbers while its own mappings sat unused would be choosing the
weaker evidence because it was easier to reach. It was **not** promoted to verified. Doing so
requires creating a Phase 5 scoring namespace, running the scorer, triaging and promoting —
new pipeline machinery, written at the deployment gate, writing to append-only methodological
tables. The evidence says it would pass; the architect should be the one to authorise the run
that makes it so.

## 2. Evidence hierarchy

Every tier is deterministic and reads only data already imported. **No tier uses the
occupation's title.** "Software Developer sounds automatable" is not evidence, and a plausible
number attached to no warrant is indistinguishable, to the reader, from a measured one.

| Tier | Evidence | n | Rendering |
|---|---|---|---|
| **E1** | Complete task evidence (coverage ≥ 80). The validated engine's own score, withheld from the verified cohort by a *publication* gate — or, for Software Developers, by never having been scored at all until now. | **59** | point |
| **E2** | Partial task evidence. The engine's score over coverage below 80. | **293** | point ≥70, range <70 |
| **E3** | No task evidence. Weighted average of verified O\*NET-related occupations, weighted by relatedness tier (Primary-Short 3, Primary-Long 2, Supplemental 1). | **38** | always a range |
| **E4** | Occupation-characteristic archetype | **0** | not built |

**E4 has no members and was deliberately not built.** The tier would apply to an occupation with
no verified relatives but with element ratings to build an archetype from. Cross-tabulating the
54 never-assessed staged occupations: 39 have verified relatives, 15 have neither relatives nor
element ratings, and **none** has element ratings without relatives. Building an unexercised
tier would mean shipping untested code and an uncalibrated method for zero occupations.

### E1 carries no borrowed evidence

Verified directly, not assumed:

| Check | Result |
|---|---|
| E1 estimates with a related-occupation source | **0** |
| E1 estimates with `supporting_relative_count` set | **0** |
| E1 estimates recording their own weighted coverage | **58 of 58** |
| Lowest E1 coverage / confidence | 80.221 / 79.090 |

No E1 point estimate is contaminated by proxy data, and E2 likewise carries zero
`evidence_sources` across all 293.

### The pilot-mapping question, resolved

Six estimates — including **Electricians**, the only E1 among them — sit on occupations whose
task mappings come *solely* from the Phase 4A pilot mapper (run 7), whose provenance declares
`pilotOnly: true`, `activationAllowed: false`, `productionScoreWritesAllowed: false`. That reads
like disqualifying evidence.

It is not, and the reason is decisive: **run 7 covers twelve occupations and five of them are
already in the verified cohort** — Accountants and Auditors, Statisticians, Secondary School
Teachers, Photographers, Nurse Practitioners. Run 7 contributed 1,455 task assessments to the
Phase 5 calculation runs that produced the promoted scores. The flags constrain that run as a
*pipeline actor*; they do not quarantine its mappings from downstream scoring which has since
consumed and validated them. Holding staged occupations to a stricter standard than the verified
cohort already meets would be incoherent.

**No reclassification was required.** This also corrects a claim in the preceding expansion
report — see that report's Software Developers correction.

**The estimator never adjusts an engine score.** For E1 and E2 the number is the engine's own
output, unmodified; what varies with confidence is the label and whether a range is shown.
Nudging a validated output because we are less sure of it would produce a third quantity that
is neither the engine's answer nor an honest estimate. A test pins this.

## 3–4. Calibration and error statistics

### What "calibration" means for each tier

Only E3 can be calibrated by hidden-target validation, and pretending otherwise would be
fabricating a test.

* **E1 and E2 are not estimators.** They are the validated engine's own output over the
  occupation's own task evidence, unmodified. A leave-one-out test would be asking the engine
  to reproduce itself, which it does exactly, and reporting MAE 0.00 would be a meaningless
  number dressed as a reassuring one. Their uncertainty is not estimation error at all — it is
  the question of whether *more* evidence would move the score, which is a truncation question
  requiring the engine be re-run over deliberately incomplete evidence. That work is not done
  here, and §17 records it as a limitation rather than papering over it.
* **E3 is a genuine inference** and is calibrated below.

### E3 — leave-one-out against all 507 verified occupations

Each verified occupation's own evidence is discarded and its score rebuilt from its verified
relatives alone, exactly as a staged occupation's would be.

| | MAE | median | p90 | p95 | max | band agreement |
|---|---|---|---|---|---|---|
| **AI Exposure** | 4.68 | **3.60** | **10.15** | 13.27 | 28.61 | 77.9% |
| **Replacement Risk** | 3.65 | **2.84** | **7.73** | 9.53 | 16.01 | 77.5% |

| Acceptance threshold | Target | Exposure | Replacement |
|---|---|---|---|
| Median absolute error | ≤ 8 | **3.60** ✅ | **2.84** ✅ |
| 90th percentile error | ≤ 15 | **10.15** ✅ | **7.73** ✅ |

Both clear with room, so no tier was withheld for poor calibration. Calibration is re-measured
on every run and stored on the run row.

## 5. Confidence policy — derived, and it overturned the obvious choice

The first implementation split E3 confidence on **how many** verified relatives an occupation
had, on the strength of a p90 of 17.8 in a 3–5-relative bucket. That bucket held twelve
occupations and counted *all* relatives rather than strong ones. Re-measured properly across
strong-relative strata, the effect disappears:

| Strong relatives | n | Exposure MAE | p90 | Replacement MAE | p90 |
|---|---|---|---|---|---|
| 1–2 | 23 | 4.93 | 9.1 | 5.04 | 8.0 |
| 3–5 | 127 | 4.84 | 9.8 | 3.66 | 7.7 |
| 6–9 | 333 | 4.64 | 10.4 | 3.56 | 7.6 |
| 10–14 | 21 | 4.12 | 8.6 | 3.43 | 6.3 |

Error is essentially flat from two relatives to fourteen. **Counting relatives does not predict
accuracy**: correlation with absolute error is **+0.003** for exposure and **−0.070** for
replacement risk.

What does predict it is whether the borrowed occupations **agree with one another** — the
weighted standard deviation of their own scores about the weighted mean:

| Exposure dispersion | n | MAE | median | p90 | p95 |
|---|---|---|---|---|---|
| < 6 | 284 | 3.87 | 3.14 | 8.2 | 10.7 |
| 6–9 | 164 | 5.88 | 4.78 | 12.4 | 14.7 |
| 9–12 | 55 | 5.08 | 4.69 | 10.4 | 14.3 |
| ≥ 12 | 4 | 7.50 | 5.40 | 18.2 | 18.2 |

| Replacement dispersion | n | MAE | median | p90 | p95 |
|---|---|---|---|---|---|
| < 5 | 284 | 3.23 | 2.41 | 7.3 | 8.7 |
| 5–7 | 184 | 3.90 | 3.18 | 7.6 | 8.9 |
| 7–9 | 33 | 5.30 | 4.89 | 9.5 | 12.4 |
| ≥ 9 | 6 | 6.94 | 5.29 | 13.4 | 13.4 |

Correlation with absolute error: **+0.221** and **+0.235** — small in absolute terms, but two
orders of magnitude better than counting, and the strata are monotonic. The intuition it encodes
is simple: when the occupations we are borrowing from agree, their average is trustworthy; when
they disagree, it is not, and *no quantity of disagreeing sources fixes that*.

**The implemented policy** (`EXPOSURE_DISPERSION_BANDS = (6.0, 12.0)`,
`REPLACEMENT_DISPERSION_BANDS = (5.0, 9.0)`): an E3 estimate is **moderate**-confidence when
both dispersions fall in the lowest band and **low** otherwise. E3 is never "higher" — a
borrowed number does not become a measurement of this occupation however well its sources agree.

Two occupations show the change most clearly:

| Occupation | Under counting | Under dispersion | Why |
|---|---|---|---|
| **Software Developer** | low, 53–89 | **moderate, 62–80** | only 5 relatives, but they agree |
| **Project Management Specialists** | moderate, 58–78 | **low, 55–81** | 14 relatives that disagree |

Counting had both backwards.

## 6. Range policy — widths are the measured p90

Half-widths are the observed p90 absolute error of each dispersion stratum, rounded up to a
whole point, so a rendered range is a ~90% interval rather than a decorative one. Observed p90s
were 8.2 / 12.4 / 18.2 (exposure) and 7.3 / 7.6–9.5 / 13.4 (replacement); the middle strata are
merged and widened to the larger of the pair, because a range that *narrowed* as the evidence
got worse would invert the signal it exists to send.

| Stratum | Exposure half-width | Replacement half-width |
|---|---|---|
| Lowest dispersion | ±9 | ±8 |
| Middle | ±13 | ±10 |
| Highest | ±19 | ±14 |

**Does the range actually contain the truth?** Checked against all 507 verified scores:

| | Count-based (previous) | Dispersion-based (now) |
|---|---|---|
| Exposure range covers the verified score | 89.7% | **91.7%** |
| Replacement range covers the verified score | 91.3% | **94.1%** |

Better calibrated *and* better covering, with no widening of the typical case: 15 of the 39 E3
estimates sit in the tightest band.

E2 keeps a fixed conservative width (±8 / ±6) below 70% coverage. Its uncertainty is about
*absent* coverage rather than disagreeing relatives, so the E3 strata do not describe it, and
reusing their numbers would mean borrowing a calibration that does not apply.

## 6a. Outlier review — the tail the MAE hides

The worst errors are not ignorable just because the median is 3.6. The ten largest exposure
errors:

| Error | Verified | Estimated | Relatives (strong) | Range covers? | Occupation |
|---|---|---|---|---|---|
| 28.6 | 34.4 | 63 | 9 (4) | no | Travel Agents |
| 24.5 | 71.5 | 47 | 15 (9) | no | Glass Blowers, Molders, Benders and Finishers |
| 22.3 | 70.3 | 48 | 13 (7) | no | Graders and Sorters, Agricultural Products |
| 21.6 | 65.6 | 44 | 15 (8) | no | Shoe Machine Operators and Tenders |
| 19.5 | 68.5 | 49 | 13 (6) | no | Model Makers, Wood |
| 18.9 | 45.1 | 64 | 4 (3) | no | Driver/Sales Workers |
| 18.5 | 77.5 | 59 | 12 (6) | no | Sound Engineering Technicians |
| 18.3 | 39.7 | 58 | 16 (9) | no | Solar Energy Installation Managers |
| 18.3 | 45.7 | 64 | 3 (1) | no | Food Servers, Nonrestaurant |
| 18.2 | 35.8 | 54 | 9 (5) | no | Insurance Appraisers, Auto Damage |

Worst replacement errors run 12.2–16.0 (Cost Estimators, Wind Energy Engineers, Poets and
Creative Writers, Aerospace Engineers, Credit Analysts).

Three honest observations:

1. **Relative count does not explain the tail.** The worst case has nine relatives, and several
   have thirteen to sixteen. This is the same finding as §5 arriving from the other direction.
2. **A confidence downgrade would not have caught most of them.** The ranges as rendered do not
   cover these errors, and widening bands far enough to cover a 28-point miss would make every
   estimate useless. The tail is a real limit of the method, not a tuning failure.
3. **The failure is semantic, not statistical.** Travel Agents is the clearest case: O*NET
   relates it to customer-service and sales occupations, whose AI exposure is much higher than
   the verified score for Travel Agents itself. Relatedness in the O*NET sense — similar
   activities, skills and context — is not the same as similar *automatability*, and where the
   two come apart the proxy is wrong in a way no amount of dispersion measurement detects. This
   is the strongest single argument for keeping estimates out of rankings, and it is why the
   page shows a range and names its sources rather than asserting a figure.

## 7. The staged 405

| Tier | Count |
|---|---|
| E1 | 59 |
| E2 | 293 |
| E3 | 38 |
| E4 | 0 |
| **Insufficient evidence** | **15** |
| | **405** |

The 15 are **every SOC 55 occupation** — Infantry, Special Forces, Air Crew Members, Artillery
and Missile Officers and the rest. O\*NET publishes no task ratings and no related-occupation
links for military occupations, so there is nothing to measure and nothing to borrow from. They
are not published, and no amount of method work changes that.

## 8. High-value occupations

| Occupation | Tier | Source | AI Exposure | Replacement Risk | Confidence | Relatives |
|---|---|---|---|---|---|---|
| **Electricians** | E1 | own task evidence, 100% coverage | **~47** | **~33** | Higher | — |
| **Exercise Trainers** | E2 | own task evidence, 79.3% | ~60 | ~45 | Moderate | — |
| **Bakers** | E2 | own task evidence, 75.6% | ~64 | ~50 | Moderate | — |
| **Waiters and Waitresses** | E2 | own task evidence, 71.5% | ~65 | ~49 | Moderate | — |
| **Data Entry Keyers** | E2 | own task evidence, 64.6% | **59–75** | **55–67** | Low | — |
| **Cashiers** | E2 | own task evidence, 50.9% | **52–68** | **44–56** | Low | — |
| **Data Scientists** | E3 | verified relatives | **67–85** | **63–79** | Moderate | 13 |
| **Software Developers** | **E1** | **own task evidence, 85.98% coverage** | **~75** | **~72** | Higher | — |
| **Web/Digital Interface Designers** | E3 | verified relatives | **63–81** | **59–75** | Moderate | 9 |
| **Project Management Specialists** | E3 | verified relatives | **55–81** | **49–69** | Low | 14 |

All ten carry a published estimate. Two render under pre-existing consumer-facing titles —
Software Developer and, for Web and Digital Interface Designers, **UX Researcher** — because
those editorial pages already existed and an editorial decision already taken is not revisited.
The canonical identity remains the O\*NET SOC code in both cases.

Software Developer and Project Management Specialists swapped confidence bands when the policy
moved from counting relatives to measuring their agreement; see §5.

## 8. Public counts

```
VERIFIED OCCUPATIONS        507      activation_status = 'public'
VERIFIED LIVE SCORES        507      current_production_occupation_scores
ESTIMATED OCCUPATIONS       390      current_published_occupation_estimates
TOTAL PUBLIC / SEARCHABLE   897      editorial pages, both classes
OVERLAP                       0      enforced by trigger and by the view
```

The old "507 public" invariant is retired. What remains invariant is the *relationship*: every
`public` publication has exactly one live verified score, and no identity carries both a
verified score and a published estimate. Tests assert the relationships, not the counts, so the
session-scoped fixtures that move ambient numbers cannot make them flap.

**Score distributions** (estimated cohort; the verified cohort is unchanged):

| | mean | median | SD | min | max |
|---|---|---|---|---|---|
| AI Exposure | 59.4 | 61.0 | 11.4 | 24 | 80 |
| Replacement Risk | 50.4 | 50.5 | 10.0 | 29 | 73 |

Close to the verified cohort (60.7 / 52.2) and neither saturates its bound, which is what one
would expect if the estimator is not systematically biased. Signed mean bias on the
leave-one-out test is −1.07 for exposure and −0.22 for replacement risk: slightly conservative,
not materially skewed.

## 9. Search V2 integration

**Relevance decides ranking; score class decides only the label.** `TermMatch.is_public` was
redefined from "activation_status is public" to "has a published analysis of either class", and
gained `score_status`. The semantic-tie logic is untouched — it already resolved intent before
consulting publication, which is precisely why it needed no change.

The two classes are hydrated into separate response fields, so a client that has not been
updated for estimates receives an empty `results` rather than an estimate it might render as
verified. Verified payloads are byte-identical to before.

The legacy `/occupations/search` endpoint is **verified-only by contract**: its
`list[Occupation]` shape carries task exposure and factor breakdowns that an estimate does not
have, and there is no way to place one in that list without inventing those values.

Suggestions are labelled compactly — "Verified analysis" / "Preliminary estimate" — and
browser-verified: `nurse` returns three verified plus one estimate; `data scientist` returns
Data Scientists as a preliminary estimate rather than a verified but unrelated occupation.

## 10. Rankings — verified only

Estimated occupations cannot reach the Highest/Lowest Replacement Risk lists, and not because a
filter excludes them. Every verified read path composes `public_occupation_predicate`, which
gates on `activation_status = 'public'` — a status no estimate ever receives. A filter is
something a future query can forget; this is not. Verified in the browser: 20 job links on
`/rankings`, zero of which are estimated. A test asserts it directly.

## 11–13. Career Fit, Compare, Action Plans

**Career Fit: verified-only for V1.** Its ranking algorithm has no notion of estimate
confidence, so introducing estimates would let a low-confidence proxy outrank a measured score
with no way for the user to see why. Excluded by the same publication predicate.

**Compare: verified-only for V1.** Two occupations side by side with visually equivalent
numbers is exactly the presentation the labelling rules forbid, and building a comparison view
that renders one column as a range and the other as a point is real design work rather than a
flag. Documented rather than half-built.

**Action Plans and Career Transitions: withheld for estimated occupations.** They need
validated task-level evidence. The estimate page says so explicitly — "A detailed task
breakdown, career transitions and an action plan need validated task-level evidence… we would
rather leave them out than generate guidance we cannot stand behind" — rather than rendering an
empty section.

## 14. Methodology and disclaimer

`/methodology#preliminary-estimates` explains both classes, the three tiers, the calibration
numbers, the limits and the upgrade path. It does not claim estimates passed validation.

Disclaimers are **per tier**, because one sentence cannot be true of all of them. The suggested
wording asserts insufficient evidence, which is false for E1 — those occupations have *complete*
task evidence and are withheld by a review gate. Telling their readers otherwise would make the
estimate layer's own explanations inaccurate, which defeats its purpose. E1 instead reads: "This
occupation has complete task-level evidence, but has not yet cleared JobsVsAI's full validation
review."

Placement is deliberate: **status and confidence appear above the first digit**, not beneath it.
A disclaimer below a number is read after the number has already been believed.

## 15. SEO

One canonical page per occupation, no alias duplicates, canonical URL rules unchanged. 385 pages
created and 5 existing pages updated in place (titles and slugs preserved). Pages carry the
O\*NET summary verbatim plus the evidence explanation, so they are not thin score-only pages.
`verdict` is written empty rather than templated — the verdict template describes a promoted
snapshot, and there is none.

Page metadata says "preliminary estimate" in the title and description too: a page that is
honest on screen and silent in search results is only half honest.

## 16. Tests

| Suite | Result |
|---|---|
| `./scripts/run-tests.sh` | **586 passed, 3 skipped, 0 failed** |
| `npm test` | **67 passed, 0 failed** |
| `npm run lint` | clean |
| `npm run build` | succeeds |
| Browser QA | PASS |

New coverage: the four database guards, the dispersion-based confidence policy (two agreeing
relatives outrank ten disagreeing ones) and its monotonic range widths, per-tier estimator behaviour, reproducibility, integer
rendering, "no relatives produces no estimate", migration additivity, the no-overlap invariant,
publication/score one-to-one, rankings exclusion, the separate API field, disclaimer presence,
absence of internal status vocabulary, and that search ranks identity relevance over score
class.

**Three pre-existing tests needed updating, and it is worth being explicit about why**, since
changing a test to make new code pass is usually the wrong move:

* `test_public_results_are_all_actually_public` asserted every shown result had
  `activation_status = 'public'`. That is no longer the definition of showable. It now asserts
  every result carries a known score class — the property that actually matters.
* The benchmark's "non-public detection" band scored success as returning
  `occupation_not_available`. Those occupations now have estimates, so declining to analyse them
  would be a regression rather than a success. The band always really measured *substitution* —
  did we answer with the occupation the user meant, or a different one — so detection is now
  "the intended occupation is the one named", in whichever class.
* `test_legacy_endpoint_shares_the_v2_resolver` compared the legacy list against every resolver
  match. The legacy shape is verified-only by contract, so it compares against the verified
  subset.

One test **fixture** was also fixed rather than the code: `ensure_related_occupations` reused any
pre-existing related row, but the reader resolves `max(content_run_id)` per occupation, so a
later content run covering the whole corpus silently shadowed the fixture's row — the link
existed in the table and was invisible to the API. The fixture now checks that its row is in the
newest run for that occupation. This is the trap CLAUDE.md already warns about, reached from a
new direction.

## 17. Limitations

1. **E2 ranges are not directly calibrated.** E1 and E2 are the engine's own output, so their
   uncertainty is a truncation question — would more evidence move the score? — which requires
   re-running the engine over deliberately incomplete evidence. Not done here. Their ranges are
   conservative by construction, not measured.
2. **Band agreement is 78%, not 95%.** Roughly one estimate in five lands in a different risk
   band than the verified score would. That is the honest cost of the layer and the reason
   estimates are excluded from rankings.
3. **Worst-case error is large, and the cause is semantic.** Maximum leave-one-out exposure
   error is 28.6 points (Travel Agents). O\*NET relatedness means similar activities, skills and
   context — not similar *automatability*. Where those come apart the proxy is wrong in a way no
   dispersion measure detects, and widening ranges enough to cover it would make every estimate
   useless. See §6a.
4. **A proxy inherits its relatives' provisional inputs.** E3 estimates borrow from verified
   scores that themselves carry provisional replacement-risk factor models.
5. **Content run 4 covered all 1,016 occupations**, adding 3,670 related-occupation rows for
   verified identities beyond run 2's cohort-internal links. Verified pages' *visible* related
   lists are unchanged — the reader filters targets through the publication predicate — but the
   underlying rows are new. Verified by direct comparison: run 2's 6,470 rows are a strict
   subset of run 4's.
6. **Compare and Career Fit deliberately do not include estimates**, so 390 occupations are
   searchable and viewable but not comparable.

## 18. Upgrade path: estimated → verified

An estimate becomes a verified analysis when its underlying evidence clears the existing gates.
Nothing about the estimate carries over — the verified score is calculated from scratch by the
engine, and the estimate is not an input to it.

| Cohort | n | What unblocks it |
|---|---|---|
| E1 | 59 | 57 need the two provisional replacement-risk factor models validated; 1 (Credit Counselors) needs its flagged anomaly investigated; **1 (Software Developers) passes every evaluable launch gate today and needs only a Phase 5 scoring run to be promoted** |
| E3, no mappings | 15 | A task→capability mapping run |
| E2 | 293 | Part of the 311 for which zero mappable tasks remain — a source-data limit |
| SOC 55 | 15 | Nothing available; O\*NET publishes no ratings or relations |

When an occupation is promoted, its estimate stops being served automatically: the live-estimate
view excludes any identity holding a verified score. No cleanup step has to be remembered.

**The single best return on effort remains validating the two provisional factor models.** It
would move 57 occupations from estimated to verified — including Electricians, which already has
100% task coverage and 87.7 confidence — without a single new task mapping.
