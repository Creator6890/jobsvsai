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

## 2. Evidence hierarchy

Every tier is deterministic and reads only data already imported. **No tier uses the
occupation's title.** "Software Developer sounds automatable" is not evidence, and a plausible
number attached to no warrant is indistinguishable, to the reader, from a measured one.

| Tier | Evidence | n | Rendering |
|---|---|---|---|
| **E1** | Complete task evidence (coverage ≥ 80). The validated engine's own score, withheld from the verified cohort by a *publication* gate — provisional-input sensitivity or a flagged anomaly — not by missing evidence. | **58** | point |
| **E2** | Partial task evidence. The engine's score over coverage below 80. | **293** | point ≥70, range <70 |
| **E3** | No task evidence. Weighted average of verified O\*NET-related occupations, weighted by relatedness tier (Primary-Short 3, Primary-Long 2, Supplemental 1). | **39** | always a range |
| **E4** | Occupation-characteristic archetype | **0** | not built |

**E4 has no members and was deliberately not built.** The tier would apply to an occupation with
no verified relatives but with element ratings to build an archetype from. Cross-tabulating the
54 never-assessed staged occupations: 39 have verified relatives, 15 have neither relatives nor
element ratings, and **none** has element ratings without relatives. Building an unexercised
tier would mean shipping untested code and an uncalibrated method for zero occupations.

**The estimator never adjusts an engine score.** For E1 and E2 the number is the engine's own
output, unmodified; what varies with confidence is the label and whether a range is shown.
Nudging a validated output because we are less sure of it would produce a third quantity that
is neither the engine's answer nor an honest estimate. A test pins this.

## 3–4. Calibration and error statistics

The E3 proxy is the only tier that is an inference rather than a measurement, so it is the tier
that must be calibrated. **Leave-one-out against all 507 verified occupations**: each
occupation's own evidence is discarded and its score reconstructed from its verified relatives
alone, exactly as a staged occupation's would be.

| | MAE | median | p90 | p95 | max | band agreement |
|---|---|---|---|---|---|---|
| **AI Exposure** | 4.68 | **3.60** | **10.15** | 13.27 | 28.61 | 77.9% |
| **Replacement Risk** | 3.65 | **2.84** | **7.73** | 9.53 | 16.01 | 77.5% |

| Acceptance threshold | Target | Exposure | Replacement |
|---|---|---|---|
| Median absolute error | ≤ 8 | **3.60** ✅ | **2.84** ✅ |
| 90th percentile error | ≤ 15 | **10.15** ✅ | **7.73** ✅ |

Both metrics clear the thresholds with room, so **no tier was withheld for poor calibration**.
Calibration is re-measured on every run and stored on the run row, so a published estimate can
always be traced to the evidence that justified publishing it.

Error rises where relatives are sparse, which is what drives the confidence policy:

| Verified relatives | n | MAE (exposure) | p90 |
|---|---|---|---|
| 3–5 | 12 | 6.75 | 17.84 |
| 6–9 | 78 | 4.92 | 11.07 |
| 10+ | 415 | 4.58 | 9.98 |

**A limitation stated plainly:** E2 range widths are *inherited* from the E3 calibration as a
conservative proxy. They are not derived from a direct study of how an engine score at 55%
coverage differs from the same occupation's score at full coverage, because producing that
ground truth means re-running the scoring engine over truncated evidence — real work, not done
here. The E2 ranges should be read as "deliberately wide" rather than "measured".

## 5. Confidence policy

| Public label | Applies to | Rendering |
|---|---|---|
| Higher-confidence estimate | E1 | point (`~47`) |
| Moderate-confidence estimate | E2 coverage ≥ 70; E3 with ≥ 6 relatives | E2 point, E3 range |
| Low-confidence estimate | E2 coverage < 70; E3 with < 6 relatives | range |

**"Higher-confidence", never "High confidence."** The latter reads as a stronger version of a
verified score when it is a different kind of claim altogether.

166 of 390 estimates render as a range. All values are integers: rendering `72.43` for a number
whose p90 error is ten points asserts a precision the method does not have.

## 6. The staged 405

| Tier | Count |
|---|---|
| E1 | 58 |
| E2 | 293 |
| E3 | 39 |
| E4 | 0 |
| **Insufficient evidence** | **15** |
| | **405** |

The 15 are **every SOC 55 occupation** — Infantry, Special Forces, Air Crew Members, Artillery
and Missile Officers and the rest. O\*NET publishes no task ratings and no related-occupation
links for military occupations, so there is nothing to measure and nothing to borrow from. They
are not published, and no amount of method work changes that.

## 7. High-value occupations

| Occupation | Estimate | Tier | AI Exposure | Replacement Risk | Confidence | Evidence |
|---|---|---|---|---|---|---|
| **Electricians** | YES | E1 | **~47** | **~33** | Higher | Complete task evidence (100% coverage); withheld only by provisional-sensitivity |
| **Data Scientists** | YES | E3 | **66–86** | **63–79** | Moderate | Financial Quantitative Analysts, Operations Research Analysts, Statisticians, Bioinformatics Scientists |
| **Software Developers** | YES | E3 | **53–89** | **55–79** | Low | Verified relatives; page titled "Software Developer" |
| **Cashiers** | YES | E2 | **52–68** | **44–56** | Low | Partial task evidence (50.9% coverage) |
| **Data Entry Keyers** | YES | E2 | **59–75** | **55–67** | Low | Partial task evidence (64.6% coverage) |
| **Waiters and Waitresses** | YES | E2 | ~65 | ~49 | Moderate | Partial task evidence (71.5%) |
| **Bakers** | YES | E2 | ~64 | ~50 | Moderate | Partial task evidence (75.6%) |
| **Exercise Trainers** | YES | E2 | ~60 | ~45 | Moderate | Partial task evidence (79.3%) |
| **Project Management Specialists** | YES | E3 | **58–78** | **51–67** | Moderate | Verified relatives |
| **Web and Digital Interface Designers** | YES | E3 | **62–82** | **59–75** | Moderate | Verified relatives; page titled "UX Researcher" |

**All ten now have a published estimate.** Two render under pre-existing consumer-facing titles
(Software Developer, UX Researcher) because those editorial pages already existed and an
editorial decision already taken is not revisited; the canonical identity remains the O\*NET
SOC code.

Software Developers is worth a note: it holds 17 fully-rated, fully-mapped tasks, but the
mappings come from the Phase 4A pilot mapper whose provenance declares
`activationAllowed: false`. Those mappings are **not** used. Its estimate is E3, drawn from
relatives, and its low confidence and wide range reflect exactly that.

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

New coverage: the four database guards, per-tier estimator behaviour, reproducibility, integer
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

1. **E2 ranges are not directly calibrated.** See §3–4. They are conservative by construction,
   not measured.
2. **Band agreement is 78%, not 95%.** Roughly one estimate in five lands in a different risk
   band than the verified score would. That is the honest cost of the layer and the reason
   estimates are excluded from rankings.
3. **Worst-case error is large.** Maximum leave-one-out exposure error is 28.6 points. Ranges
   communicate typical uncertainty, not worst case.
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
| E1 | 58 | 57 need the two provisional replacement-risk factor models validated; 1 (Credit Counselors) needs its flagged anomaly investigated |
| E3 with task evidence | 15 | A production-grade task→capability mapping run |
| E2 | 293 | Part of the 311 for which zero mappable tasks remain — a source-data limit |
| SOC 55 | 15 | Nothing available; O\*NET publishes no ratings or relations |

When an occupation is promoted, its estimate stops being served automatically: the live-estimate
view excludes any identity holding a verified score. No cleanup step has to be remembered.

**The single best return on effort remains validating the two provisional factor models.** It
would move 57 occupations from estimated to verified — including Electricians, which already has
100% task coverage and 87.7 confidence — without a single new task mapping.
