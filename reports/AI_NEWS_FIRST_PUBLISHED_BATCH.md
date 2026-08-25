# AI News — First Production Batch Attempt

**Date:** 2026-08-25 · **Release:** `26e91c0` · **Outcome: PROVIDER RELIABILITY LIMITED INITIAL BATCH**

**Recommendation: FIX PROVIDER RELIABILITY** — §18.

**Zero articles were published.** Not because of editorial or policy problems, but because
every generation call in this session failed at the provider. `/news` remains empty. No
existing safety state was changed, and the newsroom pipeline itself was never shown to be at
fault — it was never reached.

---

## 1. Initial newsroom state

Verified from production, not assumed.

| Measure | Value |
|---|---|
| `news_sources` | 9 (9 enabled, 0 failing) |
| Ingest items | 37 |
| Candidates | 32 |
| Ignored | 5 |
| Articles | **0** (draft 0, review_required 0, published 0) |
| Generation attempts (before) | 2 |
| Generation runs (before) | 2 |
| Tokens (before) | 1,469 in / 615 out |

Health 24/24, 507 public / 507 live / JVS 1.0.3, all three AI News flags false, provider
`null`, no key, `NEXT_PUBLIC_ADS_ENABLED=false`. No cron.

### Pipeline components — all present, nothing missing

Verified before spending any quota, per the critical principle:

| Component | Where |
|---|---|
| Per-item generation | `POST /admin/news/incoming/{id}/generate`, `cli generate --item` |
| Generation priority | `news-generation-priority-v1`, live |
| Semantic gate | `news-semantic-relevance-v2`, live |
| Draft / review_required creation | `decide_status`, never emits `published` |
| Editorial inspection | `GET /admin/news/{id}` |
| Pre-publish blockers | `GET /admin/news/{id}/publication-check` |
| Explicit publish | `POST /admin/news/{id}/publish` → `repositories.news.publish()` |
| Public listing / detail / sitemap | `GET /news`, `/news/{slug}`, `/news/sitemap` |
| Semantic requeue | `cli requeue --item ID` |

No second pipeline was built and none was needed.

### Top candidates by generation priority

| ID | Source | AI | Prio | Band | Title |
|---|---|---|---|---|---|
| 24 | OpenAI | 67 | **87** | HIGH | Asana cleared 5 years of engineering work in 2 weeks with Codex |
| 14 | OpenAI | 70 | 59 | MEDIUM | Advancing price-performance for developers with GPT-5.6 |
| 32 | MIT Tech Review | 61 | 59 | MEDIUM | How to encourage smarter AI use in the classroom |
| 9 | Mistral AI | 80 | 52 | MEDIUM | Agentic Search |
| 17 | OpenAI | 70 | 50 | MEDIUM | Offering Zero Data Retention for frontier models |
| 16 | OpenAI | 80 | 36 | MEDIUM | Stampli cuts launch hours by 68% using ChatGPT Work |
| 21 | OpenAI | 55 | 34 | LOW | Partnering with CodeAI |
| 18 | OpenAI | 80 | 32 | LOW | Replit expands access to software creation with GPT-5.6 |
| 22 | OpenAI | 80 | 32 | LOW | Pacing model development in an era of cyber-critical capabilities |
| 31 | Ars Technica | 46 | 32 | LOW | Microsoft Copilot reveals secret input that allowed it to be hacked |

Candidate 25 was absent because it was still `ignored` under its v1 verdict.

## 2. Candidate 25 semantic-v2 result

**Unknown — the model was never reached.**

The requeue worked exactly as designed, via the deployed operator command rather than SQL:

```
AI News · requeue for reassessment
  current semantic policy = news-semantic-relevance-v2
  Item 25 returned to the queue.
    policy      : news-semantic-relevance-v1
    is_ai_news  : False   confidence 0.95
    prior status: ignored
  generation_attempts stays at 1: the spend already happened and the daily cap still counts it.
```

Post-requeue state: `status=candidate`, `is_ai_news=NULL`, `semantic_policy_version=NULL`,
`generation_attempts=1` — the historical attempt preserved, exactly as intended.

Two generation attempts followed. **Both failed at the provider before any semantic judgement
was made.** So the central open question — whether v2 accepts the Stanford labour-market study
that v1 rejected — remains unanswered. That is the single most important thing this session
did not learn.

## 3. Candidates attempted

| # | Item | Time (UTC) | Result | Latency | Error |
|---|---|---|---|---|---|
| 1 | 25 | 08:21:08 | **FAILED** | 138,245 ms | `server_error` — 504 |
| 2 | 25 | 08:25:36 | **FAILED** | 126,995 ms | `server_error` — 503 |

Two candidates in total were touched this session (25 twice). Candidate 24 was **not**
retried — the stop rule fired first.

A 90-second pause was taken between the two attempts to let the provider settle, rather than
retrying immediately. The service's own bounded retry policy ran inside each attempt; no manual
retry loop was created.

## 4. Provider successes and failures

**0 successes, 2 failures, both provider-level `server_error`.**

Each attempt burned roughly 2 minutes of wall clock, consistent with the documented
"failing call occupies 80–140 seconds" behaviour — the 45s timeout multiplied by up to three
bounded attempts plus backoff.

Cumulative provider record across all sessions: **4 attempts, 1 completed call (a v1 semantic
rejection), 3 provider failures** — one 503, one 504, one 503. That is a **75% provider failure
rate** over the whole history, on a free tier.

### Stop rule

The brief specified halting after two consecutive provider-level failures. Both attempts
failed, so generation stopped there. One daily attempt (4 of 5 used) was deliberately left
unspent rather than gambled.

## 5–7. Articles generated, rejected, published

| | |
|---|---|
| Generated | **0** |
| Rejected editorially | 0 |
| Published | **0** |

`news_articles` is still 0, published 0, semantic verdicts 0.

## 8. Editorial reasoning

None to record. No article reached the editorial gate, so the eight quality criteria were never
applied. No editorial judgement is reported here, because none was made — inventing one would
be worse than reporting the gap.

## 9. Source-attribution observations

**Still untested, for the third session running.** The vendor-attribution question — whether a
brief built from OpenAI's own Asana case study would attribute "five years of engineering work
in two weeks" to OpenAI/Asana rather than assert it as fact — remains the most important
unanswered quality question in the newsroom. `news-semantic-relevance-v2` now instructs the
model to treat first-party evidence as the company's report rather than established fact, but
no generated text has ever been inspected against that instruction.

## 10. Impact classifications

None produced. Impact factors are computed only for accepted items, and nothing was accepted.

## 11. Token and latency metrics

From the deployed metrics command:

```
GENERATION
  Attempts             : 4
  Accepted / rejected  : 0 / 0
  Failed               : 2
  Success rate         : 0%
  Provider failure rate: 50%   timeouts 0%   retries 50%
  Latency mean         : 70821ms
  Latency median (p50) : 14663ms
  Latency p95 / max    : 126979ms / 126979ms
    server_error      2

TOKENS   input 1469 · output 615 · total 2084 · per attempt 521.0 · per article —

COST
  No currency estimate: NEWS_LLM_COST_PER_1M_INPUT / _OUTPUT not configured.
  INSUFFICIENT SAMPLE SIZE: 0 successful generation(s); 5 needed.
  Per-article figures and projections are withheld rather than estimated.

EDITORIAL  created 0 · draft 0 · review_required 0 · published 0
QUALITY    semantic acceptance — · editorial acceptance — · impact distribution 0/0/0
```

The honesty rules held: projections withheld at 0 successful generations, pricing declared
unavailable rather than guessed, and zero-denominator rates rendered `—` instead of a
reassuring `0%`.

`Accepted / rejected` reads `0 / 0` rather than `0 / 1` because requeueing item 25 cleared its
v1 verdict. That is correct: the verdict no longer exists, so it is no longer counted.

### A token-accounting defect found in passing

Runs 3 and 4 **failed and returned no usage**, yet each recorded `input_tokens=1469,
output_tokens=615` — item 25's pre-existing values, re-read rather than measured.

| Source | input | output |
|---|---|---|
| Summed over `news_generation_runs` | 4,407 | 1,845 |
| Summed over `news_ingest_items` (truth) | 1,469 | 615 |

The run-level total is inflated threefold. **The metrics surface is unaffected**, because
`repositories/news_metrics.py` aggregates token columns from `news_ingest_items`, not from run
rows — which is why the command above reports the correct 2,084. The defect is confined to the
`news_generation_runs.input_tokens` / `output_tokens` columns, and would matter to anyone who
queried run rows directly for cost.

Also noted: item 25's `generation_latency_ms` now reads 126,979 ms — the failed call's latency,
overwriting the successful call's 10,088 ms. Failure metadata overwrites success metadata on
the same item.

Neither was fixed here; the brief was explicit about not redesigning the system mid-batch.

## 12. Public URLs

None — nothing was published.

## 13. `/news` QA

| Surface | Result |
|---|---|
| `https://jobsvsai.com/news` | **200** |
| `https://api.jobsvsai.com/api/v1/news` | 200, body `[]` |
| `https://api.jobsvsai.com/api/v1/news/sitemap` | 200, body `[]` |

`/news` renders its empty state cleanly rather than erroring. Card rendering, ordering, impact
labels, excerpts, tags and job areas could not be verified because there is nothing to render.

**No leakage:** the public list is `[]` despite 33 candidates and 4 ignored items sitting in
the database, confirming that ingest items have no public route and that draft, review_required
and ignored material stays internal.

## 14. Sitemap

`https://jobsvsai.com/sitemap.xml` returns 200 with **0 `/news/` URLs**. Correct: only
published news should appear, and there is none. No draft or review-required URL is exposed. No
new SEO system was added.

## 15. Persistent flags

| Setting | backend | worker |
|---|---|---|
| `ingestion_enabled` | **False** | **False** |
| `generation_enabled` | **False** | **False** |
| `news_auto_publish` | **False** | **False** |
| `news_llm_provider` | `'null'` | `'null'` |
| API key present | **False** | **False** |

Production `.env` contains **zero** `NEWS_LLM_API_KEY` and **zero** `NEWS_LLM_PROVIDER` lines;
mtime `2026-08-25 07:52:04`, unchanged since the release deployment. The credential travelled
over SSH stdin into a mode-700 runner, never appearing in argv, history or logs, and the runner
was deleted — verified absent afterwards. No cron installed.

## 16. AdSense remains dark

`NEXT_PUBLIC_ADS_ENABLED=false`, `NEXT_PUBLIC_ADS_DEBUG=false` in the running frontend. Zero
`adsbygoogle` occurrences on `/news`. Nothing about monetisation was touched.

## 17. Scoring integrity

| Check | Value |
|---|---|
| Public occupations | **507** |
| Live production scores | **507** |
| Active scoring model | **JVS 1.0.3** |
| Promotion run 30 snapshots | 507 |
| Legacy `occupation_scores` | 11 |
| Healthcheck | **24 passed, 0 failed** |

No change to AI Exposure, Replacement Risk, scoring versions, snapshots or publication state.

## 18. Recommendation

### FIX PROVIDER RELIABILITY

This is the binding constraint, and it is now the only one with real evidence behind it.

Across four production attempts the provider has completed **one** call and failed **three** —
a 75% failure rate, all `server_error` (503/504), none of them schema or safety refusals. The
retry policy is behaving correctly: bounded at three attempts, classifying accurately, leaving
every candidate recoverable. It simply has nothing reliable to retry against. The newsroom
pipeline has never been the problem; it has never been reached.

Two compounding costs make this untenable as-is. A failing call occupies **80–140 seconds**, so
a nominal two-item batch can run past four minutes producing nothing. And because
`generation_attempts` increments on failure — correctly, since the spend is real — **provider
failures consume the same daily budget as successes**. Today four of five attempts were spent
to produce zero articles.

Concretely, in rough priority order:

1. **Move off the free tier.** Every documented failure — the Phase 3 429s, and now 503/504 —
   points at free-tier capacity rather than at the integration. This is the change most likely
   to make everything else moot.
2. **Reconsider whether failed attempts should consume the daily cap.** The current behaviour
   is defensible (a failed call still costs the provider something) but it means an unreliable
   provider silently exhausts the budget. A separate failure allowance would decouple the two.
3. **Fix the run-row token accounting** (§11) before anyone bases a cost decision on run rows.
4. **Only then** re-attempt candidate 25. The v2 semantic question and the vendor-attribution
   question are both still open, and both need a provider that answers.

### Was anything else wrong?

No. Health is 24/24, core product untouched, safety state exactly as it started, the requeue
path worked correctly on its first production use, and the metrics honesty rules held under a
zero-success sample. The one defect found (§11) was surfaced by the failures rather than caused
by them, and does not affect the metrics surface.

### What was not done, by instruction

No auto-publish, no scheduled generation, no cron, no bulk generation, nothing published
without review, no scoring change, no AdSense change, and `news-semantic-relevance-v2` was not
modified during the batch. The 8-candidate generation ceiling was never approached — 2 attempts
were made — and the daily cap was respected rather than raised.
