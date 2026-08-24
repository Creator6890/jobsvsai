# AI News v1 — architecture

Date: 2026-08-23
Status: **Foundation built. No automated ingestion, no LLM provider, nothing published.**
Migration `029_ai_news_v1.sql`. Impact policy `news-impact-v1`.

## 1. Product goal

> Latest AI developments — and what they mean for jobs.

Every item answers three questions and nothing else:

1. **What happened?**
2. **Why does it matter for jobs?**
3. **How significant is this development for work?** — answered as `LOW`, `MEDIUM` or
   `HIGH JOBS IMPACT`.

### Why this is not a blog, and not an AI-news aggregator

A generic AI-news site competes on speed and volume; there are dozens and they are better
resourced. The only thing JobsVsAI can say that they cannot is the third question. The
target is 2–3 stories a day, each carrying a *defensible* significance reading — not a feed.

Two consequences follow, and they shape the whole design:

- **The impact reading must be derived, not asserted.** A model that outputs "high" has
  produced a judgement with no auditable basis, no way to recalibrate, and no way to explain
  a disagreement. So the model supplies evidence and JobsVsAI supplies the arithmetic.
- **We do not republish.** The page carries JobsVsAI prose and a link out. A summary that
  paraphrases the source closely is a derivative work with a citation attached to it.

## 2. Explicit separation from occupation scoring

**Jobs Impact is a news-significance indicator. It is not AI Exposure and not Replacement
Risk.** It describes one event; those describe an occupation, from O\*NET evidence, under a
different versioned methodology.

The separation is a schema fact, not a policy anyone has to remember:

- No table created by migration 029 has a foreign key into `occupations`,
  `canonical_occupation_identities`, `occupation_publications`,
  `production_occupation_score_snapshots` or `scoring_model_versions`. A test asserts this
  by querying `information_schema`, so adding one later fails the suite.
- `news_article_job_areas.job_area` is **free editorial text** ("Software Development",
  "Legal"). It is deliberately not a SOC code and not an occupation identity. Linking them
  is the single change that would create the coupling this design exists to prevent.
- Nothing in `backend/app/news/` or `backend/app/repositories/news.py` reads or writes an
  occupation table. `test_the_news_workflow_never_touches_occupation_scoring` runs a full
  create → assess → publish → override cycle and asserts the occupation counts, snapshot
  counts, publication counts, promotion runs and active model are byte-identical afterwards.

A news article can never move an occupation score, because there is no path between them.

## 3. System architecture

```
  (Phase 2)  RSS / feeds
                 |
                 v
     news_sources -> news_ingest_items          third-party material lives here
                 |        |
            dedupe    relevance                 canonical_url + content_hash (built)
                 |        |
                 v        v
        NewsGenerationProvider                  provider-neutral, one structured call
                 |
                 v
        five factors + confidence
                 |
                 v
        news-impact-v1  (deterministic)         JobsVsAI code, not the model
                 |
                 v
          news_articles (draft)                 JobsVsAI prose lives here
                 |
             admin review                       ALWAYS manual in V1
                 |
                 v
             published  ->  /news, /news/[slug], sitemap
```

Source material and JobsVsAI prose are in **different tables** and never merge.

| Module | Role |
|---|---|
| `backend/app/news/impact_policy.py` | `news-impact-v1`. Pure, no I/O. The only place weights and thresholds exist. |
| `backend/app/news/generation.py` | `NewsGenerationProvider` protocol, response validation, `NullGenerationProvider`, provider registry. |
| `backend/app/news/pipeline.py` | `NewsSourceFetcher` / `NewsDeduplicator` / `NewsRelevanceFilter` protocols; `canonicalise_url` and `content_hash` implemented. |
| `backend/app/repositories/news.py` | All data access. Holds `PUBLIC_ARTICLE_PREDICATE` and the publication guard. |
| `backend/app/api/news.py` | Public API. |
| `backend/app/api/admin_news.py` | Admin API, behind the existing `require_admin` Basic auth. |

## 4. Schema

Migration **029**, seven tables.

- **`news_sources`** — name (unique), feed_url, site_url, `source_type` (`primary` =
  the organisation that did the thing; `secondary` = journalism about it), `trust_tier` 1–5,
  enabled.
- **`news_ingest_items`** — third-party material: `external_url`, `canonical_url`,
  `original_title`, `original_excerpt`, `source_published_at`, `content_hash`, status
  (`new`/`duplicate`/`ignored`/`candidate`/`processed`). Two dedupe axes are enforced by
  constraint: `UNIQUE (canonical_url)` and `UNIQUE (source_id, content_hash)`.
- **`news_articles`** — JobsVsAI prose plus the impact record. Status
  `draft`/`review_required`/`published`/`rejected`; level `low`/`medium`/`high`. Stores the
  five raw factors so a future policy version can be back-tested without re-calling a
  provider.
- **`news_article_sources`** — article ↔ ingest item, with `is_primary`. A partial unique
  index allows at most one primary per article: the "Read original source" link is singular.
- **`news_article_tags`**, **`news_article_job_areas`** — free editorial text.

### Constraints that carry weight

- Published rows must be complete — headline, both prose fields, `impact_level`,
  `impact_score`, `impact_policy_version` and `published_at` — enforced by a table CHECK.
- An override is all-or-nothing: `impact_overridden_at` requires `impact_overridden_by` and
  a populated `automated_impact_level`. Losing who or when would make the
  automated/editorial distinction unauditable.
- Excerpts are never rendered publicly; the public schema has no field for them.

## 5. Article lifecycle

```
draft ──assess (confidence >= 0.80)──> draft ──publish──> published
  │                                                          │
  └──assess (confidence < 0.80)──> review_required           └──unpublish──> review_required
                    │
                    └──reject──> rejected
```

Publication has exactly one entry point, `repositories.news.publish()`, which calls
`publication_blockers()` first and refuses with **every** blocker at once so an editor fixes
an article in one pass rather than discovering problems one refusal at a time.

**An article may not be published unless all of:** headline present · what_happened present ·
why_it_matters_for_jobs present · impact_level present · impact_score present ·
impact_policy_version present · at least one source · not rejected.

`set_status()` refuses `published` outright, so no code path reaches public visibility while
bypassing the guard.

## 6. The Jobs Impact model

### What the provider returns

```json
{
  "headline": "...", "what_happened": "...", "why_it_matters_for_jobs": "...",
  "tags": [], "job_areas": [],
  "capability_advancement": 0, "commercial_deployability": 0,
  "breadth_of_affected_work": 0, "adoption_speed": 0,
  "human_work_reduction_potential": 0,
  "impact_confidence": 0.0, "impact_reasoning": "..."
}
```

One structured call produces the brief and the assessment together, to keep token usage
inside a free tier. **The provider never returns a level, a score, a slug, a source URL or a
publication decision.** The interface gives it no field for a source URL specifically so it
cannot fabricate a citation.

### news-impact-v1 weights

| Factor | Weight |
|---|---|
| `capability_advancement` | **30%** |
| `commercial_deployability` | **25%** |
| `breadth_of_affected_work` | **20%** |
| `adoption_speed` | **15%** |
| `human_work_reduction_potential` | **10%** |

```
score = capability_advancement        * 0.30
      + commercial_deployability      * 0.25
      + breadth_of_affected_work      * 0.20
      + adoption_speed                * 0.15
      + human_work_reduction_potential* 0.10
```

Weights sum to exactly 1, so a uniform factor value scores exactly that value — which is how
the boundary tests pin the bands through the real entry point.

**Rounding is explicit:** the weighted sum is computed in `Decimal` and rounded
`ROUND_HALF_UP` to two decimal places, the precision the column stores. Classification then
runs on that stored value, so the level shown can never disagree with the score beside it.

### Thresholds

| Score | Level |
|---|---|
| `<= 34` | **low** |
| `35 – 69` | **medium** |
| `>= 70` | **high** |

Note the gap: scores carry two decimals, so `34.01`–`34.99` falls between the written bands.
The rule applied is the literal one — **low is `score <= 34`** — so anything above 34 is
already medium. This is tested explicitly rather than left to discovery.

### Confidence policy

`impact_confidence < 0.80` moves the article to **`review_required`** and it does not become
publishable automatically. A missing confidence is treated as too low: an assessment that
cannot state how sure it is has not earned the benefit of the doubt.

### Why public pages show only the band

The numeric score is stored for auditability, future ranking, calibration and review — and
withheld from the public payload, not merely hidden in the UI. Publishing `73` next to `71`
invites readers to treat a two-point difference as meaningful on a scale that has never been
calibrated against outcomes. When there is enough published history to check whether
high-impact stories actually preceded measurable labour-market change, that decision can be
revisited. Until then the band is the honest resolution.

### Overrides

An editor can replace `impact_level`. The override never touches `automated_impact_score` or
`automated_impact_level`; if no automated assessment exists, the current values are promoted
into those columns first so "what the machine said" is always populated once an override has
occurred. Recorded: `impact_overridden_at`, `impact_overridden_by`,
`impact_override_reason`, plus the preserved automated pair. The admin editor shows both
readings side by side.

## 7. Routes

**Public** — `/news` (hero, newest first, filters All / High / Medium / Low as *links*, so
each filter is its own shareable, crawlable URL) and `/news/[slug]` (AI News eyebrow,
headline, badge, source + source date, WHAT HAPPENED, WHY IT MATTERS FOR JOBS, AFFECTED
AREAS, tags, "Read original source →", JobsVsAI publication date, and a footnote stating
that Jobs Impact is not an occupation score).

**Public API** — `GET /api/v1/news` (`impact`, `limit`, `offset`), `GET /api/v1/news/{slug}`,
`GET /api/v1/news/sitemap`. All three compose `PUBLIC_ARTICLE_PREDICATE`; draft,
review_required and rejected articles are indistinguishable from missing.

**Admin API** — under `/api/v1/admin/news`, router-level `require_admin`: list (status
filter), counts, policy, get, create, update, add source, assess impact, override impact,
publication-check, publish, reject, unpublish.

**Admin UI** — `/admin/news` (queue with Draft / Review required / Published / Rejected
counts and columns headline, source, impact, confidence, status, created),
`/admin/news/new`, `/admin/news/[articleId]` (brief editor, factor entry, override, source
attachment, publication panel listing live blockers).

## 7a. Manual article workflow (Phase 1's only path)

Phase 1 ships **no generation**, so every article is written by an editor. This is
deliberate: the whole publication workflow needs to be exercised and trusted before any
automation is pointed at it, and a manual article is a first-class article — the schema
does not treat a generated one differently.

1. `/admin/news/new` — headline, what happened, why it matters for jobs, tags, job areas.
   Creates a `draft`. `generation_provider` stays NULL, which is how a hand-written brief is
   distinguishable from a generated one forever after.
2. `/admin/news/[articleId]` → **Sources** — source name, site URL, article URL, original
   title, optional source publication date. Creates the `news_sources` row on demand and
   stores the third-party title in `news_ingest_items`, so manual sources land in exactly
   the same place the Phase 2 pipeline will put them. Attached as primary.
3. **Assess impact** — enter the five factors 0–100, a confidence and a reasoning.
   `news-impact-v1` computes score and level server-side.
   **The form has no field for a level or a score**, because letting an editor type "high"
   would bypass the model that makes the badge defensible.
4. **Editorial override** (optional) — the one audited path to a level the policy did not
   produce. Records who, when and why, and preserves the automated pair.
5. **Publish** — the button is disabled while blockers exist, but the disable is cosmetic:
   the server runs `publication_blockers()` again and returns 422 regardless of what the
   client believed. Client-side validation is never the guard.

### Why factors rather than a level

An editor entering "HIGH" produces a badge no one can later defend, recalibrate or explain.
An editor entering five factors produces a badge that is reproducible, comparable across
articles, and re-scorable when the policy improves. The override exists for the case where
the policy is genuinely wrong about a specific story — and it is recorded as a disagreement
with the model, not as a replacement for it.

## 7b. Public vs internal fields

The split is enforced by **separate Pydantic models**, not by hiding fields in the UI. The
public serialiser has no internal field to omit.

| Field | Public | Internal |
|---|---|---|
| headline, what_happened, why_it_matters_for_jobs | yes | yes |
| impact_level (LOW / MEDIUM / HIGH) | yes | yes |
| tags, job_areas | yes | yes |
| source name, source URL, original title, source published date | yes | yes |
| published_at | yes | yes |
| **impact_score** | **no** | yes |
| **impact_confidence** | **no** | yes |
| **impact_reasoning** | **no** | yes |
| **the five factors** | **no** | yes |
| **automated_impact_score / automated_impact_level** | **no** | yes |
| **override actor, time, reason** | **no** | yes |
| **status** | **no** | yes |
| **original_excerpt** (third-party text) | **no** | yes |
| generation provider / model / prompt version | no | yes |

A test asserts `impactScore`, `impactConfidence` and `impactReasoning` are absent from the
public detail payload, so a future field addition cannot leak them by accident.

## 8. Copyright and source policy

- **JobsVsAI never republishes a third-party article.** Public pages carry only JobsVsAI
  prose plus attribution and an outbound link.
- Source titles and excerpts live in `news_ingest_items` and are used for relevance
  filtering and admin context. The public schema has no field for them.
- Outbound links carry `rel="noopener noreferrer nofollow"` and `target="_blank"`.
- Provenance is stored per article: which source, which URL, which original title, which
  publication date, and — when generated — which provider, model and prompt version.
- The future pipeline should send a provider only the material needed to understand and
  summarise the development, never a full article body for reproduction.

## 9. Why Phase 1 makes no external LLM call

Not a scheduling accident — three reasons:

1. **The workflow must be trustworthy before it is automated.** Publication guards,
   override auditing and public/internal separation are the parts that matter if something
   goes wrong. Testing them against generated content would confound "is the pipeline
   correct" with "is the model any good".
2. **The impact policy must be provably independent of the provider.** `news-impact-v1` is
   a pure function over five integers, tested with no database and no network. If a provider
   had been wired in first, the temptation to let it emit a level directly would have been
   considerable, and the audit trail would never have existed.
3. **A provider is a dependency with a bill and a rate limit.** The interface, its
   validation and its failure mode can all be designed and tested without one.
   `NullGenerationProvider` **refuses** rather than returning placeholder prose: a stub that
   invented a brief would put machine-written filler into an editorial queue that cannot
   tell it apart from a real generation.

## 10. Phase 2 — ingestion (no LLM) — **IMPLEMENTED**

Built and documented in `reports/AI_NEWS_PHASE2_INGESTION.md` (migration 030, policies
`news-relevance-v1` and `news-dedupe-v1`). Nine verified free RSS feeds, deterministic URL
canonicalisation, two-axis exact dedupe, Jaccard near-duplicate detection at 0.55 over a 48h
window, a presence-based relevance prefilter with a source floor, RQ scheduling, and an admin
incoming queue. Disabled by default (`NEWS_ENABLED=false`); no schedule is active.

The sketch below is what was planned; the report above records what was actually built and
where it differed.


### RSS ingestion
Implement `NewsSourceFetcher` in the RQ worker on a schedule. Seed `news_sources` with
primary labs (OpenAI, Anthropic, Google DeepMind, Meta AI, Microsoft, NVIDIA, Mistral,
Hugging Face, robotics labs) at `trust_tier` 1 and secondary outlets (Reuters, TechCrunch,
The Verge, Ars Technica, MIT Technology Review) at 2–3. Write every entry as a
`news_ingest_item` with status `new`; let the two UNIQUE constraints reject repeats rather
than checking first.

### Deduplication
The hard axes are already enforced by the schema. `NewsDeduplicator` adds the soft axis —
several outlets covering one event — for which title-shingle similarity within a 48-hour
window over `candidate` items is a reasonable first cut. Prefer the lowest `trust_tier`
source as the primary; mark the rest `duplicate` and attach them as secondary sources.

## 11. Phase 3 — generation — **IMPLEMENTED**

Built and live-validated; see `reports/AI_NEWS_PHASE3_GEMINI.md` (migration 031, prompt
`news-generation-v1`, semantic policy `news-semantic-relevance-v1`). One structured Gemini
call per candidate returns a semantic verdict, an original brief, controlled tags and job
areas, and five impact factors that `news-impact-v1` turns into a score and level. Disabled
by default; no scheduler, no auto-publish.

The supervised run reached 3 of 5 candidates before free-tier rate limits intervened. Both
Phase 2 false positives were correctly rejected at 0.95 confidence, and the one generated
brief was factually grounded with no hallucination.

The sketch below is what was planned; the report above records what was actually built and
where it differed — notably the SDK surface, which had to change.


### Gemini free tier
Implement `GeminiGenerationProvider` with `name = "gemini"`, register it via
`register_provider`, and request JSON output. Route the response through the existing
`parse_provider_response` so validation cannot drift between providers. Configuration:

```
NEWS_ENABLED=true
NEWS_LLM_PROVIDER=gemini
NEWS_LLM_API_KEY=            # never committed
NEWS_LLM_MODEL=
NEWS_DAILY_GENERATION_LIMIT=10
NEWS_AUTO_PUBLISH=false      # must stay false
```

Run the deterministic relevance filter **before** the API call — the free tier's limit is the
binding constraint, and it should be spent on plausible candidates only. Enforce
`NEWS_DAILY_GENERATION_LIMIT` in the worker, not in the provider.

### Phase 3 scope

- `GeminiGenerationProvider` implementing `generate_news_brief`.
- **One structured call** producing brief and factor readings together, to stay inside the
  free tier.
- **Semantic relevance confirmation** — the Phase 2 filter is deterministic and cheap and
  will over-admit; a second pass can reject candidates that survived it.
- **Automated impact factor generation** feeding `news-impact-v1` unchanged. The policy does
  not learn that a provider exists.
- Still **no automatic publishing**. `NEWS_AUTO_PUBLISH` stays false; a generated article
  lands as `draft`, or `review_required` when confidence is below 0.80.

## 12. Future calibration

`news-impact-v1` weights are a reasoned starting point, not an evidence-derived model —
the same honesty the occupation methodology applies to its two provisional replacement-risk
factors. Nothing has yet checked whether high-impact stories precede measurable change in
the work they name.

Because the five raw factors are stored per article, a `news-impact-v2` can be back-tested
across the entire archive without re-calling a provider. When that happens, publish both
versions during a transition rather than silently re-scoring history, and keep
`impact_policy_version` per row so a page can always state which policy produced its badge.

The other calibration input is the override log. A factor that editors consistently correct
in the same direction is a weighting problem, and
`automated_impact_level` vs `impact_level` measures exactly that.
