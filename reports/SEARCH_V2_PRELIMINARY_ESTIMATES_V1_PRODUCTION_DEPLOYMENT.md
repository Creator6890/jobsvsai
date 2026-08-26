# Search V2 + Preliminary Estimates V1 — production deployment

**Date:** 2026-08-26 · **Status:** deployed, verified, healthy · **Three faults found and fixed in flight**

## 1. What shipped

| | |
|---|---|
| Application code deployed | **`7b2c7a1`** — Search V2 + Preliminary Estimates V1 |
| Migration 036 applied from | `fee6887` (adds one index; no application code differs) |
| AdSense hardening | `77d4e4a` — see §11.3 |
| Release directories | `/opt/jobsvsai/releases/7b2c7a1`, `/opt/jobsvsai/releases/fee6887` (both retained) |

Two commits were approved and superseded before this deployment: `a1d79cf` was halted at the
Step 4 search gate (see §11), and `7b2c7a1` replaced it.

### Artifacts

| Commit | Artifact | Size | SHA-256 |
|---|---|---|---|
| `7b2c7a1cfc24b4bd5b1981d23ff07db67f9ca7e6` | `jobsvsai-7b2c7a1.tar.gz` | 2,252,978 B | `568c1ca49a61d21eda1c5479438d3b7ff4b9ab12e733a6b117b303b3c4720eaf` |
| `fee6887` | `jobsvsai-fee6887.tar.gz` | 2,253,976 B | `0be5d45baa332e306be206c17d99bf5a5d9441d9c17e678d4c4346d593346034` |

Both built with `git archive` from a clean tree at `HEAD == origin/main`, verified byte-for-byte
by SHA-256 after upload. 471/472 entries, **zero** `.env`, `.git`, `node_modules`, `.next`, key
or certificate paths. Credential scan across the release diff and the full tracked tree at both
commits: no provider tokens committed; `.env` untracked and git-ignored.

### Database backup

`/var/backups/jobsvsai/jobsvsai-20260826T122026Z.dump`, 874 MB, verified readable by
`backup-db.sh` before any migration ran. 14 backups retained; none deleted.

## 2. Migrations

| | |
|---|---|
| Before | 33 applied, 0 pending |
| Pending found in the new release | exactly 2 — `034_consumer_search_v2.sql`, `035_preliminary_occupation_estimates.sql` |
| 034 | **PASS** — applied 12:31 |
| 035 | **PASS** — applied 12:31 |
| 036 (added in flight, see §11.2) | **PASS** |
| After | **36 applied, 0 pending** |

No migration history row was hand-written. All three went through `scripts/migrate.sh`.

## 3. Estimate population

Migration 035 creates the store; it does not populate it. Population ran through the committed
deterministic workflow:

```
scoring.run_preliminary_estimates --run-version prelim-estimates-2026q3-v3 --publish
```

Dry run first, and it reconciled exactly against the approved figures before any write:

| | Expected | Dry run | Written |
|---|---|---|---|
| E1 | 59 | 59 | 59 |
| E2 | 293 | 293 | 293 |
| E3 | 38 | 38 | 38 |
| E4 | 0 | 0 | 0 |
| Insufficient | 15 | 15 | 15 |
| Total estimates | 390 | 390 | **390** |
| **External model calls** | **0** | **0** | **0** |

Estimated occupations also needed canonical pages. Two further committed, deterministic,
zero-AI steps ran:

* `ingestion.run_public_content --run-version prelim-content-2026q3-v1` → content run 4,
  1,016 occupations, 507 complete / 509 incomplete — identical to the local run.
* `ingestion.populate_estimate_occupations --content-run 4` → 385 pages created, 5 existing
  pages updated in place, 385 identities linked, **0 publications touched**.

## 4. Production invariants

The old single "507 public" invariant is retired. These are now tracked separately:

```
VERIFIED OCCUPATIONS      507     activation_status = 'public'
VERIFIED LIVE SCORES      507     current_production_occupation_scores
PRELIMINARY ESTIMATES     390     current_published_occupation_estimates
TOTAL PUBLIC/SEARCHABLE   897
INSUFFICIENT               15     all SOC 55 military occupations
OVERLAP                     0
```

Verified cohort untouched: 507 publications, 507 live scores, JVS 1.0.3 active
(`legacy-jvs-1`), promotion run 30 `phase6-promotion-2026q3-v1` completed with 507 snapshots.

Estimate store integrity: 0 duplicate active estimates, 0 inverted ranges, 0 values outside
0–100, every row carrying method, confidence and evidence source.

## 5. Search V2 corpus

| | Local | Production |
|---|---|---|
| Search terms | 62,681 | **62,681** |
| Distinct normalised terms | 50,886 | **50,886** |
| Consumer aliases | 135 | **135** |

Exact match — no variance to investigate.

## 6. Critical query results (live production)

Every query leads with the intended occupation, in one relevance order across both score
classes:

| Query | Leading result | Second |
|---|---|---|
| **`soft eng`** | **Software Developer [E1]** | Etchers and Engravers (verified) |
| **`data analyst`** | **Data Scientists [E3]** | Statisticians (verified) |
| `software developer` | Software Developer [E1] — ~75 / ~72 | — |
| `data scientist` | Data Scientists [E3] — 67–85 / 63–79 | — |
| `electrician` | Electricians [E1] — ~47 / ~33 | — |
| `cashier` | Cashiers [E2] — 52–68 / 44–56 | Gambling Change Persons [E2] |
| `data entry operator` | Data Entry Keyers [E2] — 59–75 / 55–67 | — |
| `pen tester` | Cybersecurity Analyst [E1] | Penetration Testers [E3] |
| `ML engineer` | Data Scientists [E3] | Software Developer [E1] |
| `project manager` | Project Management Specialists [E3] | *(ambiguous chooser)* |
| `web designer` | UX Researcher [E3] | — |
| `martial arts instructor` | Exercise Trainers [E2] | Coaches and Scouts [E2] |
| `teacher` | Elementary School Teachers (verified) | Secondary School Teachers |

`soft eng` never leads with Etchers and Engravers. `pen tester` never reaches a physical-testing
occupation.

## 7. Five page classes (live)

| Class | URL | Result |
|---|---|---|
| **Verified** | `/jobs/accountant` | 200 — unchanged, no estimate panel, no "Preliminary estimate" |
| **E1** | `/jobs/software-developer` | 200 — PRELIMINARY ESTIMATE, Higher-confidence, **~75 / ~72** |
| **E2** | `/jobs/cashiers` | 200 — PRELIMINARY ESTIMATE, Low-confidence, **52–68 / 44–56** |
| **E3** | `/jobs/data-scientists` | 200 — PRELIMINARY ESTIMATE, Moderate-confidence, **67–85 / 63–79**, sources named |
| **Insufficient** | `/jobs/infantry` | **404** |

Disclaimer placement verified programmatically: the preliminary status and its wording appear
**above** the first score on every estimated page. Score labels read "Estimated AI Exposure" and
"Estimated Replacement Risk". Scanned for "guessed", "verified" and "fully validated" applied to
preliminary scores — **zero occurrences**. Scanned for internal vocabulary (`staged`,
`review_required`, `provisional_input_sensitivity`) — **zero occurrences**.

## 8. Product-surface invariants

| Surface | Policy | Verified |
|---|---|---|
| Rankings | Verified only | **PASS** — 20 job links, 0 estimated slugs, no "Preliminary estimate" text |
| Career Fit | Verified only | **PASS** — `/occupations` returns 507, 0 estimated |
| Compare | Verified only (V1) | **PASS** — selector sourced from the same 507 |
| Action Plan / Transitions | Withheld for estimates | **PASS** — estimate pages state they need validated task evidence |

The exclusion is structural, not a filter: every verified read composes
`public_occupation_predicate`, which gates on `activation_status = 'public'` — a status no
estimate ever receives.

## 9. Methodology, SEO, privacy, performance

**Methodology** (`/methodology#preliminary-estimates`): verified live to distinguish verified
from preliminary, and to carry the evidence hierarchy, calibration figures, confidence/range
policy, limitations and the upgrade path. It does **not** claim estimates passed validation.

**SEO.** One canonical page per occupation, no alias duplicates, no directory page. **The
sitemap lists 507 verified pages, not 897.** Architect decision after this deployment: keep it
at the 507 verified pages for now and do not submit the 390 preliminary pages. This is an
explicit temporary SEO policy; a separate SEO audit will decide indexation for E1/E2/E3.

**Privacy.** `occupation_search_used` carries `query_result_count` and, on selection,
`selected_occupation_slug` (a published slug). No raw query text, no alternate-title text, no
freeform strings, no evidence provenance.

**Performance.** Search API over 30 live samples: **p50 133 ms, p95 279 ms**, max 469 ms.
Estimated page `/jobs/data-scientists`: 0.21 s.

## 10. AdSense and AI News

| | |
|---|---|
| AdSense meta tag | **exactly 1 in `<head>`** — `content="ca-pub-7855774194309157"` |
| AdSense loader | present, `client=ca-pub-7855774194309157`, injected via `strategy="afterInteractive"` |
| Live `<ins class="adsbygoogle">` units | **0** — manual ads OFF |
| `NEXT_PUBLIC_ADS_ENABLED` | `false` |
| `ads.txt` | `google.com, pub-7855774194309157, DIRECT, f08c47fec0942fa0` |
| AI News flags | `NEWS_INGESTION_ENABLED=false`, `NEWS_GENERATION_ENABLED=false`, `NEWS_AUTO_PUBLISH=false` |
| News cron entries | 0 |
| Gemini calls | **0** — no provider key is even present in the production environment |

This state was **broken and restored during the deployment** — see §11.3.

## 11. Three problems found, and what they say

### 11.1 `soft eng` returned Etchers and Engravers — deployment halted

The originally approved commit `a1d79cf` hit an explicit stop condition at the Step 4 gate. The
weak search tiers assigned one flat score to every term type, so the curated alias
"software engineer" tied the scraped alternate title "Soft Metal Hand Engraver" at 700 and the
order between them was arbitrary.

It had always been broken. The weak-tier fallback declined to answer whenever an *unpublished*
candidate tied the best published one, and Software Developer was unpublished — so the bug was
masked by publication state. Publishing it as an E1 estimate removed the mask. Fixed in
`7b2c7a1` by carrying term-type authority into the weak tiers, exactly as the exact tiers
already do, plus `resultOrder` so the API's class split cannot re-sort by score class.

### 11.2 `/compare` returned 500 after the content run

Not caught by the release healthcheck, which passed 24/24 **including `/compare` → 200** —
because it ran before the content run landed.

Every public occupation read hydrates related careers through a LATERAL filtering on
`identity_id` and taking `max(content_run_id)`. Every index on that table leads with
`content_run_id`, so none could serve it. Survivable at 6,470 rows; generating content for the
full 1,016-occupation corpus took it to 31,401, and the cost is per hydrated occupation:
`/occupations?limit=500` went to **8.3 s**, past the frontend fetch timeout, and `/compare`
(which loads every occupation for its selector) started failing.

Fixed by an index on `(identity_id, content_run_id)`: **8.3 s → 2.6 s**, `/compare` back to 200.
Recorded as migration `036` rather than left as a hand-applied object.

The general lesson is not "add an index". A data-volume change in one pipeline surfaced as an
outage in an unrelated page, through an N+1 hydration nobody had reason to re-examine, in the
window where the healthcheck had already passed.

### 11.3 The AdSense connection went dark — caused by this deployment

**The most serious of the three, and it was caused by the rebuild.**

`lib/ads.ts` read `process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID ?? "ca-pub-7855774194309157"`.
`??` falls back only on `null`/`undefined`. Production `.env` carried the key **present but
empty**, and compose interpolates that as `""`, so the rebuild baked an empty client ID. The
site-verification meta tag and the loader both disappeared — silently, in the middle of Google's
active review. Nothing failed: the tag was simply absent, and every other check still passed.

The previous image had been built when the key was absent rather than empty, so the `??`
fallback fired and the tag was present. The AdSense Connection V1 deployment report records both
as verified PASS, which is how the regression was identified.

Restored by setting `NEXT_PUBLIC_ADSENSE_CLIENT_ID=ca-pub-7855774194309157` in the production
`.env` (previous file backed up alongside, mode 600) and rebuilding. Verified: exactly one meta
tag in `<head>`, loader present with the right client, zero live ad units.

Hardened in code so it cannot recur: `??` → `||`, so an empty string falls back too. **An empty
string is not a configured value.**

## 12. Validation

| Gate | Result |
|---|---|
| `./scripts/run-tests.sh` | **591 passed, 3 skipped, 0 failed** |
| `npm test` | **67 passed, 0 failed** |
| `npm run lint` | clean |
| `npm run build` | succeeds |
| Pre-deploy production healthcheck | **24 passed, 0 failed** |
| Post-deploy production healthcheck | **24 passed, 0 failed** |
| Hardened healthcheck (post-release, see below) | **41 passed, 0 failed** |
| Browser QA | PASS — five page classes, desktop and 360 px, no overflow |

## 13. Open items

1. **The sitemap lists 507 pages, not 897.** It is generated from `getOccupations()`, which is
   verified-only, so estimated pages are excluded *by construction* — this was never
   implemented, not deliberately decided. The 390 estimated pages return 200, carry no
   `noindex`, and are crawlable via internal links; they are simply not submitted. Adding 390
   preliminary-content pages to the sitemap during an active AdSense review is an SEO decision
   above deployment scope, so it is left for an explicit call.
2. **The exposed Gemini credential still needs rotating.** It is not in the repository — verified
   at every deployed commit — but it was printed in an agent session. It does not block anything:
   AI News is disabled and no provider key exists in the production environment at all.
3. **Software Developers remains E1 preliminary**, not verified, per the deployment brief. It
   passes every evaluable launch gate; promoting it needs a dedicated scoring-expansion run.

## 13a. Post-release health hardening

All three faults in §11 passed every liveness check while they were live. The health check now
covers them, taking it from 24 checks to **41**:

| Added | Guards |
|---|---|
| Three semantic smoke queries, asserted on canonical **slugs** | `soft eng` → `software-developer`, `pen tester` → `cybersecurity-analyst`, `data analyst` → `data-scientists`, each also naming the documented wrong answer. Not the 187-query benchmark — that stays in the suite, not in something cron runs. |
| Related-career index presence | Migration 036's index cannot be dropped unnoticed |
| Hydration budget | `/occupations?limit=500` under a deliberately generous 6s (the regression was 8.3s; normal is ~1.8s), plus `/compare` → 200 |
| AdSense, as **two** facts | `ADSENSE CONNECTION: LIVE` reported separately from `MANUAL AD SERVING: OFF`, so "ads are off, as intended" can never mask "the publisher tag is gone" |
| Two-class invariants | verified, estimated, E1/E2/E3, overlap and insufficient tracked **separately**; verified stays 507 and is never replaced by the 897 total |
| Product policy | 0 estimated occupations reachable through `public_occupation_predicate`, which covers rankings, Career Fit and Compare in one structural assertion |

Cohort expectations are overridable (`EXPECT_VERIFIED`, `EXPECT_ESTIMATES`, `EXPECT_E1`…),
following `deploy.sh`'s existing idiom — a health check that cannot be updated without editing
it gets commented out the first time it is inconvenient.

Every new check was verified to *fail* when its invariant is broken, not merely to pass:
wrong estimate counts, a wrong publisher ID, and reverting `||` to `??` each produce a FAIL.

## 14. Rollback

Not required, and not performed. Should it become necessary:

* **Preferred: redeploy the previous application release.** Migrations 034, 035 and 036 are
  purely additive — two new tables, one materialised view, one index, and no change to any
  existing column or row. The previous release reads none of them and tolerates their presence.
  Preliminary estimate rows simply sit inert.
* `scripts/rollback.sh` restores the images recorded in `.deploy-state` at the start of each
  `update.sh` run.
* Database restore point: `/var/backups/jobsvsai/jobsvsai-20260826T122026Z.dump` (874 MB,
  verified readable). A restore would only be needed if a *destructive* fault were found, and
  nothing in this release deletes or rewrites data.
* **Do not drop the estimate tables to roll back.** They are append-only by trigger and hold the
  only record of what was shown to users.

Prior release directories are retained on disk; none were deleted.
