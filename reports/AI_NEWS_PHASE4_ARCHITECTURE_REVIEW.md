# AI News Phase 4 — architecture review

Date: 2026-08-24
Scope: **inspection and documentation only.** No code was modified.
Reviewed at `main` @ `76200a3`. Migrations 029, 030, 031 applied.

## 0. Verified state

The brief's premises were checked rather than assumed.

| Claim | Verified |
|---|---|
| `main` at `76200a3` | yes — `feat/ai-news` was fast-forwarded; both refs identical, tree clean |
| Deployed to production | yes — `jobsvsai.com/news` returns 200 and renders the newsroom hero; `api.jobsvsai.com/api/v1/news` returns 200 |
| Occupation scoring untouched | yes — live rankings API returns **507** public occupations |
| AI News gated | yes — production `news_*` tables hold 9 seeded sources and **0** ingest items, **0** articles, **0** runs |
| Tests | **313 passed** |

The zero row counts are the strongest single signal that the gating works: the code is
deployed and reachable, and nothing has ingested or generated.

---

## 1. Database layer

Eight tables, all created by the three news migrations. No table outside the `news_*`
namespace was touched.

| Table | Cols | Idx | FKs | Migration |
|---|---|---|---|---|
| `news_sources` | 14 | 3 | 0 | 029 (+030 adds feed/health cols) |
| `news_ingest_items` | 31 | 7 | 2 | 029 (+030 relevance, +031 semantic) |
| `news_articles` | 30 | 5 | 0 | 029 |
| `news_article_sources` | 4 | 2 | 2 | 029 |
| `news_article_tags` | 2 | 1 | 1 | 029 |
| `news_article_job_areas` | 2 | 1 | 1 | 029 |
| `news_ingestion_runs` | 21 | 3 | 0 | 030 |
| `news_generation_runs` | 25 | 3 | 0 | 031 |

### Actual flow (differs from the brief's sketch)

```
 news_sources ──< news_ingest_items ──┐   (self-FK: duplicate_of_ingest_item_id)
      │                  │            │
      │                  │            └──> semantic verdict + generation state (031)
      │                  │
      │                  └──< news_article_sources >──── news_articles
      │                                                        │
 news_ingestion_runs (030)                                     ├──< news_article_tags
 news_generation_runs (031)          observability only        └──< news_article_job_areas
```

Two corrections to the brief's diagram:

- There is **no separate "candidates" table**. A candidate is `news_ingest_items` with
  `status='candidate'`; the lifecycle is a status column, not a table transition.
- There is **no separate "published news" table**. Publication is
  `news_articles.status='published'` plus `published_at`, gated by one repository function.

### Isolation

**Zero** foreign keys from any `news_*` table into `occupations`,
`canonical_occupation_identities`, `occupation_publications`,
`production_occupation_score_snapshots` or `scoring_model_versions` — verified by query, and
asserted by a test that reads `information_schema`. `job_area` is free editorial text.

### Constraints doing real work

- `news_articles`: a CHECK forbids `status='published'` without headline, both prose fields,
  impact level, score, policy version and `published_at`.
- `news_ingest_items`: `UNIQUE (canonical_url)` and `UNIQUE (source_id, content_hash)` are
  the two dedupe axes; a duplicate link implies `status='duplicate'`; a scored item must
  carry its policy version; a semantic verdict must carry its confidence.
- Override integrity: `impact_overridden_at` requires both an actor and a preserved
  `automated_impact_level`.

---

## 2. Ingestion pipeline

```
  news_sources (feed_url, feed_format, trust_tier, enabled)   <- config lives in the DB
        │
   HttpFeedFetcher            app/news/feeds.py    20s timeout, 5MB streamed cap, UA set
        │
   parse_feed                 defusedxml, RSS 2.0 + Atom, per-entry fault isolation
        │
   to_plain_text              decode-then-strip; no feed HTML is ever stored
        │
   lookback window            NEWS_LOOKBACK_HOURS (48) — entries with no date are admitted
        │
   exact dedupe               canonical_url, then (source_id, content_hash)
        │
   near dedupe                app/news/dedupe.py — Jaccard tokens+shingles, 0.55, 48h window
        │
   news-relevance-v1          app/news/relevance.py — presence-based, source floor
        │
   news_ingest_items          candidate | ignored | duplicate | new
```

**Sources are data, not code.** Nine verified RSS 2.0 feeds seeded by migration 030; adding
one is an INSERT. Anthropic and Meta AI are deliberately absent — no public feed exists.

**Failure handling** is per-source: a failure writes `last_error`, increments
`consecutive_failures`, appends to the run's `errors` array, and the run continues. Proven by
test and by the supervised live run (9/9 sources succeeded; an injected failure was isolated).

---

## 3. AI generation pipeline

```
  candidate (status='candidate', is_ai_news IS NULL)
        │
  resolve_provider()          generation_service.py — config-driven, Gemini built here only
        │
  GeminiGenerationProvider    app/news/gemini.py — the ONLY module importing the SDK
        │                     client.models.generate_content (stable surface)
        │                     system_instruction + response_schema, one call
        │
  parse_provider_response     app/news/generation.py — refuses, never coerces
        │
  ┌─────┴─────┐
  │           │
is_ai_news    is_ai_news=true
  =false        │
  │           news-impact-v1 (five factors -> score -> level)
  │             │
ignored       decide_status()  ->  draft | review_required     (never published)
(verdict kept)
```

- **Prompt**: `app/news/prompts.py`, version `news-generation-v1`, persisted on every row.
  Semantic policy versioned separately as `news-semantic-relevance-v1`.
- **Model**: `gemini-3.7-flash`, configurable. The provider deliberately uses
  `models.generate_content`, not `interactions.create` — the latter is flagged experimental
  and requires SDK ≥ 2.0.0, which caused a 400 on every call in the first live run.
- **Validation**: out-of-range factors are errors, not clamped. Unknown tags are dropped so
  one invented tag cannot cost a good brief. The schema gives the model no field for an
  impact level, status or source URL.
- **Retries**: 429/5xx/timeout only, 3 attempts, jittered backoff. Schema-invalid responses
  and safety refusals are not retried.

---

## 4. Worker architecture — **this is the blocking gap**

```
worker/main.py:
    Worker([queue], connection=redis).work(with_scheduler=False)
```

| Component | State |
|---|---|
| RQ queue + worker | present and healthy |
| Job: `fetch_news_sources` | present, correct |
| Job: `generate_news_candidates` | present, correct |
| `enqueue_ingestion` / `enqueue_generation` | present |
| **Recurring trigger** | **does not exist** |

**Can this support ingestion every 6 hours and generation daily? Not as deployed.**

Three independent reasons, all verified:

1. `with_scheduler=False` — RQ's own scheduler is explicitly disabled.
2. `rq-scheduler` is not a dependency (`requirements.txt` has only `rq>=2.5,<3`).
3. No cron entry, systemd timer or loop process exists for news anywhere in
   `scripts/`, `deploy/` or the compose files.

The jobs are correct and idempotent; **only the trigger is missing.** Today the only way to
run either is the admin button or a manual command.

Note also that RQ's built-in scheduler handles `enqueue_in`/`enqueue_at` — one-shot delays —
not cron-style recurrence. So `with_scheduler=True` alone would *not* give a 6-hourly
cadence. The realistic options are:

| Option | Cost | Notes |
|---|---|---|
| **Host cron calling `enqueue_ingestion`** | lowest | No new dependency, no new process; fits the existing `backup-db.sh` cron convention already documented in the repo |
| `rq-scheduler` package | medium | New dependency, cron syntax, needs its own process |
| Self-rescheduling job | low | Job re-enqueues itself with `enqueue_in`; drifts, and a single failure ends the chain silently |

**Recommendation: host cron.** It matches a convention the project already uses, adds no
dependency, and keeps the schedule visible outside the application.

### Concurrency

`generate_for_candidate` checks for an existing linked article before calling the provider,
and `news_article_sources` has a composite primary key, so a double-fire cannot create two
articles for one candidate. This is tested. There is **no distributed lock** preventing two
overlapping *ingestion* runs — harmless today because the UNIQUE constraints absorb repeats,
but worth knowing before a schedule exists.

---

## 5. Admin workflow

Routes: `/admin/news` (queue), `/admin/news/incoming`, `/admin/news/[articleId]`,
`/admin/news/new`. 24 admin API endpoints, all behind the existing HTTP Basic dependency.

**Can a human currently…**

| Capability | Answer |
|---|---|
| Review a candidate? | **Yes** — incoming queue shows source, tier, relevance score, matched signals, excerpt, dates, original link |
| See AI reasoning? | **Yes** — semantic verdict, confidence, reason, provider/model, tokens, on both the incoming card and the article editor |
| Approve a generated article? | **Yes** — Publish, guarded server-side; the button's disabled state is cosmetic |
| Reject it? | **Yes** |
| Edit it? | **Yes** — headline, both prose fields, tags, job areas, impact factors, editorial override |

All sixteen review surfaces the editorial workflow needs were verified present through the
real admin API.

**Missing against the Phase 4D brief:** `Regenerate` and `Archive` actions. Neither exists.
`Archive` would also need a new status — the CHECK constraint currently allows only
`draft`, `review_required`, `published`, `rejected`.

---

## 6. Public frontend and SEO

| Requirement | State |
|---|---|
| `/news`, `/news/[slug]` | present, deployed, rendering |
| Impact filters | present, server-driven as links (shareable, crawlable) |
| `title` / `description` | present |
| Canonical | present |
| OpenGraph incl. `publishedTime` | present |
| `NewsArticle` JSON-LD | present |
| Sitemap integration | present — published only, by construction |
| Headline, date, source attribution, summary, jobs explanation | present |
| **Related occupations / related careers** | **absent** |

### The one genuine architectural conflict in this brief

Phase 4E asks for **related occupations** and **related careers** on news article pages.
That is the single change the entire AI News design was built to prevent: migration 029's
opening comment, the `job_area`-is-free-text rule, and a test querying `information_schema`
all exist specifically to stop news linking into the occupation graph.

This is not an argument against ever doing it — but it cannot be done incidentally. Someone
must first decide what the link *means*: is it "this development touches work resembling this
occupation" (editorial, defensible) or "this development changed this occupation's score"
(false, and it would let news traffic imply movement in a score that never moved)?

Recommendation: implement it as a **display-time join through `job_area` text**, with no
foreign key and no write path, or defer it. Do not add a schema relationship.

---

## 7. What already works

- Full ingestion pipeline, live-validated against 9 real feeds (238 entries, 0 source failures).
- Deterministic dedupe on two schema-enforced axes plus near-duplicate detection.
- `news-relevance-v1`, calibrated against real headlines.
- Gemini generation, live-validated: 3 of 5 candidates completed; both planted false
  positives correctly rejected at 0.95 confidence; the one generated brief was factually
  grounded with no hallucination.
- `news-impact-v1` deterministic handoff, verified end to end (62.25 → medium).
- Publication guard with a single entry point; `set_status()` refuses `published`.
- Complete editorial review surfaces.
- Public pages, SEO, sitemap.
- Observability tables for both pipelines, including token accounting.
- 313 tests, including a live-LLM guard preventing the suite from calling the real API.

## 8. What is missing

| # | Gap | Severity |
|---|---|---|
| 1 | **No recurring scheduler** (§4) | blocks 4C |
| 2 | No CLI for ingestion/candidates — only the admin button and ad-hoc scripts | blocks 4A as specified |
| 3 | `Regenerate` and `Archive` actions; `Archive` needs a new status value | blocks 4D |
| 4 | Related occupations on article pages — conflicts with the isolation rule (§6) | needs a decision, not code |
| 5 | No cost estimate surface — tokens are stored, currency is not derived | blocks 4F partially |
| 6 | No admin metrics dashboard — counters exist per run, not aggregated | blocks 4F |
| 7 | No ingestion concurrency lock | low |

## 9. Technical risks

1. **Free-tier quota is the real constraint.** The supervised run sustained ~3 calls before
   429s, and kept returning 429 after a 90s backoff. Defaults are now 5/day, batch 2. A daily
   generation schedule is feasible; anything larger is not, on this tier.
2. **The 0.70 semantic threshold is unvalidated by live data.** Every real verdict returned
   0.95. The routing is proven by test at 0.62/0.699/0.70, but whether 0.70 is the *right*
   number is unknown.
3. **Near-dedupe has never seen a real duplicate.** The live sample contained no same-event
   pairs, so 0.55 remains calibrated only against constructed cases.
4. **A 48h lookback yields nothing on a normal day.** First-party labs publish every few days.
   The first scheduled run must use a wider one-off window or it will appear broken.
5. **No Atom source has been live-tested.** All nine feeds are RSS 2.0.
6. **Enabling `NEWS_ENABLED=true` in production immediately makes the admin Generate button
   live against a real key.** There is no separate "ingestion on, generation off" switch —
   one flag gates both.

Risk 6 is worth emphasising: the brief's plan is to validate ingestion *before* generation,
but the current configuration cannot express that state.

## 10. Recommended implementation order

Ordered so each step is independently reversible and the riskiest thing is last.

1. **Split the enable flag** — `NEWS_INGESTION_ENABLED` and `NEWS_GENERATION_ENABLED`, so
   ingestion can run in production while generation stays off. Prerequisite for 4A.
2. **Add the CLI** (`ingest --dry-run`, `ingest`, `candidates`) — read-mostly, no scheduler,
   makes 4A possible and is useful permanently.
3. **Run 4A in production** with a one-off 168h window, generation still disabled. Document.
4. **Add `Regenerate` and `Archive`** (4D), including the migration for the new status.
5. **Add cost derivation and an aggregated metrics view** (4F) — read-only over existing
   counters.
6. **Run 4B** — the supervised 5-candidate generation, once quota allows.
7. **Add the scheduler last** (4C), host cron, ingestion first at 6h, generation daily only
   after 4B looks right across a wider sample.
8. **Decide the related-occupations question** (§6) separately, on its merits.

`NEWS_AUTO_PUBLISH=false` should remain unchanged throughout all of the above. Nothing in
Phase 4 as scoped requires it to change.
