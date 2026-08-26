# Consumer Job Search & Coverage V2 — Discovery Audit

**Date:** 2026-08-25 · **Phase:** audit and offline prototype · **Nothing deployed, promoted, published or scored**

**The reframe holds, and it is sharper than first stated.** Of 101 failing benchmark queries,
**82 (81.2%) fail because the occupation is not published** and only 19 (18.8%) because search
cannot find one that is. **Zero** fail because O*NET lacks a suitable occupation.

Search V2 alone takes the useful rate from **46.0% → 55.6%**. Adding every staged occupation
that already meets both launch gates takes it to **63.1%**. The same prototype against the full
imported taxonomy reaches **99.5%** — so the ranking design is validated, and everything
between 63% and 99% is scoring work that has not been done.

---

## 1. Current benchmark

187 plain-language queries across 16 sectors, graded against the live production API.
**A** intended result first · **B** top 3 · **C** present in top 10 · **D** results but none
useful · **F** nothing.

| Grade | n | Rate |
|---|---|---|
| A | 42 | 22.5% |
| B | 28 | 15.0% |
| C | 16 | 8.6% |
| D | 73 | **39.0%** |
| F | 28 | **15.0%** |

**A 22.5% · A+B 37.4% · useful 46.0% · D 39.0% · F 15.0%**

## 2. Authoritative failure classification

Every D/F query reclassified using the **publication status recorded in the database**, with
`staged` and `review_required` separated. No heuristic or indirect annotation.

| Class | n | % of failures | % of benchmark |
|---|---|---|---|
| **STAGED_COVERAGE_GAP** | **81** | **80.2%** | 43.3% |
| REVIEW_REQUIRED_COVERAGE_GAP | 1 | 1.0% | 0.5% |
| SEARCH_GAP | 9 | 8.9% | 4.8% |
| ALIAS_GAP | 8 | 7.9% | 4.3% |
| AMBIGUOUS_QUERY | 2 | 2.0% | 1.1% |
| **SOURCE_TAXONOMY_GAP** | **0** | **0.0%** | 0.0% |

**Coverage-caused: 82 (81.2%). Search-caused: 19 (18.8%).**

**SEARCH_GAP (9)** — public occupation, exact alias already in the database, ranking fails:
`auditor`, `office manager`, `product manager`, `operations manager`, `product designer`,
`marketing manager`, `driver`, `mechanical engineer`, `electrical engineer`.

**ALIAS_GAP (8)** — public occupation, consumer word absent: `devops engineer`,
`cloud engineer`, `sysadmin`, `it support`, `lab technician`, `maths teacher`, `headteacher`,
`driving instructor`.

## 3. Root cause of the search failures

`search_occupations` (`app/repositories/occupations.py:41`) orders by

```sql
ORDER BY similarity(lower(o.title || ' ' || o.search_aliases), lower(:query)) DESC, o.title
```

`search_aliases` averages **1,269 characters, maximum 18,368**. Trigram similarity divides
shared trigrams by the union, so a longer haystack means a larger denominator: **the more
alternate titles an occupation carries, the lower it ranks.** A precise inversion of intent.

Measured live for `data entry operator`, the only returned row scores `similarity = 0.0254` —
**below the 0.18 threshold**. It was admitted by the unanchored `LIKE '%token%'` clause (its
5,104-character blob happens to contain all three tokens) and ranked first because nothing else
matched. There is **no exact-match tier at all**: a curated alias, a canonical title and an
accidental substring compete on one fuzzy number.

## 4. Alternate-title utilisation

| Measure | Count |
|---|---|
| `onet_alternate_titles` rows | 57,543 |
| Distinct titles / abbreviations | 46,687 / 3,316 |
| SOC codes covered | 1,016 (whole taxonomy) |
| **Alt titles for the public 507** | **27,993 — ~55 each** |

Currently these participate **only** as undifferentiated text inside the blob, where they
actively harm ranking. A large, structured, already-licensed alias corpus is being wasted.

## 5. Staged occupation audit

All 509 non-public occupations assessed against triage run 2 (`phase6-triage-postcoverage-2026q3-v1`).

**No staged or review_required occupation carries a production score.** Only the 507 public
identities have snapshots — promotion is what creates a score, so "staged" means "not scored".

| Bucket | STAGED (405) | REVIEW_REQUIRED (104) | Total |
|---|---|---|---|
| READY_OR_NEAR_READY | **0** | **0** | **0** |
| MINOR_REMEDIATION | 207 (51.1%) | 10 | **217** |
| MAJOR_REMEDIATION | 116 (28.6%) | 10 | 126 |
| DO_NOT_PUBLISH | 28 (6.9%) | 0 | 28 |
| NOT_TRIAGED | 54 (13.3%) | 84 | **138** |

**Not one staged occupation is launch-eligible.** The triage-eligible cohort is exactly the
public 507 — everything that passed the gates was promoted.

### The 217 "minor" cases split in two, and the split matters

| Sub-group | n | Nature |
|---|---|---|
| **(a) Both launch gates met, blocked only by provisional-model sensitivity** | **68** | methodological — no new data needed |
| (b) Coverage within 8 points of the 80 gate | 149 | mapping — needs evidence |

Group (a) is the actionable one. Electricians is the clearest case: **coverage 100, confidence
88** — passing both gates — blocked because neutralising the provisional labour model moves
replacement risk by **3.32 points against a 3.0 maximum**. The finding is explicit: *"the score
moves materially when the provisional regulation, adoption and labour-market models are
neutralised, so it is really a claim about those models."*

### The 138 never triaged

The Phase 5 bounded corpus covered **878 of 1,016** occupations. The 138 excluded were never
scored, never triaged, and have **no coverage or confidence reading at all** — they are
unknowns, not rejects. They include the highest consumer-value technology occupations.

Blocking codes across all 878 assessed:

| Code | n |
|---|---|
| `weighted_coverage_below_launch_minimum` | 311 |
| `not_review_ready` | 134 |
| `confidence_below_launch_minimum` | 128 |
| `provisional_input_sensitivity` | 106 |
| `high_replacement_despite_severe_constraints` | 1 |

## 6. High-priority consumer coverage

58 occupations behind the 82 coverage failures.

| Bucket | n |
|---|---|
| MINOR_REMEDIATION | 25 |
| MAJOR_REMEDIATION | 18 |
| NOT_TRIAGED | 10 |
| DO_NOT_PUBLISH | 5 |

**Never triaged — no reading exists (highest consumer value, least known):**

| SOC | Title | Serves |
|---|---|---|
| 15-1252.00 | **Software Developers** | software engineer, swe, programmer, backend, full stack, mobile |
| 15-2051.00 | **Data Scientists** | data scientist, data analyst, ml engineer, ai engineer |
| 15-1255.00 | Web and Digital Interface Designers | ux designer, ui designer |
| 13-1082.00 | Project Management Specialists | project manager, product manager |
| 13-2051.00 | Financial and Investment Analysts | financial analyst |
| 27-3043.00 | Writers and Authors | copywriter |
| 29-2042.00 | Emergency Medical Technicians | paramedic |
| 53-3054.00 | Taxi Drivers | taxi driver |
| 51-9199.00 / 51-2099.00 | Production Workers / Assemblers, All Other | factory worker, assembler |

**Gates met, sensitivity-blocked (promotable on a policy decision, no new data):**
Electricians (100/88), Welders (87/81), Plumbers (86/82), Personal Financial Advisors (86/82),
Information Security Analysts (86/83), Firefighters (86/81), Laborers & Freight Movers (86/81),
Brickmasons (85/80), Massage Therapists (85/82).

**Major remediation:** Waiters (71/76), Web Developers (64/69), Graphic Designers (64/70),
Data Entry Keyers (65/70), Childcare Workers (64/70), Executive Secretaries (70/76), and 12 more.

**Do not publish:** Bartenders (36/36), Baristas (43/44), Retail Salespersons (45/47),
Cashiers (51/53), Locksmiths (41/40) — coverage far below any defensible gate.

## 7. Was the 507 too conservative?

**Not against its own gates — the 507 is exactly the triage-eligible set, not an arbitrary
count.** But two findings suggest the *policy* deserves architect review, and neither is mine
to decide.

**First, a policy inconsistency worth naming.** Every published occupation's public payload
already discloses provisional dependence:

```
confidence            = 79.9
weightedTaskCoverage  = 82.3
provisionalWeightShare = 25.0
```

All 507 snapshots carry a `provisional_sensitivity` value, and `phase6-provisional-disclosure-v1`
decided disclosure **yes, per page**. So the shipped product already tells readers that a
quarter of replacement-risk weight rests on provisional proxy models — while the launch gate
excludes 106 occupations for being *sensitive* to those same models. **The disclosure stance is
more permissive than the gating policy.** Reconciling them would unblock 68 occupations without
weakening any evidence requirement. That is a deliberate decision for the architect, not a
gate to quietly loosen.

**Second, the bounded corpus excluded the occupations that matter most to this product.** 138
occupations were never scored, and they include Software Developers and Data Scientists — the
occupations an AI-and-careers product exists to talk about. That is a scope artefact of Phase 5,
not a quality judgement about those occupations.

## 8. Search V2 architecture

Deterministic tiers, highest wins. **No LLM, no network, no per-query model call.**

| Tier | Floor | Matched against |
|---|---|---|
| 1 Curated consumer alias, exact | 1000 | `consumer_aliases` |
| 2 Canonical title, exact | 950 | normalised title |
| 3 Curated ambiguous parent | 920 | `consumer_aliases` |
| 4 O*NET alternate title, exact | 900 | each alt title **individually** |
| 5 Canonical title prefix | 850 | normalised title |
| 6 Alternate title prefix | 800 | each alt title individually |
| 7 All tokens in canonical title | 700 | normalised title |
| 8 All tokens in one alt title | 650 | each alt title individually |
| 9 Fuzzy | 0–500 | **best single title**, never a blob |

The decisive changes: candidates are compared against **individual** titles so alias richness
can only help, and fuzzy is capped at 500 so it can never overtake an exact or curated tier —
which is exactly the `pen tester` failure. Ambiguous parents sit above generic alternate-title
matches because `teacher` is an exact alt title for dozens of occupations: noise, not signal.
Ties break by tokens present in the canonical title, then title length — alphabetical alone is
what put *Adapted Physical Education Specialists* first for `teacher`.

**Publication eligibility is enforced at the index, not the ranker.** The audit may index
staged occupations to measure potential; the public runtime indexes only publishable ones, so
no user can be routed to an unpublished occupation.

### Normalisation (Step 8)

Curated, deterministic expansions applied before matching: `ml → machine learning`,
`ai → artificial intelligence`, `swe → software engineer`, `ux → user experience`,
`ui → user interface`, `seo → search engine optimization`, `hr → human resources`,
`it → information technology`, `soc analyst → security operations center analyst`,
`pen tester → penetration tester`. The prototype catalogue holds **80 terms / 135 mappings** —
small on purpose, because 27,993 O*NET alt titles already do the bulk of the work.

### Generic families (Step 9)

Broad queries return disambiguation rather than a forced pick. `teacher` →
Elementary · Secondary · Kindergarten · Special Education · Postsecondary, filtered to
publishable occupations only. Contract: results carry `matched_term`, `mapping_type`,
`confidence` and `is_disambiguation`, so the UI can render a chooser instead of a ranking.

## 9. Prototype results — both cohorts

**Cohort B = 507 public + 68 staged that already meet both launch gates (575).** Nothing whose
coverage or confidence falls short, and nothing never triaged — an unknown is not a candidate.

| Metric | Current | **V2 / 507** | **V2 / cohort B (575)** | V2 / full 1016 |
|---|---|---|---|---|
| A | 22.5% | 50.8% | **57.2%** | 92.0% |
| A+B | 37.4% | 54.5% | **62.0%** | 98.9% |
| **useful (A+B+C)** | **46.0%** | **55.6%** | **63.1%** | **99.5%** |
| D | 39.0% | 43.9% | 36.4% | 0.5% |
| F | 15.0% | 0.5% | 0.5% | 0.0% |

### Step 12 — search improvement versus coverage improvement

```
CURRENT                             46.0% useful
SEARCH V2 ONLY                      55.6% useful   (+9.6 from architecture)
SEARCH V2 + SAFE COVERAGE EXPANSION 63.1% useful   (+7.5 more from 68 occupations)
SEARCH V2 + FULL TAXONOMY           99.5% useful   (theoretical ceiling)
```

**Architecture buys ~10 points. The safe expansion buys ~7 more. The remaining ~36 points are
scoring work that has not been done** — the 126 major-remediation and 138 never-triaged
occupations.

D rises slightly under V2/507 (39.0% → 43.9%) because V2 converts dead ends into *some*
answer: queries that graded F now grade D. F falling 15.0% → 0.5% is the same movement seen
from the other side. Neither is a real quality change for those queries — the occupation is
still missing.

## 10. Supplied failures re-evaluated

| Query | Current | Canonical / status | Class | V2 / 507 | V2 / cohort B |
|---|---|---|---|---|---|
| **teacher** | Adapted Physical Education Specialists | multiple, public | — (graded B) | **Elementary → Secondary → Kindergarten** | same |
| **ML engineer** | Search Marketing Strategists | Software Developers, **staged** | STAGED_COVERAGE_GAP | Petroleum Engineers *(fuzzy)* | unchanged |
| **data scientist** | Bioinformatics Technicians | Data Scientists, **staged** | STAGED_COVERAGE_GAP | Atmospheric and Space Scientists | unchanged |
| **data analyst** | Bioinformatics Technicians | multiple, public | — (graded C) | **Statisticians → Management Analysts → BI Analysts** | same |
| **data entry operator** | First-Line Supervisors of Office | Data Entry Keyers, **staged** | STAGED_COVERAGE_GAP | First-Line Supervisors *(fuzzy)* | unchanged |
| **pen tester** | Non-Destructive Testing Specialists | Information Security Analysts, **staged** | STAGED_COVERAGE_GAP | Inspectors, Testers, Sorters | **Information Security Analysts** ✓ |
| **martial arts instructor** | *(no results)* | Exercise Trainers, **staged** (79/79) | STAGED_COVERAGE_GAP | Career/Technical Education Teachers | unchanged |

**Two fixed by search alone** (`teacher`, `data analyst`). **One more by the safe expansion**
(`pen tester`). **Four still need scoring work.** Exercise Trainers misses cohort B by a single
coverage point (79 against the 80 gate).

## 11. Performance

| Measurement | p50 | p95 | p99 |
|---|---|---|---|
| Current production API (from a laptop, includes network) | 275 ms | 365 ms | — |
| V2 prototype, 507 | 238 ms | 366 ms | 448 ms |
| V2 prototype, 575 | 272 ms | 422 ms | 510 ms |

**None of these is a production figure and they are not comparable.** The baseline includes a
round trip to the VPS; the prototype is pure Python doing a full linear scan over every
occupation × ~55 alt titles with `difflib` on each query. A SQL implementation does not work
that way.

What the profile does establish is the shape of the work: **80% of queries (149/187) resolve in
the exact or curated tiers** — btree lookups on a normalised term, effectively free — and only
**20% fall through to fuzzy**, the one tier needing a GIN trigram scan. The materialised term
set is ~28k rows. **No per-query AI call; fully deterministic.**

## 12. Database design

**Recommendation: do not duplicate 57k rows into a hand-maintained table.**

`onet_alternate_titles` is keyed by `occupation_code`, not `occupation_id`, and carries no
normalised column or index — so it cannot serve search directly today, but it should remain the
source of truth. The smallest robust change:

1. **A materialised view `occupation_search_terms`** unioning three sources into one shape —
   `(occupation_id, term, normalized_term, term_type, priority, source)`:
   canonical titles (`term_type='canonical'`), O*NET alternate titles
   (`'alternate'` / `'abbreviation'`, joined through `canonical_occupation_identities`), and
   curated consumer aliases. Refreshed on O*NET import and on promotion.
2. **Indexes:** btree on `normalized_term` (tiers 1–8), GIN `gin_trgm_ops` on `normalized_term`
   (tier 9).
3. **A small `consumer_aliases` table** (~135 rows today) with `mapping_type`, `confidence`,
   `source`, `notes`, `policy_version`.

The view keeps one copy of the data and one refresh path; the alias table is the only
hand-maintained surface. **No scoring table is touched, no occupation row created, no score
written.**

## 13. Consumer display labels

Results carry both identities: `display_label` (what the user typed or the friendly name,
e.g. *Penetration Tester*) and the canonical occupation (*Information Security Analysts*) with
its slug and score. **The alias never owns a score and never becomes an occupation.**

`Teacher` must not receive an averaged "generic teacher" score — the underlying occupations
genuinely differ, which is why broad terms return disambiguation instead.

## 14. SEO

**Do not mint a page per alias.** `/jobs/penetration-tester` must not exist merely because the
alias does; that manufactures duplicate content against `/jobs/information-security-analysts`.
Aliases belong in search and in on-page synonym text, not in the URL space. If alias routing is
ever wanted, it should be an explicit design with 301s to the canonical slug — a separate
decision, not a side effect of this work.

## 15. Publication recommendation

```
Current public cohort                              507
Safely promotable on a policy decision only        +68   (gates met, sensitivity-blocked)
                                                   ----
Recommended revised cohort                          575

Minor remediation (coverage within 8 pts of gate)  +149  (needs a mapping run)
Major remediation                                  +126
Never triaged / unknown                            +138  (needs full scoring)
Do not publish                                      +28
```

**575 is not proposed as a target number.** It is the set for which the evidence already exists
and only a policy reconciliation is outstanding (§7). Everything beyond it requires real
scoring work, and no occupation should be promoted to improve a search metric.

## 16. Implementation sequence

**Phase A — Search V2 on the existing 507.** Materialised view, indexes, alias table, tiered
ranking behind a flag. Expected 46.0% → ~55.6% useful, F 15.0% → ~0.5%. No scoring change, no
promotion, fully reversible.

**Phase B — reconcile the provisional-sensitivity policy (§7).** An architect decision, not an
engineering task. If the disclosure stance already accepted for the 507 extends to the
sensitivity gate, 68 occupations become promotable through the normal triage → promotion →
content pipeline, taking useful to ~63.1%.

**Phase C — scoring expansion for the never-triaged 138**, prioritising Software Developers,
Data Scientists, Web and Digital Interface Designers and Project Management Specialists. This
is a Phase 5B-scale mapping and scoring programme and is where the majority of the remaining
consumer value sits.

**Phase D — alias and display-label expansion** once real search telemetry exists.

**Phase E — permanent search-quality gate** (§17).

## 17. Search quality gate

The 187-query benchmark becomes a checked-in regression fixture with deterministic grading
(substring match against expected canonical titles — no subjective judgement at test time).

Proposed gates, asserted against the **current public cohort** so coverage changes do not mask
search regressions:

| Gate | Threshold |
|---|---|
| Useful rate (A+B+C) | must not fall below the recorded baseline − 2 points |
| Misleading rate (D) | must not rise above baseline + 2 points |
| No-result rate (F) | must not exceed 2% |
| Critical-query set | a named subset (`teacher`, `nurse`, `electrician`, `driver`, `accountant`, …) must each grade A or B |

Grading is deterministic, so this can block a search release safely. It should **not** block
unrelated builds — scope it to changes touching search, the alias table or the term view.

## 18. Risks

**Promoting occupations to improve search metrics.** The strongest temptation this audit
creates. Electricians passes both launch gates and is still blocked for a stated reason.
Search numbers are not evidence about scoring quality, and §7 is a request for a decision, not
a recommendation to lower a bar.

**Aliases acquiring scores.** `Penetration Tester` must resolve *to* Information Security
Analysts and never become a scored entity; `teacher` must never receive an averaged score. The
schema in §12 stores no score and offers no path to one.

**Mapping drift into editorialising.** `product manager → Project Management Specialists` at
0.75 is a judgement. Confidence and `notes` are stored so mappings are reviewable, and
low-confidence hits should read "closest occupation", not an identity claim.

**Prototype latency is not production latency** (§11). The SQL implementation must be measured
on its own before any responsiveness claim.

**Benchmark bias.** 187 queries written by one author in one sitting, weighted toward UK/US
English. A good relative instrument; not an absolute measure of consumer behaviour. Real
telemetry should be privacy-preserving and aggregated (§19).

## 19. Privacy

The existing principle — **raw search strings are never sent to GA4** — is preserved, and
nothing here requires changing it. The benchmark is a synthetic checked-in corpus, and
prototype evaluation ran entirely offline.

If search-quality telemetry is wanted, aggregate rather than log: counts of zero-result and
no-click searches bucketed by **matched tier** (`CURATED_EXACT`, `ALT_TITLE_EXACT`, `FUZZY`,
`NONE`), never by query text. That shows whether the fuzzy tail is carrying too much load
without recording what anyone typed.

---

## Final status

```
CURRENT USEFUL RATE:              46.0%   (A 22.5% · A+B 37.4% · D 39.0% · F 15.0%)

AUTHORITATIVE FAILURE BREAKDOWN:  101 D/F of 187 queries
  STAGED_COVERAGE_GAP              81   80.2% of failures   43.3% of benchmark
  REVIEW_REQUIRED_COVERAGE_GAP      1    1.0%                0.5%
  SEARCH_GAP                        9    8.9%                4.8%
  ALIAS_GAP                         8    7.9%                4.3%
  AMBIGUOUS_QUERY                   2    2.0%                1.1%
  SOURCE_TAXONOMY_GAP               0    0.0%                0.0%

PUBLIC SEARCH GAPS:               9
ALIAS GAPS:                       8
STAGED COVERAGE GAPS:             81
REVIEW_REQUIRED GAPS:             1
SOURCE TAXONOMY GAPS:             0

STAGED OCCUPATIONS:               405   (+104 review_required = 509 non-public)
READY/NEAR-READY:                 0     no staged occupation is launch-eligible
MINOR REMEDIATION:                217   of which 68 already meet both gates and are
                                        blocked only by provisional-model sensitivity
MAJOR REMEDIATION:                126
DO NOT PUBLISH:                   28
NOT TRIAGED:                      138   never in the Phase 5 bounded corpus; no reading exists

HIGH-PRIORITY CONSUMER OCCUPATIONS:
  Never triaged   Software Developers · Data Scientists · Web and Digital Interface
                  Designers · Project Management Specialists · Financial and Investment
                  Analysts · Writers and Authors · Emergency Medical Technicians ·
                  Taxi Drivers · Production Workers · Assemblers and Fabricators
  Gates met       Electricians (100/88) · Information Security Analysts (86/83) ·
                  Welders (87/81) · Plumbers (86/82) · Personal Financial Advisors (86/82) ·
                  Firefighters (86/81) · Laborers & Freight Movers (86/81) ·
                  Brickmasons (85/80) · Massage Therapists (85/82)

SEARCH V2 CURRENT-507 USEFUL RATE:    55.6%   (A 50.8% · A+B 54.5% · D 43.9% · F 0.5%)
SEARCH V2 EXPANDED-COHORT USEFUL RATE: 63.1%   (A 57.2% · A+B 62.0% · D 36.4% · F 0.5%)
                                       99.5%   against the full taxonomy — the ceiling,
                                               shown to prove the ranking design, not proposed

RECOMMENDED PUBLIC COHORT SIZE:   575   = 507 + 68 whose evidence already clears both gates.
                                        Not a target number; the set where only a policy
                                        reconciliation is outstanding.

MIGRATION REQUIRED:               YES — additive only: a materialised occupation_search_terms
                                  view over existing O*NET titles with btree + GIN indexes,
                                  plus a small consumer_aliases table. No scoring table
                                  touched, no occupation created, no score written.

SCORING WORK REQUIRED:            YES — and it is the dominant constraint. 81% of failures are
                                  coverage. Architecture buys ~10 points, the safe expansion
                                  ~7 more; the remaining ~36 points need the 138 never-triaged
                                  and 126 major-remediation occupations scored.

RECOMMENDED NEXT IMPLEMENTATION:  Phase A — ship Search V2 on the existing 507. It is cheap,
                                  deterministic, needs no LLM, reuses 27,993 already-imported
                                  alternate titles, removes essentially every dead end, and
                                  touches no scoring data. In parallel, put the
                                  provisional-sensitivity policy inconsistency (§7) to the
                                  architect: the shipped product already discloses provisional
                                  dependence on every page, while the gate excludes 68
                                  occupations for that same dependence. Treat the 138
                                  never-triaged occupations as a separate scoring programme —
                                  that is where the consumer experience actually lives.

STATUS:                           READY FOR ARCHITECT REVIEW
```
