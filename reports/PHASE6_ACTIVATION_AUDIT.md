# Phase 6 — Activation audit

Date: 2026-08-21
Status: **Promoted and activated 2026-08-21.** 507 publications are `public`.
Active scoring model is still **JVS 1.0.3**; production snapshots reference **JVS 2.0.0-phase4b**.

## Verdict

**ACTIVATED.** Approved by Akshay on 2026-08-21, including the decision to keep the
SOC-derived categories. The stale frontend image was rebuilt first (§10); activation and its
verification are recorded in §11.

## 1. Promotion

| Check | Expected | Actual |
|---|---|---|
| Promotion run status | completed | completed |
| Production snapshots (current) | 507 | **507** |
| Distinct identities | 507 | **507** |
| Duplicate current identities | 0 | 0 |
| Factor contribution rows | ~3,042 | **3,042** |
| Task contribution rows | ~8,218 | **8,218** |
| Snapshots outside approved cohort | 0 | 0 |
| Snapshots on a legacy model | 0 | 0 |
| Snapshots not publishable | 0 | 0 |
| Occupation-level augmentation promoted | 0 | 0 |
| Factor reconciliation failures | 0 | 0 |
| Task reconciliation failures | 0 | 0 |
| Carry mismatches vs Phase 5B candidates | 0 | 0 |
| Minimum coverage in cohort | ≥80 | 80.08 |
| Minimum confidence in cohort | ≥75 | 75.78 |

Run key `phase6-promotion-2026q3-v1`, source `phase5b-coverage-completion-2026q3-v1`,
selection from the frozen identity list in `reports/PHASE6_APPROVED_LAUNCH_COHORT.codes`
(507 codes, `--expect-count 507`), not a live re-selection.

Provisional provenance survived promotion intact: **1,014 provisional factor rows**
(507 × 2), one proxy model version, `isProvisionalProxy` and `proxyModelVersion` preserved
per factor.

**Rollback capability verified** without disturbing the approved run: flipping the run to
`rolled_back` inside a transaction dropped currency to 0 while all 507 snapshots remained,
and reverting restored 507. The run is still `completed`.

Phase 5 and Phase 5B historical data unchanged — 5 calculation runs, dependency hashes and
replay flags intact, 4,390 candidate scores, 35,686 scope rows.

## 2. Content

| Check | Result |
|---|---|
| Complete publication candidates | **507 / 507** |
| Incomplete | 0 |
| With `jobsvsai_verdict` | 507 |
| Bound to a verdict snapshot | 507 |
| Snapshot not current | 0 |
| Distinct slugs | 507 (no collisions) |
| Carrying the provisional disclosure | **507** |

Content run `phase6-content-postpromotion-2026q3-v1` (id 2), policy
`phase6-public-content-v2`, template `phase6-verdict-template-v2`.

### Disclosure — Option A as implemented

Computed per occupation from that snapshot's own factor rows, so the sentence a page shows
cannot drift from the arithmetic behind the score. Combined weight is derived, not
hard-coded, and resolves to **0.25 / 25%** for all 507.

- **Page note** (concise, beside Replacement Risk): "Replacement Risk includes provisional
  estimates for AI adoption pressure and labour-market resilience. These inputs are
  versioned and monitored as the methodology improves." — with a link to
  `/methodology#provisional-factors`.
- **Detail** (score methodology area): names both factors with weights 0.15 and 0.10, states
  they collectively carry 25% of Replacement Risk weighting, states they are estimated from
  structural proxies and have not had the validation the other four factors have had, and
  states they are versioned and published per occupation.
- **`/methodology`**: full explanation, anchored at `#provisional-factors`.

No probability language, no claim that the score is wrong, and the models are never
described as validated. Verified by assertion in
`test_provisional_factors_are_disclosed_with_their_real_combined_weight`.

One correctness fix during implementation: the builder originally treated "no provisional
factors" and "factors never loaded" identically, which would have let a wiring fault silently
drop the disclosure. Absent key now marks content incomplete; an empty list is legitimately
no disclosure.

## 3. Editorial rows

| Check | Result |
|---|---|
| Editorial rows total | 512 (507 cohort + 5 legacy, out of cohort) |
| Cohort rows complete (summary and verdict) | **507 / 507** |
| Empty-verdict shells | **0** |
| Identities linked to a page | 507 |
| Publications bound to approved snapshot | 507 |
| Activation status changed | **0** |

503 rows created, 4 existing rows updated in place. Existing editorial titles and slugs were
preserved; only summary, verdict, aliases, category and provenance were written.

**Decision worth your confirmation:** `occupations.category_id` is NOT NULL and the legacy
taxonomy had 7 categories that do not match the 22 SOC-derived job families the content
policy emits. I reused `Healthcare` (exact name match) and created the other 21, then
assigned all 507 cohort rows their SOC-derived family. This means the 4 pre-existing cohort
pages moved category — e.g. Accountant from `Finance` to `Business & Finance`. The 5
non-cohort legacy pages kept their original categories, so `Finance`, `Technology`,
`Creative & Design`, `Strategy` and `Research` still exist with a handful of rows each. If
you would rather the launch reuse the legacy 7, that is a re-run, not a rebuild.

## 4. Related occupations

| Check | Result |
|---|---|
| Staged rows (content run 2) | 6,470 |
| Sources covered | 507 / 507 |
| Sources with zero visible related | **0** |
| Targets outside the cohort | **0** |
| Average visible related per occupation | 12.76 |
| Occupations with ≥6 (the display cap) | 493 |

Every related target is itself in the launch cohort, so no public link can point at an
unpublished page. Targets are additionally re-checked against the publication gate and
current-score requirement at read time, so a later withdrawal degrades safely.

**Reader switched** from the hand-seeded `career_relationships` (4 rows, 3 occupations, two
of them outside the cohort) to `public_occupation_related_occupations`.

This forced an API contract change. O\*NET publishes a relatedness tier and rank and nothing
else; `skill_overlap`, `transition_difficulty` and `retraining_months` had no source for 507
occupations and were dropped rather than fabricated. `CareerRelationship` now carries
`relatedness_tier` and `relatedness_rank`. The section heading changed from "Safer adjacent
careers" to "Related occupations", because O\*NET relatedness is not a safety claim and the
old copy asserted one the data cannot support.

The reader resolves the newest content run **per occupation** rather than globally, so
regenerating content for a subset cannot blank out relations for occupations that subset
did not include.

## 5. Public surface readiness

Nothing is public, so these were verified by simulating the activation predicate read-only
rather than by activating anything.

| Surface | Result |
|---|---|
| Page resolution (identity → active page → current score) | 507 / 507 |
| Slug uniqueness | 507 distinct |
| Category assigned | 507 / 507 |
| Search aliases present | 507 / 507 (0 empty) |
| Search | trigram indexes present on title and title+aliases |
| Rankings | flows through `getOccupations`; all 507 reachable |
| Comparison | selector flows through `getOccupations`; both sides gate-checked per slug |
| Sitemap | 507 job URLs + 5 static; `/career-finder` correctly excluded |
| Admin production-score inspector | resolves all 507 |

**Two truncation defects found and fixed**, both of which would have silently dropped 7
occupations from a 507 cohort:

- `getOccupations` requested `?limit=500` against an API capped at `le=500`. Sitemap,
  rankings, compare selector and admin lists would each have shown 500 of 507. Now paginated
  through offsets, so it does not need revisiting as the cohort grows.
- The admin inspector's snapshot list was capped at `LIMIT 500`. Raised to 1,000.

Pagination also required a stable sort: `ORDER BY o.title` alone can skip or repeat rows
across pages. Now `ORDER BY o.title, o.id`. (Titles happen to be unique today — 512 of 512 —
so this was latent rather than active.)

## 6. Frontend and mobile

`npm run build` succeeds. `tsc --noEmit` clean. `eslint --max-warnings=0` clean.

Checked at 375 px against the built app:

- `/methodology` renders, the `#provisional-factors` anchor resolves, the expanded
  disclosure text is present, and there is no horizontal overflow.
- The Replacement Risk footnote layout was verified synthetically at 375 px (flex column,
  351 px wide, visible, no viewport overflow). It could not be verified on a real occupation
  page because no page is public yet — see blockers.

Two pre-existing typecheck errors on `/admin/production-scores/[snapshotId]` turned out to be
stale generated route types, not code faults; they clear after a build.

## 7. Isolation

| Protected state | Status |
|---|---|
| Active scoring model | JVS 1.0.3 (unchanged) |
| JVS 2.0.0-phase4b | registered, `is_active=false` |
| Legacy `occupation_scores` / `task_ai_scores` | 11 / 23 (unchanged) |
| Public occupations | **0** |
| Phase 5, Phase 5B runs and hashes | unchanged |
| Publication/snapshot inconsistencies | 0 |
| Archetype scoring | disabled |
| Scoring formulas, thresholds, mappings, triage rules | unchanged |

Test suite: **111 passed, 0 failed.**

## 8. Remaining blockers and items to note

**Blocking activation:** none outstanding. The stale frontend image is resolved — see §10.

**Not blocking, but you should know:**

2. **5 active editorial pages sit outside the cohort** (graphic-designer, software-developer,
   ux-researcher, cybersecurity-analyst, financial-advisor). They have no production score,
   so the publication gate keeps them invisible even if activated. Two of them
   (15-1212.00, 13-2052.00) are in the 59 occupations blocked solely by provisional
   sensitivity. Leave them unpublished; do not activate them to "round out" the launch.
3. **`career_relationships` is now dead for public reads** but still feeds `/careers`
   (career-finder), which remains excluded from launch and still on legacy scores.
4. **`education_requirement` defaulted to 2** on the 503 new rows. It is read only by
   career-finder, so no launch surface uses it. It should not be treated as a real value.
5. **The occupation-page footnote has never rendered against real data.** It is
   code-complete, typechecked and layout-tested synthetically, but the first genuine render
   happens at activation. Worth eyeballing one page immediately after.
6. **Three tests were rewritten** because they encoded the pre-authorisation world:
   `test_no_phase5_candidate_was_promoted` asserted that nothing had ever been promoted — it
   is now `test_only_the_approved_cohort_was_promoted` and asserts that the only non-fixture
   promotion is the approved one, from the approved source run, entirely within the approved
   cohort, on the engine model. Two currency tests asserted globally that currency came from
   their fixture run; they are now scoped to their own identities. No assertion was weakened
   to make a failure disappear.

## 9. What activation would do

Set `activation_status='public'` on the 507 bound publications. At that point the publication
gate opens and all 507 pages, the rankings, the sitemap and comparison become live, each
serving a JVS 2.0.0-phase4b snapshot with its provisional-factor disclosure.

**Not performed. Awaiting explicit approval.**


## 10. Frontend rebuild verification (2026-08-21)

`docker compose build frontend` and `docker compose up -d frontend`. Image rebuilt, container
recreated from it.

Served-code checks against the running container on :3000:

| Check | Result |
|---|---|
| `/methodology` carries `id="provisional-factors"` | yes |
| Disclosure names both weights (0.15 / 0.10) | yes |
| "25% of Replacement Risk weighting" present | yes |
| "estimated from structural proxies rather than measured directly" | yes |
| New strings in bundle ("Related occupations", "Closely related work", the Replacement Risk footnote, the empty state) | all present |
| Stale strings removed ("Safer adjacent careers", "Adjacent careers are being evaluated") | gone |
| Stale `occupations?limit=500"` single-page fetch | gone |
| Paginated `occupations?limit=500&offset=` in bundle | present |

Live surfaces, still pre-activation:

| Route | Status |
|---|---|
| `/`, `/rankings`, `/compare`, `/methodology`, `/about`, `/sitemap.xml` | 200 |
| `/jobs/accountant` | 404 — publication gate holding |
| `/jobs/does-not-exist` | 404 |
| `/api/v1/occupations`, `/api/v1/rankings`, `/api/v1/occupations/search` | `[]` |

Sitemap currently emits the 5 static routes and no job URLs, which is correct while nothing
is activated; the paginated fetch completes without error.

The related-occupations reader was executed against real cohort data with only the activation
check relaxed, confirming it resolves post-activation. For Accountant it returns six related
occupations — Financial Examiners, Treasurers and Controllers, Tax Preparers, Budget Analysts,
Credit Analysts, Tax Examiners — each carrying a current production score. Relatedness ranks
come back as 2, 3, 4, 6, 7, 9: O*NET's own ranks, preserved with non-cohort targets omitted
rather than renumbered.

Final state: **0 public**, 507 current snapshots, promotion `completed`, active model
JVS 1.0.3, 11 legacy rows untouched, 512 populated editorial pages. Test suite 111 passed.


## 11. Activation (2026-08-21)

Approved: keep the SOC categories, activate the 507.

`ingestion/run_public_activation.py --content-run 2 --expect-count 507`, policy
`phase6-public-activation-v1`. All-or-nothing, and it re-verifies readiness per occupation
rather than trusting the earlier audit: complete content, a current production snapshot, an
`approved_score_snapshot_id` equal to that snapshot, a verdict describing that same snapshot,
and an active editorial page with a real summary and verdict.

| Check | Result |
|---|---|
| Readiness failures | **0 of 507** |
| Rows changed | 507 |
| Previous status | 469 `staged`, 38 `review_required` |
| Public publications after | **507** |
| Public outside the approved cohort | **0** |
| Publication/snapshot inconsistencies | **0** |
| Active scoring model | JVS 1.0.3 (unchanged) |
| Legacy `occupation_scores` | 11 (unchanged) |

Reversal is available: `--deactivate` sets the cohort back to `approved`, and the run
recorded every prior status.

### Live verification

| Surface | Result |
|---|---|
| `/`, `/rankings`, `/compare`, `/methodology` | 200 |
| `/jobs/accountant`, `/jobs/statisticians`, `/jobs/nurse-practitioner` | 200 |
| `/compare/accountant-vs-tax-preparers` | 200 |
| Sitemap | **512 URLs** (507 jobs + 5 static) |
| `/api/v1/occupations` paging | 500 + 7 = **507** |
| `/api/v1/rankings?limit=1000` | 507 |

Accountant serves `JVS 2.0.0-phase4b`, category `Business & Finance`,
`provisionalWeightShare` 25.0, 21 tasks, and 6 related occupations carrying
`relatednessTier`/`relatednessRank`. The Replacement Risk footnote renders with its
`/methodology#provisional-factors` link; at 375 px it is 351 px wide, visible, with no
horizontal overflow. "Safer adjacent careers" and "Skill overlap" no longer appear anywhere.

### 38 publications carried a title-review flag

They were activated as part of the approved 507. The flags are about O*NET title wording
only — `source_title_is_taxonomic_or_exclusionary` (18), `source_title_needs_clarity_review`
(17), both (2), and one also `source_title_is_us_specific` — not content, score or evidence
problems, and `editorial_review_status` was left untouched so they stay visible in admin. The
full list is in the activation output. To pull any of them back, set that publication's
`activation_status` to `approved`.

### One product change made during activation

`/api/v1/rankings` was capped at `le=500` while 507 occupations are public, so seven were
unreachable through that endpoint. Raised to 1,000. The launch rankings page does not use it
— it reads the paginated occupations list — but the endpoint is public API.

Two integration tests were rescoped for the same underlying reason: they scanned
`?limit=100` and asserted a specific occupation appeared, which only held while the corpus
was tiny. They now page through the listing. The invariant each protects is unchanged.

Test suite after activation: **111 passed, 0 failed.**
