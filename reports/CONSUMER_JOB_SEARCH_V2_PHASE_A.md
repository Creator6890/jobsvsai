# Consumer Job Search V2 — Phase A

**Date:** 2026-08-25 · **Scope:** search only · **Not deployed, not merged**

The public cohort is unchanged at **507**. No occupation was promoted, no score written, no
publication gate touched, and the provisional-sensitivity policy is exactly as it was.

Search now answers one of four things instead of always returning a row. The failure this
replaces was a single shape — *the best of a bad field, returned as if it were an answer*.

---

## Search architecture before

`app/repositories/occupations.py`, one statement:

```sql
tokens      = query.lower().split()
search_text = "lower(o.title || ' ' || o.search_aliases)"
... AND ((<search_text LIKE '%tok%' AND ...>) OR similarity(search_text, :query) > 0.18)
ORDER BY similarity(search_text, :query) DESC, o.title
```

`search_aliases` averages 1,269 characters and reaches 18,368. Trigram similarity divides
shared trigrams by their union, so **the more alternate titles an occupation carried, the
lower it ranked**. Measured live, `data entry operator` returned one row scoring
`similarity = 0.0254` — below the 0.18 threshold — admitted only by the unanchored `LIKE`
clause finding three tokens somewhere inside five kilobytes of text. There was no exact-match
tier: a curated alias, a canonical title and an accidental substring competed on one number.

## Search architecture after

`app/repositories/occupation_search.py` (`consumer-search-v2`). Exact and prefix tiers stop early — an exact hit needs no corroboration. The three weak tiers
are gathered together, because each caps its candidate list and stopping at the first non-empty
weak tier can discard the row a later tier would have found.

| Tier | Floor | Matched against |
|---|---|---|
| Curated consumer alias, exact | 1000 + conf×40 | `consumer_aliases` |
| Canonical title, exact | 950 | canonical title |
| Curated ambiguous parent | 920 + conf×40 | `consumer_aliases` |
| O*NET alternate / abbreviation, exact | 900 | each title **individually** |
| Title prefix | 800 − overshoot | each title individually |
| Token prefix (`soft eng` → `software engineer`) | 700 | each title individually |
| All tokens in one term | 650 | each title individually |
| Fuzzy (trigram) | 640 | each title individually |

Three properties do the work:

**Terms are matched individually.** The 57,543 alternate titles become 57,543 comparable
candidates instead of 1,016 blobs, so alias richness can only help.

**Fuzzy can never answer alone.** `FUZZY_CEILING = 640` sits below `MIN_RELIABLE = 645`. A
lexical near-miss may corroborate a match; it can never constitute one. This single inequality
is what stops `ml engineer → Search Marketing Strategists`.

**Confidence is folded into the tier floor.** Within one tier a 0.85 mapping outranks a 0.60
one — without it `martial arts instructor` ranked Coaches and Scouts level with Exercise
Trainers and broke the tie on title length, which is meaningless.

### Four outcomes

| Status | Meaning | When |
|---|---|---|
| `public_matches` | here is the analysis | strong evidence for an occupation we publish |
| `occupation_not_available` | we know what you mean; we have not analysed it yet | strong evidence for an occupation we do not publish — **or** a tie in which every contender is unpublished |
| `ambiguous` | which of these did you mean? | two or more occupations tied on equal semantic evidence, at least one publishable |
| `no_reliable_match` | we cannot answer this reliably | nothing clears the relevance floor, or a weak-tier tie an unpublished candidate matches at least as well |

**Publication status never breaks a semantic tie.** Intent is resolved over every candidate
first; publication decides only what may be shown afterwards.

A staged occupation is **indexed so it can be recognised**, and named in the response so we can
say we do not analyse it yet. It never carries a score, a slug, a snapshot or a block reason —
`TermMatch` has nowhere to put one, and a test asserts that.

## Schema / migration

`migrations/034_consumer_search_v2.sql`. **Additive only.** `occupations.search_aliases` is
left in place, so rollback is a code change rather than a data restore.

| Object | Rows |
|---|---|
| `consumer_aliases` (table) | 135 mappings across 80 terms |
| `occupation_search_terms` (materialised view) | **62,681** |
| — canonical | 1,016 |
| — alternate | 57,543 |
| — abbreviation | 3,987 |
| — consumer alias / parent | 102 / 33 |

Indexes: btree `text_pattern_ops` on `normalized_term` (exact and prefix), GIN `gin_trgm_ops`
(fuzzy only), unique index so `REFRESH … CONCURRENTLY` is available.

Two decisions worth stating. **Publication status is deliberately not materialised** — it
changes on promotion, and a stale view claiming a staged occupation is public would route a
user to a page that does not exist; search joins `occupation_publications` live. And the view
covers **all 1,016 occupations**, because a staged occupation still has to be recognisable.

`SELECT DISTINCT` wraps the union: O*NET repeats a short title across several alternate-title
rows for the same occupation (`CNC Lathe Operator` on multiple rows of 51-4012.00), which broke
the unique index on the first attempt.

Verified with `EXPLAIN`: exact is `Index Scan using occupation_search_terms_normalized_idx`;
fuzzy is `Bitmap Index Scan on occupation_search_terms_trgm_idx`. **No sequential scan.**

## Alternate-title usage

Before: present only as blob text, where they lowered the ranking of the occupations carrying
them. After: **27,993 alternate titles for the public 507 are individually matchable**, and the
27,993 belonging to non-public occupations make those occupations recognisable rather than
invisible.

The curated catalogue is deliberately small — 80 terms — because O*NET already supplies the
bulk. Curated entries exist only where O*NET has nothing (`swe`, `ml engineer`, `soc analyst`)
or the everyday word differs from the canonical title (`data entry operator`).

Normalisation adds initialism expansion (`ml → machine learning`, `pen tester → penetration
tester`, `swe → software engineer`, `ux`, `ui`, `seo`, `hr`, `it`) and crude singular/plural
variants. The plural handling mattered more than expected: **O*NET titles are plural and people
type the singular**, so `medical assistant` matched no term exactly and fell through to token
matching, which reached Health Specialties Teachers — the exact failure mode this design
exists to prevent. The literal query is always tried first, so `it support` still matches the
literal O*NET term "IT Support".

## Audit finding — benchmark correctness must key on occupation identity, not display text

Discovered while scoring the final benchmark, and general enough to outlive this phase.

**An occupation's editorial display title may differ from its canonical O\*NET title.** The
`occupations` table holds consumer-facing page titles; `onet_occupations` holds the taxonomy's
own. They are frequently not the same string:

| Query | Canonical O\*NET title | Editorial page title |
|---|---|---|
| `auditor` | Accountants and Auditors | **Accountant** |

A benchmark that judges correctness by comparing returned *titles* against expected *titles*
therefore marks a correct answer as a failure. Scoring band A on titles produced 78.3% top-1
and eleven "misleading" results; scoring the identical run on SOC codes produced **91.3% and
two**. Nine of those eleven were scoring artefacts, not search defects — `auditor` among them,
where search had returned exactly the right occupation.

**Rule: benchmark correctness is keyed on canonical occupation identity — the SOC/O\*NET
code — never on display text.** The acceptance set for a query is every published occupation
the fixture judged a defensible reading of it (`public_candidates` ∪ `intended`), compared by
`soc`. Display titles are for humans and may be re-edited at any time without a migration; SOC
codes are the identity the whole scoring pipeline already keys on. Any future search,
ranking or coverage benchmark should adopt the same rule, and a benchmark that reports
suspiciously many near-miss failures should be checked for this before its results are
believed.

## Benchmark

The single A/B/C/D/F metric conflated search relevance with publication coverage, so it is
replaced by three. `backend/tests/fixtures/consumer_search_benchmark.json`,
`consumer-search-benchmark-v1`, 187 queries, every judgement inspectable.

Banding was corrected twice during this work, and both corrections were to the *fixture*, not
the search:

1. Banding on "any public occupation whose title contains an expected substring" counted
   `carpenter` as publicly answerable because **Cabinetmakers and Bench Carpenters** contains
   "Carpenters" — while the occupation a person means, Carpenters, is staged. Now resolved
   exact-title-first.
2. `", All Other"` residual SOC buckets are never what anyone types; where a published specific
   sibling exists, that is the intended answer. `psychologist` returning School Psychologists
   and Clinical and Counseling Psychologists is correct, not a substitution.

### A. Public-answerable accuracy (n = 92)

| Metric | Result | Target |
|---|---|---|
| top-1 | **91.3%** (84/92) | — |
| **top-3** | **95.7%** (88/92) | ≥ 90% ✅ |
| useful | 95.7% | — |
| **misleading** | **2.2%** (2/92) | ≤ 3% ✅ |

Scored on **SOC code**, not title: the acceptance set for a query is every published
occupation the fixture judged a defensible reading of it (`public_candidates` ∪ `intended`).
Titles are unusable as keys because an editorial page may be titled "Accountant" where O\*NET
says "Accountants and Auditors" — matching on titles scored `auditor` as a failure when it had
returned exactly the right occupation.

### B. Non-public detection (n = 95)

| Metric | Result | Target |
|---|---|---|
| **correctly detects unavailable** | **97.9%** (93/95) | ≥ 95% ✅ |
| **false substitution** | **2.1%** (2/95) | ≤ 3% ✅ |
| fell through to no-match | 0.0% | — |

A query counts as detected when it returns `occupation_not_available`, **or** when it returns
`ambiguous` and the intended occupation is itself among the choices shown as unavailable.
Naming the right occupation and saying we cannot analyse it is the behaviour the band is
testing; which of the two envelopes carries it is a presentation detail.

### C. True taxonomy gap (n = 0)

No benchmark query lacks a defensible imported occupation. O*NET has an occupation for every
ordinary job tested, including martial arts instruction. Nonsense queries were verified
separately to return `no_reliable_match`.

### False substitution — the one target missed

**2 of 95**, down from 4 once semantic ties stopped being broken by publication state.
`financial analyst` and `merchandiser` now return `ambiguous` with the intended staged
occupation named among the choices, which is the honest outcome; these two remain:

| Query | Intended (staged) | Returned (public) |
|---|---|---|
| `sales rep` | Sales Representatives, Wholesale and Manufacturing, Technical and Scientific Products | Solar Sales Representatives and Assessors |
| `store manager` | First-Line Supervisors of Retail Sales Workers | General and Operations Managers |

Both match a published occupation on a genuine exact O\*NET alternate title, so each is a
defensible answer rather than a lexical accident — but each is also a narrower or adjacent
occupation than the one meant. Closing the gap properly means publishing the intended
occupations, not tightening search; both are in the coverage list from the audit.

The two **misleading** results in band A have the same shape:

| Query | Fixture's intended | Returned |
|---|---|---|
| `teacher` | Economics Teachers, Postsecondary | Elementary / Secondary / Kindergarten School Teachers |
| `production operator` | Paper Goods Machine Setters, Operators, and Tenders | Chemical Plant and System Operators, Mixing and Blending Machine Setters |

Both are cases where the fixture pinned one arbitrary member of a large family. `teacher`
returning school teachers is not a defect; it is counted against the search anyway rather than
edited away, because the fixture has already been corrected twice and a third correction that
happens to raise the score is exactly the move this report should not make.

## Critical query results

**21 of 21 pass.** Each row records the tier the answer came from and the score it carried, so
a result can be traced to its evidence rather than taken on trust. Tier floors: curated alias
1000 + confidence×40, canonical 950, curated parent 920 + confidence×40, alternate/abbreviation
900, prefix 800, token-prefix 700, token 650, fuzzy 640.

| Query | Status | Canonical occupation(s) | Behaviour | Tier / score |
|---|---|---|---|---|
| `teacher` | `public_matches` | Elementary School Teachers, Secondary School Teachers, Kindergarten Teachers | public | consumer_parent / 954 |
| `ML engineer` | `occupation_not_available` | Data Scientists | unavailable | consumer_alias / 1034 |
| `machine learning engineer` | `occupation_not_available` | Data Scientists | unavailable | consumer_alias / 1034 |
| `data scientist` | `occupation_not_available` | Data Scientists | unavailable | canonical / 950 |
| `data analyst` | `public_matches` | Statisticians, Management Analysts, Business Intelligence Analysts | public | consumer_alias / 1029 |
| `data entry operator` | `occupation_not_available` | Data Entry Keyers | unavailable | consumer_alias / 1038 |
| `pen tester` | `occupation_not_available` | Cybersecurity Analyst | unavailable | consumer_alias / 1038 |
| `ethical hacker` | `occupation_not_available` | Cybersecurity Analyst | unavailable | consumer_alias / 1037 |
| `martial arts instructor` | `occupation_not_available` | Exercise Trainers and Group Fitness Instructors | unavailable | consumer_alias / 1034 |
| `software developer` | `occupation_not_available` | Software Developer | unavailable | canonical / 950 |
| `software engineer` | `occupation_not_available` | Software Developer | unavailable | consumer_alias / 1039 |
| `lawyer` | `occupation_not_available` | Lawyers | unavailable | canonical / 950 |
| `electrician` | `occupation_not_available` | Electricians | unavailable | canonical / 950 |
| `cashier` | `occupation_not_available` | Cashiers | unavailable | canonical / 950 |
| `waiter` | `occupation_not_available` | Waiters and Waitresses | unavailable | alternate / 900 |
| `doctor` | `public_matches` | Family Medicine Physicians, General Internal Medicine Physicians, Psychiatrists | public | consumer_parent / 954 |
| `nurse` | `public_matches` | Registered Nurses, Acute Care Nurses, Critical Care Nurses | public | consumer_parent / 957 |
| `driver` | `public_matches` | Heavy and Tractor-Trailer Truck Drivers, Driver/Sales Workers, Couriers and Messengers | public | consumer_parent / 952 |
| `salesman` | `occupation_not_available` | Retail Salespersons | unavailable | consumer_alias / 1030 |
| `customer support` | `public_matches` | Customer Service Representatives | public | consumer_alias / 1037 |
| **`soft eng`** | **`no_reliable_match`** | — | no reliable match | — |

Each row additionally asserts that the specific wrong answer V1 gave is absent: `ml engineer`
must not return Search Marketing Strategists, `data entry operator` must not return First-Line
Supervisors of Office and Administrative Support Workers, `pen tester` and `ethical hacker`
must not return Non-Destructive Testing Specialists, `cashier` must not return Tellers, and
`soft eng` must not return Etchers and Engravers. All twenty-one assertions hold.

Three patterns are visible in the tier column and worth naming:

* **Curated aliases outrank everything**, which is the point — an editorial statement about
  what a consumer means beats an incidental lexical hit. `martial arts instructor` returned
  nothing at all before V2.
* **Canonical titles at 950 settle the hard collisions.** `cashier`, `data scientist`,
  `software developer`, `lawyer` and `electrician` all win outright at 950 over alternate-title
  claimants at 900. No tie, so no tie-break, so publication is never consulted.
* **`soft eng` is the deliberate refusal.** Nothing clears the reliability floor, and the
  honest answer is to say so.

`data analyst` is the one broad query that returns public results, and deliberately: the
curated catalogue maps it to Data Scientists (staged, 0.80) **and** to Statisticians (public,
0.72). A curated mapping is an editorial statement that an interpretation is acceptable, so a
curated *published* mapping outranks an unpublished one. An accidental lexical hit gets no such
standing — the rule checks term type, not merely score.

### `cashier` — resolved by tier, not by publication

`cashier` was the query that first exposed V1 breaking ties by title length. Its resolution is
now a plain consequence of the tier floors, and worth writing down because it is the clearest
example of the rule:

| Tier | Priority | Term | Occupation | Publication |
|---|---|---|---|---|
| **canonical** | **950** | Cashiers | **Cashiers** | staged |
| alternate | 900 | Cashier | Cashiers | staged |
| alternate | 900 | Cashier | Gambling Change Persons and Booth Cashiers | staged |
| alternate | 900 | Cashier | Tellers | staged |
| alternate | 900 | Cashier | Office and Administrative Support Workers, All Other | review_required |

The singular query reaches the plural canonical title through `_plural_variants`, and an exact
**canonical title match scores 950 against a four-way alternate-title collision at 900**. There
is no tie, so no tie-break runs and publication is never consulted. Cashiers is staged, so the
answer is `occupation_not_available` naming Cashiers — not Tellers, and not a published
stand-in. Had publication been allowed to weigh in, Tellers (public) would have won on a
strictly weaker piece of evidence.

## Performance

Measured over the 187-query benchmark against the real SQL implementation:

| Layer | p50 | p95 | p99 | max |
|---|---|---|---|---|
| **DB resolver** (`resolve`, warmed) | **0.3 ms** | **0.5 ms** | 16.4 ms | 29.6 ms |
| **API** `/api/v1/occupations/search/resolve` | **5.2 ms** | **19.9 ms** | 32.9 ms | 42.9 ms |
| **Next.js proxy** `/api/occupations/search/resolve` | 8.3 ms | 22.2 ms | 35.3 ms | 47.2 ms |

0 non-200 responses across all three. The API figures include curl process spawn and localhost
HTTP; the DB figure is the resolver alone. Three orders of magnitude below the audit's Python prototype (238 ms p50), which was a full
linear scan. **No LLM call, no network call, fully deterministic.** The p99 tail is the fuzzy
tier; ~80% of queries never reach it.

## UI states

`OccupationSearch.tsx` calls `/api/occupations/search/resolve`. Smallest change that carries
the new contract; no redesign.

- **public match** — unchanged behaviour.
- **`occupation_not_available`** — the matched title, "We don't have a JobsVsAI analysis for
  this occupation yet", and optionally related published careers as links. **No AI Exposure
  and no Replacement Risk are rendered, because no approved public score exists.** Styled
  deliberately unlike a result card so it cannot read as a score.
- **`ambiguous`** — "Which role best matches what you do?" and the choices. Available choices
  link to their page; unavailable ones read "— analysis not available yet" and carry no link,
  because there is no page to link to. An unavailable interpretation is **listed rather than
  dropped**: dropping it would silently resolve the ambiguity in favour of whatever happens to
  be published.
- **`no_reliable_match`** — the existing message.

The typeahead itself gained a keyboard layer in this phase (ARIA combobox: ArrowDown/ArrowUp
with wrap, Escape to dismiss without clearing the query, Tab to leave, Enter to take a
highlight). It had none before — see Gate 11. That is a presentation-layer change only; no
ranking, scoring or publication code was touched.

## Privacy

Unchanged and preserved: **raw search queries are never sent to GA4.** The unavailable state
fires the existing `occupation_search_used` event with `query_result_count: 0` and no query
text, no unpublished job title, and no freeform string. `related_public_results` carries only
published slugs and titles.

## API contract

`GET /occupations/search` is **unchanged in shape** — still a bare `list[Occupation]`, so
existing clients are unaffected. It now ranks through V2, and returns an empty list when the
query resolves to an unpublished occupation.

`GET /occupations/search/resolve` is new and returns `SearchResponse`: `queryStatus`,
`results`, `matchedTitle`, `canonicalTitle`, `publicationStatus`, `isDisambiguation`,
`relatedPublicResults`, `choices`. `publicationStatus` is the coarse lifecycle state only —
never a coverage figure, confidence, triage finding or blocking code.

`queryStatus` is one of the four outcomes above, and **both endpoints reach it through the same
`occupation_search.resolve`** — there is no second ranking implementation to drift from the
first, and a test asserts the legacy wrapper delegates and that the two agree on ordering. The
legacy endpoint expresses only what its bare-list shape can: results for `public_matches` and
`ambiguous`, `[]` for the other two.

**No unpublished score can cross this boundary.** `TermMatch` carries no score field at all, so
the repository has nothing to leak; `SearchResponse` has no `provenance`; an unavailable
`AmbiguousChoice` carries no slug, because there is no page to link to. The only publication
signal that crosses is the coarse `publicationStatus`, reduced further to a boolean `available`
on each choice. Verified in the browser: no panel in any of the four states renders an AI
Exposure or Replacement Risk number, and none contains the strings `staged`, `review_required`,
`provisional`, `snapshot`, `coverage`, `triage`, `not_available` or `public_matches`.

## Rollback

1. **Code only** — revert the commit. `occupations.search_aliases` is untouched and the old
   ranking returns with it. No data restore.
2. **Schema** — `DROP MATERIALIZED VIEW occupation_search_terms; DROP TABLE consumer_aliases;`
   Nothing else references them; no other table was altered.
3. **Frontend** — reverts with the same commit; `/api/occupations/search` still exists.

Migration 034 is **not applied** to dev or production (`034 applied to dev? 0`). The search
tests skip cleanly when it is absent, so a database without it does not produce false failures.

## Provisional count reconciliation

Three numbers appeared in audit discussion. Resolved against triage run 2:

| Count | Meaning | Correct? |
|---|---|---|
| **106** | occupations carrying the `provisional_input_sensitivity` blocker | **correct** |
| 47 | of those, *also* blocked by coverage, confidence or review-readiness | correct |
| **59** | blocked **only** by sensitivity, all genuinely meeting coverage ≥ 80 and confidence ≥ 75 | **correct** |
| 68 | — | **my error** |
| 60 | — | **my error** |

**68 and 60 were artefacts of my own rounding.** When dumping triage results I rounded
`weighted_task_coverage` and `confidence` to integers, so occupations at 79.5–79.99 rounded up
to 80 and appeared to meet a gate they actually fail. Filtering on the unrounded values gives
59; filtering on the rounded values gives 68, of which 60 carried the sensitivity blocker.

**106 and 59 match what CLAUDE.md already records.** No runtime behaviour depends on any of
these numbers, and the provisional-sensitivity policy is unchanged.

## Tests

| Suite | Result |
|---|---|
| Backend `./scripts/run-tests.sh` | **570 passed, 1 skipped, 0 failed** |
| Frontend `npm test` | **67 passed, 0 failed** |
| `npm run lint` | clean |
| `npm run build` | succeeds |

New tests cover normalisation agreeing with the migration's own SQL expression, initialism and
plural handling, the publication boundary (unpublished occupations named but never returned,
no score field anywhere on the result type), the stop rule, strict tier ordering, the
production substitutions asserted absent by name, broad-family disambiguation, aggregate
quality gates, and the migration runner (`test_migration_runner.py`: guarded array expansion,
an executable `set -u` proof, per-migration `BEGIN`/`COMMIT` balance, 034's declared objects,
idempotency, checksum drift, and the failure path leaving no history row).

## Risks

**Normalisation drift.** Query-time `normalise()` and the migration's `regexp_replace` must
agree; if they diverge, exact matching silently degrades to fuzzy and nothing fails loudly. A
test pins the pairing, but it compares against hardcoded expectations rather than executing the
SQL, so a migration edit could still slip past.

**Materialised view staleness.** New O*NET imports and alias edits need
`REFRESH MATERIALIZED VIEW CONCURRENTLY occupation_search_terms`. Publication status is joined
live, so promotion does *not* require a refresh — the case that would have mattered most.

**Curated mappings are judgements.** `product manager → Project Management Specialists` at 0.75
is an opinion. Confidence and `notes` are stored so mappings are reviewable, and low-confidence
matches should read as "closest occupation" rather than an identity claim.

**Benchmark bias.** 187 queries by one author, UK/US-English weighted. A good relative
instrument, not an absolute measure of consumer behaviour.

**The gates are not yet wired to CI scope.** They run in the normal suite; they should be
scoped to changes touching search, the alias table or the term view rather than blocking
unrelated builds.

---

## Gate 1 — exact term collisions

| Measure | Count |
|---|---|
| Distinct high-priority terms (priority ≥ 900) | 50,886 |
| **Terms mapping to more than one occupation** | **7,581** |
| Of those, tied at identical priority | **7,526** |

That is a large surface, and V1 settled every one of them by title length and row order. A tie
is now broken only by *canonical-title evidence* — how much of the query the occupation's own
title accounts for. "Cashier" is an exact alternate title for both Cashiers and Tellers; only
one is *called* Cashiers, and that is a real reason. Title length is not.

When evidence cannot break the tie, search returns **`ambiguous`** with the choices rather than
guessing. On the benchmark this fires for **21 of 187** queries, every one of them genuinely
multi-occupation: `financial analyst`, `secretary`, `project manager`, `physician`,
`psychologist`, `music teacher`, `sales rep`, `merchandiser`, `buyer`, `architect`, `painter`,
`cnc operator`, `truck driver`, `forklift operator`, `pilot`, `cook`, `police officer`,
`social worker`, `production operator`, `quality inspector`, `assembler`.

The count rose from 7 to 21 when publication stopped breaking semantic ties. That is the
intended direction: the 14 additional queries were previously resolved *silently* in favour of
whichever tied interpretation happened to be published, which is precisely the substitution
this design exists to prevent.

Two constraints on when ambiguity may fire, both learned from defects during this work:

* **Only at exact tiers.** `soft eng` briefly returned `ambiguous` because Software Developer
  tied with *Etchers and Engravers* (via "Soft Metal Hand Engraver") on a token-prefix scrape.
  Offering that as a decision is worse than ranking it, so ambiguity now requires
  `score >= STRONG_MATCH`.
* **Publication may not break a semantic tie.** The tie check now runs *before* the
  publication decision, over every candidate regardless of status. The reverse order — which
  this report carried in an earlier revision — let a published occupation win a tie it had no
  stronger evidence for. The rule is now: resolve what the query *means* first; only once
  intent is settled does publication decide what can be *shown*. Where every tied contender is
  unavailable, the result is `occupation_not_available`, because a chooser with nothing
  choosable is not a choice; where some are available it is `ambiguous`, and the unavailable
  interpretations stay in the list rather than being dropped.

## Gate 2 — the `data analyst` mapping, justified

`data analyst` is the one critical query that returns published results while its
highest-confidence interpretation is unpublished. The catalogue records three mappings:

| SOC | Occupation | Type | Confidence | Status |
|---|---|---|---|---|
| 15-2051.00 | Data Scientists | COMMON_TITLE | 0.80 | **staged** |
| 15-2041.00 | Statisticians | COMMON_TITLE | 0.72 | public |
| 13-1111.00 | Management Analysts | COMMON_TITLE | 0.65 | public |

The rule is **not** "prefer a public occupation". It is that a *curated* mapping is an editorial
statement that an interpretation is acceptable, so a curated published mapping outranks an
unpublished one — and the code checks `term_type in ("consumer_alias", "consumer_parent")`, not
merely publication state. An accidental lexical hit gets no such standing.

Why Statisticians is defensible: O*NET's Statisticians covers "collect, analyze and interpret
numerical data" and carries *Data Analyst* among its own alternate titles, so this is O*NET's
mapping rather than an invention. Business Intelligence Analysts (public) also appears in the
results, one tier lower, via its own exact alternate title.

Alternatives considered and rejected: **Data Scientists** is the strongest interpretation and is
staged, which is why the query is also a coverage finding, not only a search one.
**Operations Research Analysts** is narrower — optimisation and modelling rather than reporting
analysis. **Business Intelligence Analysts** is a good match and does surface; it is not
promoted to first because the curated confidence for Statisticians is higher and BI Analysts
reaches the list on its own O*NET evidence anyway.

This was not tuned to pass the benchmark: the mapping predates the fixture, and the fixture was
re-banded to *follow* the catalogue rather than the reverse.

## Gate 7 — false positive review

Every remaining misleading or substituting result, classified by cause.

**Band A misleading — 2 of 92 (2.2%).** `teacher` and `production operator`. Neither is a
lexical accident: both are broad terms where the fixture pinned one arbitrary member of a large
occupational family (Economics Teachers, Postsecondary; Paper Goods Machine Setters) and search
returned different, equally real members of it. Counted against the search anyway.

**Band B false substitution — 2 of 95 (2.1%), inside the 3% target.**

| Query | Intended (staged) | Returned (public) | Shared exact term |
|---|---|---|---|
| `sales rep` | Sales Representatives, Wholesale and Manufacturing, Technical and Scientific Products | Solar Sales Representatives and Assessors | "Sales Rep" |
| `store manager` | First-Line Supervisors of Retail Sales Workers | General and Operations Managers | "Store Manager" |

Cause: **alternate-title collision between a published and an unpublished occupation carrying
the identical exact O\*NET term at identical priority** — and, critically, where the *canonical
title evidence differs*. In both rows the published occupation's own canonical title accounts
for more of the query than the staged one's does, so the tie-break resolves on evidence and
never reaches the publication question at all.

An earlier revision of this report recorded 4 of 95 here and argued that "preferring the
published occupation on equal exact evidence is defensible". **That argument was wrong and has
been withdrawn.** Publication status may not break a semantic tie: it is a fact about what we
have finished analysing, not evidence about what the user meant. Once the tie-break was moved
ahead of the publication decision, `financial analyst` and `merchandiser` stopped resolving to
Financial Quantitative Analysts and Online Merchants and began returning `ambiguous` with the
intended staged occupation named among the choices — which is what they should always have
done. The band improved from 4.2% to 2.1% as a consequence of the correctness fix, not of any
tuning.

The two that remain are not ties, so no policy change reaches them. **Closing that gap properly
means publishing the intended occupations**; both are already in the audit's coverage list.

## Gate 8 — performance

| Tier | p50 | p95 | p99 | max |
|---|---|---|---|---|
| **DB** (`resolve`, 187 queries, warmed) | **0.3 ms** | **0.5 ms** | 16.4 ms | 29.6 ms |
| **API** (HTTP direct, 187 queries) | **5.2 ms** | **19.9 ms** | 32.9 ms | 42.9 ms |
| **API** (through the Next.js proxy route) | 8.3 ms | 22.2 ms | 35.3 ms | 47.2 ms |

0 non-200 responses. `EXPLAIN` confirms exact tiers use
`occupation_search_terms_normalized_idx` and fuzzy uses `occupation_search_terms_trgm_idx` — no
sequential scan. **No LLM call at query time.** The p99 tail is the fuzzy tier; roughly 80% of
queries never reach it, which is why p95 and p99 differ by a factor of thirty.

## Gate 9 — API compatibility

Every caller was enumerated from the source, not assumed:

| Caller | Endpoint | Status |
|---|---|---|
| `frontend/src/components/OccupationSearch.tsx` | `/search/resolve` | migrated |
| `frontend/src/app/api/occupations/search/resolve/route.ts` | `/search/resolve` | new proxy |
| `frontend/src/lib/api.ts` → `resolveOccupationSearch` | `/search/resolve` | new |
| `frontend/src/app/api/occupations/search/route.ts` | `/search` | retained, unchanged |
| `frontend/src/lib/api.ts` → `searchOccupations` | `/search` | retained, unchanged |
| `backend/tests/test_integration.py` (2 call sites) | `/search` | retained, passing |

Both endpoints call the **same** `occupation_search.resolve`, so they cannot drift into two
implementations; a test asserts the legacy wrapper delegates and that both agree on ordering.

`/occupations/search` keeps its bare-list shape. It returns results for `public_matches` **and**
`ambiguous` — the old shape simply cannot express "these are alternatives" — and returns `[]`
when the query resolves to an unpublished occupation, because it has no way to say so. Every
one of the four statuses is handled explicitly in all four layers (repository, API, `lib/api`
types, component state); there is no branch where `ambiguous` degrades into an empty state.

The response schema itself is the boundary: `SearchResponse` has no `provenance` field, no
score, and no slug on an unavailable choice. `publication_status` is the only lifecycle signal
that crosses, and `AmbiguousChoice` reduces even that to a boolean `available`.

**A bug this gate caught:** the endpoint function `occupation_search` shadowed the module import
of the same name, so `/search/resolve` returned 500 for every request. Repository tests passed
throughout because they bypass the API. Fixed by aliasing the import; browser QA is what found
it.

## Gate 10 — homepage UX states

Verified in a real browser against the running stack, reading the live DOM.

| State | Query | Result |
|---|---|---|
| **A public match** | `nurse` | **PASS** — 3 suggestions; selecting one shows Acute Care Nurses, AI Exposure 54/100, Replacement Risk 48/100, link `/jobs/acute-care-nurses` |
| **B non-public** | `software engineer` | **PASS** — see below |
| **C ambiguous** | `psychologist` | **PASS** — chooser rendered, all three choices linked |
| **D no reliable match** | `zzqx` | **PASS** — "No matching occupation found. Try another title or a broader term." |
| **E recovery** | `zzqx` → `electrician` | **PASS** — no-match replaced by the unavailable panel for Electricians |

State B, read from the live DOM:

```
software engineer
We don't have a JobsVsAI analysis for this occupation yet (Software Developer).
Related careers we can analyse today:
  Computer Systems Analysts · Computer Programmers ·
  Data Warehousing Specialists · Network and Computer Systems Administrators
```

State C, read from the live DOM:

```
Psychologist
Which role best matches what you do?
  School Psychologists · Clinical and Counseling Psychologists ·
  Industrial-Organizational Psychologists
```

Each panel was scanned for the internal vocabulary — `staged`, `review_required`,
`provisional`, `snapshot`, `coverage`, `triage`, `not_available`, `public_matches`. **Zero
matches in every state.** No AI Exposure or Replacement Risk number appears on an unavailable
or ambiguous panel.

Mobile (360×780) re-checked after the markup change: no horizontal overflow
(`scrollWidth == innerWidth == 360`), the list spans 10px–350px inside the viewport, all three
options render.

## Gate 11 — keyboard UX

**An earlier revision of this report said this component had no dropdown to navigate. That was
wrong** — `.autocomplete` has always rendered a list of `<button>` suggestions. What it lacked
was any keyboard route to them: the list was reachable by mouse and by Tab, and ArrowDown,
ArrowUp and Escape did nothing at all. Confirmed in-browser before the fix: pressing ArrowDown
left focus in the input with no `aria-activedescendant`, and Escape left the overlay open.

Phase A now implements the ARIA combobox pattern. The input carries `role="combobox"`,
`aria-expanded`, `aria-controls`, `aria-autocomplete="list"` and `aria-activedescendant`; the
list is `role="listbox"` with presentational `<li>` wrappers so it owns the `role="option"`
buttons directly; options are `tabIndex={-1}` because the pattern keeps focus in the input and
moves the active descendant instead.

Verified in a real browser, reading the live DOM after each keystroke:

| Interaction | Result |
|---|---|
| type `nurse` | 3 options, `aria-expanded="true"`, nothing highlighted |
| **ArrowDown** ×1 | `occupation-option-0` — Registered Nurses |
| ArrowDown ×3 | `occupation-option-2` — Critical Care Nurses |
| ArrowDown ×4 | wraps to `occupation-option-0` |
| **ArrowUp** | wraps to `occupation-option-2` |
| **Escape** | `aria-expanded="false"`, highlight cleared, **query text preserved** |
| continued typing | list re-opens (`nurse pract` → 1 option); dismissal is not sticky |
| **Tab** | list closes, focus moves to "Check my job" — no Tab-trap through options |
| **Enter** on a highlight | selects Acute Care Nurses, fills the input, closes the list |
| **mouse** click | unchanged; hover also moves the highlight, so the two modes agree |
| submit | result card, correct scores, correct `/jobs/…` link |

Two deliberate choices. `activeIndex` starts at −1 rather than 0, so **Enter with nothing
highlighted submits what the user typed** instead of silently choosing a suggestion they never
looked at. And Escape closes the overlay without clearing the query, because erasing someone's
typing when they asked for the overlay to go away is a hostile reading of the key.

One thing could not be exercised: **Enter-to-submit through the harness.** Its synthetic key
events carry `code:""` and `which:0`, so the browser performs no default actions and implicit
form submission never fires. The same `analyze` path was verified through the submit button
instead. Enter-to-submit is unchanged from before this work.

## Gate 13 — migration safety

| Property | Result |
|---|---|
| Additive | yes — one table, one materialised view, four indexes; nothing altered or dropped |
| Rows created | 135 alias rows; **62,681** term rows (57,543 alternate + 3,987 abbreviation + 1,016 canonical + 135 curated) |
| **Runtime** | **1.6 s** on the full corpus |
| Repeatably testable | yes — `IF NOT EXISTS` throughout; applied to `jobsvsai_test` and to dev |
| Lock behaviour | `CREATE MATERIALIZED VIEW` takes no lock on existing tables; it only reads `onet_*` and `canonical_occupation_identities`. Later refreshes should use `REFRESH … CONCURRENTLY`, which the unique index makes available. |

**A portability bug found and fixed in `scripts/migrate.sh`.** `"${wrap[@]}"` on an empty array
aborts under `set -u` in bash 3.2, still the macOS default; the VPS runs bash 5.2 and was never
affected, which is why 032 and 033 applied to production without trouble despite also declaring
their own transactions. The expansion is now `${wrap[@]+"${wrap[@]}"}`. This only ever broke
local runs.

### Disposition of the runner change

The standing instruction was: change the runner only if the failure reproduces through the
normal supported invocation on the current repository state; otherwise revert. **It
reproduces**, so the change stands. The evidence, re-verified against the committed tree:

| Check | Result |
|---|---|
| `scripts/migrate.sh` shebang | `#!/usr/bin/env bash` |
| Resolves on this machine to | `/bin/bash` — **GNU bash 3.2.57** |
| Migrations taking the `wrap=()` branch | **33 of 34** |
| Unguarded `"${wrap[@]}"`, empty array, `set -euo pipefail` | **aborts: `wrap[@]: unbound variable`** |
| Guarded `${wrap[@]+"${wrap[@]}"}`, same conditions | survives, expands to no arguments |
| Unfixed runner, virgin database | **0 of 34 applied** — dies at migration 001 |
| Fixed runner, virgin database | **34 of 34 applied**, second run a clean no-op |

The change landed in `bb5e7a1`. It is three characters of parameter expansion at one call site;
`set -euo pipefail` is retained and nothing is special-cased for 034.

Two things make this look smaller than it is, and both are worth stating plainly rather than
letting the summary carry them. First, **production was never at risk** — the VPS runs bash
5.2, where the unguarded form is legal, and all 33 self-transactional migrations applied there
successfully. Second, **the defect is invisible from any Linux shell**, which is why an
end-to-end check run anywhere but macOS shows a clean pass and concludes there is no defect.
The failure is real, host-specific, and total where it occurs: on a Mac, the runner applies
nothing at all.

**Unrelated local drift, reported not fixed:** the dev database has the AI News tables present
but does not record migrations 029–033 as applied, so `migrate.sh` refuses at 029. Production
has all 33 recorded. 034 was applied to dev directly and recorded, exactly as `migrate.sh`
would have. The drift predates this work and is left for a separate decision.

### Rollback

1. **Code** — revert the commit. `occupations.search_aliases` is untouched, so V1 ranking
   returns with it. No data restore.
2. **Schema** — `DROP MATERIALIZED VIEW occupation_search_terms; DROP TABLE consumer_aliases;`
   Nothing else references either.
3. **Frontend** — reverts with the same commit; `/api/occupations/search` still exists.

---

## Migration runner — bug, root cause, fix, tests

### The contract, established from the code and the corpus

`scripts/migrate.sh` deliberately supports **two** migration styles and chooses by inspecting
the file:

* no transaction control → the runner wraps it in `--single-transaction`
* its own `BEGIN`/`COMMIT` → run bare, because psql's `--single-transaction` would let the
  inner `COMMIT` end the outer transaction early

**33 of the 34 migrations in this repository take the second path.** Self-transactional is the
norm here, not an exception, and 034 follows it.

### Root cause

The self-transactional branch builds an empty array, `wrap=()`, and the call site expanded it
as `"${wrap[@]}"`. **Bash 3.2 treats an empty array as unset under `set -u` and aborts** with
`wrap[@]: unbound variable`. Bash 4.4 and later do not.

One correction to the brief's framing, and I want to be exact about it because it changes what
was at risk: **production was never affected.** The VPS runs bash 5.2, and all 33
self-transactional migrations — including 032 and 033 — applied there successfully. Verified
directly: production reports 33 applied. macOS still ships bash 3.2, so the defect only ever
broke local runs. It is a real bug worth fixing and it was not a production-safety hole.

### Fix — generic, not a workaround for 034

```bash
psql … ${wrap[@]+"${wrap[@]}"} -q < "$path"
```

`${arr[@]+…}` expands to nothing when the array is empty and to the quoted elements otherwise,
so both branches work on every bash. **`set -euo pipefail` is retained**; shell safety was not
weakened, and nothing was special-cased for migration 034.

### Runner regression tests

`backend/tests/test_migration_runner.py`, 12 test functions / 45 cases (one parametrised across all 34 migration files). `scripts/` was already mounted into the
test container; `migrations/` was added so the tests assert against the real corpus rather
than a hypothetical one.

Coverage: the script parses; `set -euo pipefail` is retained; **both** wrapper branches still
exist; the unguarded expansion cannot return (counted, not membership-tested — `"${wrap[@]}"`
is a substring of the guarded form); the guarded expansion is **executed** under `set -u` in
whatever bash the machine has, empty and populated; the BEGIN/COMMIT detection classifies the
real 34 files; a failed migration is not recorded as applied (the failure branch precedes the
`INSERT` and exits non-zero, and `ON_ERROR_STOP=1` is present); already-applied migrations are
skipped; checksum drift refuses to proceed; and every migration balances `BEGIN` with `COMMIT`.

### Migration 034 through the real runner

Validated on a **virgin database** rather than a clone, so the whole chain is exercised:

| | |
|---|---|
| All 34 migrations applied via `scripts/migrate.sh` | **PASS** |
| Total runtime, all 34 | **6.2 s** |
| Migration 034 alone, on the populated corpus | **1.6 s** |
| Re-run | `Database is up to date; nothing to apply.` |
| `034` rows in `schema_migrations` | **1** — no duplicate application |
| Indexes created on the view | **4** |
| `consumer_aliases` rows | 135 |

**Unrelated local drift, reported not fixed:** the dev database and its test clone hold the AI
News tables without recording migrations 029–033, so `migrate.sh` refuses at 029 on both.
Production records all 33. This predates the work and is left for a separate decision.

## Semantic tie policy

**Publication eligibility is not evidence.** Intent is resolved over every candidate
regardless of publication state; publication is applied only afterwards, to decide what can be
shown. The ordering is: exact canonical title → curated consumer mapping → exact alternate
title → normalised exact → prefix/token → fuzzy.

When two or more occupations remain tied at the strongest tier and canonical-title evidence
cannot separate them, the result is **`ambiguous`** — never resolved by publication state,
title length, alphabetical order, occupation id or row order.

Three refinements, each from a defect found during validation:

* **Ambiguity requires strong evidence.** A token-prefix tie is weak matching, not a decision
  worth putting to someone.
* **A chooser with nothing choosable is not a choice.** When every tied interpretation is
  unpublished — `surgeon` ties several surgical specialties, none published — the answer is
  `occupation_not_available`.
* **A weak-tier tie may not resolve to the published side either.** Where an unpublished
  candidate matches the query's own words at least as well as the best published one, search
  returns `no_reliable_match`. `soft eng` identified Software Developer at the token-prefix
  tier; answering with *Etchers and Engravers* because Software Developers is staged is the
  same substitution wearing a different hat.

### Mixed public/unavailable ambiguity

`ambiguous` carries a `choices` array in which each entry is `{title, available, slug?}`.
An equally-supported unpublished reading is **listed as unavailable rather than dropped**,
because dropping it silently resolves the ambiguity in favour of whatever happens to be
published. `available` is the only publication signal that crosses the boundary — the internal
lifecycle words never do, and an unavailable choice carries no slug because there is no page.

## Collision statistics

| Measure | Value |
|---|---|
| Total term rows | 62,681 |
| **Distinct normalised terms** | **50,886** |
| **Collision terms (map to >1 occupation)** | **7,581** |
| **Collision rate** | **14.9%** of distinct terms |
| Collisions spanning the public / non-public boundary | 4,545 |

Which tier the colliding terms come from — counted as *distinct colliding terms present in that
tier*, so a term that is both an alternate title and a curated alias is counted in both and the
column does not sum to 7,581:

| Tier | Colliding terms |
|---|---|
| `alternate` | 7,152 |
| `abbreviation` | 449 |
| `consumer_alias` | 44 — deliberate multi-mappings |
| `consumer_parent` | 12 — deliberate, that is what a parent term *is* |
| **`canonical`** | **0** |

**Canonical titles never collide.** That is the load-bearing property: the highest non-curated
tier is always unambiguous, which is why `cashier` and `data scientist` resolve outright while
`cashier`'s four alternate-title claimants sit 50 points below.

**The 7,581 figure must not be read as 7,581 ambiguous searches**, and the 4,545 figure must not
be read as 4,545 chances to substitute a published occupation for an unpublished one. A
collision only reaches the user when *nothing* separates the claimants — same tier, same
priority, and equal canonical-title evidence. On the 187-query benchmark:

| | |
|---|---|
| Queries hitting a collision term | **100 of 187 (53.5%)** |
| Resolved outright by stronger evidence | **79 of those 100 (79.0%)** |
| Surfaced to the user as a chooser (`ambiguous`) | **21 of 187 (11.2%)** |

So roughly four in five collisions are settled by canonical-title evidence long before a user
sees a choice, and the remaining fifth are shown as a choice rather than guessed at. Neither
path consults publication status to decide *which occupation the query meant*.

## Typeahead policy

**The policy is conservative by decision: a partial string that cannot be resolved reliably
returns `no_reliable_match` until more characters are typed.** All ten cases, measured against
the final implementation:

| Partial input | Result | Tier / score |
|---|---|---|
| `regist nur` | **`public_matches`** — Registered Nurses, Critical Care Nurses, Health Education Specialists | token-prefix / 700 |
| `soft eng` | `no_reliable_match` — **not** Etchers and Engravers | — |
| `data sci` | `no_reliable_match` | — |
| `pen test` | `no_reliable_match` | — |
| `teach` | `no_reliable_match` | — |
| `electric` | `no_reliable_match` | — |
| `cash` | `no_reliable_match` | — |
| `martial arts` | `no_reliable_match` | — |
| `project man` | `no_reliable_match` | — |
| `web des` | `no_reliable_match` | — |

Nine of ten decline to answer. **This is intentional, not a coverage failure.** A short partial
string matches on weak partial-token evidence, and weak evidence over a 62,681-term corpus
reliably produces a confident-looking occupation that has nothing to do with the query.
`soft eng` is the canonical example: the token-prefix tier ties Software Developer with
*Etchers and Engravers*, via the alternate title "Soft Metal Hand Engraver". Ranking one above
the other on that evidence would be a guess wearing the costume of an answer, and offering the
pair as a chooser would be worse — it presents a coin-flip as a considered question. Declining
is the only honest option at that evidence level.

`regist nur` shows what the policy admits: two tokens, each a distinctive prefix of a real
title, converging on one occupational family. That is genuine partial evidence, not a
collision.

**Continued typing recovers normally**, which is what makes the strictness affordable. Every
complete query in the critical set resolves — `teacher`, `electrician`, `cashier`,
`martial arts instructor`, `pen tester`, `software engineer`, `data scientist` all return a
definite status. Verified in the browser end to end: `zzqx` produced "No matching occupation
found", and continuing on to `electrician` replaced it with the unavailable panel naming
Electricians; `nurse` → Escape → continuing to `nurse pract` re-opened the list with a
narrowed result. Dismissal is never sticky and a no-match never latches.

The honest reading is that partial input against a corpus where most intended occupations are
unpublished cannot be answered well, and that saying so beats guessing. If typeahead
responsiveness later proves more valuable than this strictness, the knob is the tie-block in
the weak-tier fallback — it should be turned deliberately, with the benchmark re-run, not by
loosening a threshold until the numbers look better.

## Weak-tier combination policy

Exact and prefix tiers **stop early** — an exact hit needs no corroboration. The three weak
tiers (token-prefix, token-contains, fuzzy) are **gathered together**, because each caps its
candidate list at 40 and stopping at the first non-empty weak tier discards rows a later tier
would have found. `soft eng` exposed this: token-prefix returned a capped list containing no
published occupation, and the token tier that would have found one never ran.

Swamping is bounded by three things: each tier caps at 40 candidates; `_dedupe` collapses to
one row per occupation keeping its best term; and tier floors are strictly ordered, so a large
number of weak candidates can never outrank a single strong one.

## Legacy endpoint

Both endpoints call the same `occupation_search.resolve`; a test asserts the legacy wrapper
delegates and that both agree on ordering. `/occupations/search` returns results for
`public_matches` **and** `ambiguous` — the bare-list shape cannot say "these are alternatives",
but returning them beats returning nothing — and returns `[]` for `occupation_not_available`,
because it has no way to express that.

Callers re-audited: the homepage now uses `/search/resolve`; the legacy Next proxy route and
the backend integration tests still use `/search` and both pass. No caller interprets
`ambiguous` as no-results.

---

## Final status

```
MIGRATION RUNNER ROOT CAUSE:     `wrap=()` (the self-transactional branch, taken by 33 of 34
                                 migrations) expanded as `"${wrap[@]}"`. Bash 3.2 treats an
                                 empty array as unset under `set -u` and aborts. Bash 4.4+
                                 does not. The VPS runs 5.2 and applied all 33 successfully,
                                 so production was never affected; macOS ships 3.2, so only
                                 local runs broke.

MIGRATION RUNNER FIX:            `${wrap[@]+"${wrap[@]}"}` -- expands to nothing when empty,
                                 to the quoted elements otherwise. Generic, works on every
                                 bash, nothing special-cased for 034, `set -euo pipefail`
                                 retained. Landed in bb5e7a1. RETAINED, not reverted:
                                 re-verified on the committed tree that the unfixed runner
                                 applies 0 of 34 on a virgin database on this host
                                 (bash 3.2.57) while the fixed runner applies 34 of 34.
                                 The defect is invisible from bash >= 4.4, so an end-to-end
                                 check on Linux shows a clean pass either way.

MIGRATION 034 VIA migrate.sh:    PASS -- all 34 applied to a virgin database; re-run is a
                                 clean no-op; 1 row in schema_migrations, no duplicate;
                                 4 indexes created; 135 consumer aliases.
SELF-TRANSACTIONAL MIGRATIONS:   33 of 34 -- the project convention, which 034 follows.
                                 1 migration is wrapped by --single-transaction.
MIGRATION 034 RUNTIME:           1.6 s alone on the populated corpus; 6.2 s for all 34.

SEARCH TERMS:                    62,681
DISTINCT NORMALIZED TERMS:       50,886
COLLISION TERMS:                 7,581  (14.9% of distinct terms; 0 canonical,
                                 7,152 alternate, 449 abbreviation, 44 curated alias,
                                 12 curated parent -- tiers overlap, so they do not sum)
COLLISIONS CROSSING PUBLIC LINE: 4,545
BENCHMARK COLLISIONS:            100 of 187 queries hit a collision term (53.5%);
                                 79 resolved by stronger evidence; 21 ended in ambiguity

PUBLIC TOP-1:                    91.3%  (84/92)
PUBLIC TOP-3:                    95.7%  (88/92)   (target >=90%   MET)
PUBLIC USEFUL:                   95.7%
PUBLIC MISLEADING:                2.2%  (2/92)    (target <=3%    MET)
NON-PUBLIC DETECTION:            97.9%  (93/95)   (target >=95%   MET)
NON-PUBLIC FALSE SUBSTITUTION:    2.1%  (2/95)    (target <=3%    MET)
NON-PUBLIC FELL THROUGH:          0.0%
AMBIGUITY HANDLING:              21 of 187 (11.2%) return `ambiguous`; 0 forced resolutions
                                 of an unbreakable tie; 0 ties settled by publication state

CRITICAL QUERIES:                21 / 21 correct, each also asserting the specific wrong
                                 answer V1 gave is absent

PARTIAL QUERY CASES:             regist nur -> public (Registered Nurses)
                                 soft eng   -> no_reliable_match  (NOT Soft Metal Hand
                                               Engraver -- the Step 9 requirement)
                                 teach, data sci, electric, cash, web des, project man,
                                 martial arts, pen test -> no_reliable_match
                                 Deliberate: a weak-tier tie with an unpublished candidate
                                 declines rather than substituting. Every complete query
                                 still resolves.

DB P50:                          0.3 ms
DB P95:                          0.5 ms   (p99 16.4 ms, max 29.6 ms)
API P50:                         5.2 ms
API P95:                        19.9 ms   (p99 32.9 ms, max 42.9 ms, 0 non-200)
NEXT PROXY P50/P95:              8.3 ms / 22.2 ms   (p99 35.3 ms)

BACKEND TESTS:                   ./scripts/run-tests.sh -q
                                 570 passed, 1 skipped, 0 failed, 14.10s
                                 (571 collected; the skip is the docker-compose-dependent
                                  migration failure-path test, which skips rather than
                                  reporting a false pass when compose is unreachable)
FRONTEND TESTS:                  npm test
                                 67 passed, 0 failed, 0 cancelled, 0 skipped, 72.6ms
LINT:                            npm run lint -- eslint, no findings
BUILD:                           npm run build -- compiled successfully in 596ms,
                                 8/8 static pages generated, 0 errors
BROWSER QA:                      PASS -- public, non-public, ambiguous, no-match and
                                 recovery-by-continued-typing all verified in a real
                                 browser. Keyboard: ArrowDown / ArrowUp / wrap both ways /
                                 Escape / Tab / Enter-on-highlight / mouse / hover all
                                 verified against the live DOM. Enter-to-SUBMIT could not
                                 be exercised (harness sends code:"" which:0, so no default
                                 actions fire); same path verified via the submit button.
                                 Mobile 360x780 re-checked: no horizontal overflow.
                                 No scores on unavailable or ambiguous panels; no internal
                                 publication status exposed in any state.

ACCESSIBILITY FIX IN THIS PHASE: the typeahead had no ArrowDown/ArrowUp/Escape handling at
                                 all. Now implements the ARIA combobox pattern. Presentation
                                 layer only -- no ranking, scoring or publication code
                                 touched.

PROVISIONAL COUNTS:              106 total / 47 compounded / 59 sensitivity-only

COMMIT:                          feat: implement trustworthy consumer occupation search v2

STATUS:                          READY FOR ARCHITECT REVIEW
```

The public cohort is 507, unchanged. Nothing was promoted, scored, deployed or merged.
