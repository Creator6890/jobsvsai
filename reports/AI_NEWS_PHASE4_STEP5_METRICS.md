# AI News Phase 4 — Step 5: cost and metrics analysis

Date: 2026-08-24
Scope: **Step 5 only.** Analysis and observability. No scheduler, cron, generation, public
UI, occupation links, scoring or publishing changes.

## 1. Files changed

| File | Change |
|---|---|
| `backend/app/news/metrics.py` | **new** — the derivation service |
| `backend/app/repositories/news_metrics.py` | extended: fetch attempt/success counts, mean latency, distinct items attempted, source config, candidate queue state |
| `backend/app/news/cli.py` | `cmd_metrics` rewritten as presentation only; `--json` added; the generate summary reuses the same helpers |
| `backend/tests/test_news_metrics.py` | **new** — 18 tests |

No migration. No new capture: every number derives from columns Steps 2–4 already record.

## 2. Architecture

Three layers, separated because they were not before.

```
  repositories/news_metrics.py    SQL only — counts, sums, percentiles
            │
  app/news/metrics.py             every derived value: rates, cost, projections
            │
  app/news/cli.py                 formatting only — text or JSON
```

**What already existed**: per-run counters (`news_ingestion_runs`, `news_generation_runs`),
per-item generation audit (`generation_attempts`, tokens, `generation_latency_ms`,
`generation_error_kind`), and editorial audit (`regeneration_count`, `archived_at`,
`impact_overridden_at`). Step 6 added a minimal read that computed rates **inside the CLI**.

**What Step 5 adds**: the service layer. Derivations in the CLI could not be tested without
capturing stdout, and a second consumer — the JSON export, a future admin page — would have
had to reimplement them. A test now asserts `cmd_metrics` contains no arithmetic.

## 3. Formulas

```
ingestion_success_rate   = sources_succeeded / sources_attempted

generation_success_rate  = (accepted + rejected) / attempts
provider_failure_rate    = failed / attempts
timeout_rate             = failures[kind='timeout'] / attempts
retry_rate               = (attempts - distinct_items_attempted) / attempts

tokens_per_attempt       = (input_tokens + output_tokens) / attempts
tokens_per_article       = (input_tokens + output_tokens) / accepted
estimated_spend          = input_tokens/1e6 * price_in + output_tokens/1e6 * price_out
cost_per_attempt         = estimated_spend / attempts
cost_per_article         = estimated_spend / accepted
cost_per_100_articles    = cost_per_article * 100
monthly_at_N_per_day     = cost_per_article * N * 30

semantic_acceptance      = accepted / (accepted + rejected)
editorial_acceptance     = published / (published + rejected + archived)
regeneration_rate        = articles_regenerated / articles_created
```

Four definitions carry judgement, and each could reasonably have gone the other way:

- **A rejection is a successful call.** The model answered; it said no. Counting rejections
  as failures would make a working semantic filter look like an outage.
- **Retry rate uses distinct items.** `sum(generation_attempts)` counts calls;
  `count(items attempted)` counts candidates. The difference is exactly the retries.
- **Editorial acceptance excludes draft and review_required.** Those are undecided, not
  rejected. Including them would make an editor who has not looked yet appear to be rejecting.
- **Projections use cost per *accepted* article**, so they already carry the cost of the
  rejections and failures it took to produce one.

## 4. Two honesty rules, enforced in code

**Rates are `None`, never `0`, when the denominator is zero.** A 0% failure rate for a
pipeline that has never run is a reassuring lie. `None` renders as `—`.

**Projections are withheld below 5 successful generations, not caveated.** Cost per article
from n=1 is one observation wearing a mean's clothing, and a dashboard renders numbers while
dropping footnotes. Below the threshold `cost.status` is `insufficient_data` and
`costPerArticle`, `costPer100Articles` and `monthlyProjections` are all `null`. Raw sums and
per-attempt figures are still reported — those are facts at any n.

Currency requires **both** prices. Half a price would silently omit one side, so with only
one supplied the output says so rather than under-reporting.

## 5. Data sources

| Metric | Source |
|---|---|
| fetch attempts/successes/failures | `news_ingestion_runs.sources_*` |
| entries, candidates, duplicates, window rejects | `news_ingestion_runs.items_*` |
| queue state | `news_ingest_items.status` |
| attempts, tokens, latency, failure kind | `news_ingest_items.generation_*` (033) |
| semantic verdict and confidence | `news_ingest_items.is_ai_news`, `ai_relevance_confidence` (031) |
| article lifecycle | `news_articles.status`, `archived_at`, `regeneration_count` (032) |
| impact scores | `news_articles.impact_score`, `impact_confidence` |
| prices | `NEWS_LLM_COST_PER_1M_INPUT` / `_OUTPUT`, unset by default |

## 6. Current results

```
AI NEWS METRICS · last 30 days

  No ingestion runs and no generation attempts in this window.
  Every figure below is zero because nothing has run, not because it failed.

INGESTION      Sources configured: 9 (9 enabled, 0 failing)   Fetch attempts: 0
GENERATION     Attempts: 0   Success rate: —   Latency: —
TOKENS         Total: 0
COST           INSUFFICIENT SAMPLE SIZE: 0 successful generation(s); 5 needed.
EDITORIAL      Articles created: 0
QUALITY        Semantic acceptance: —   Editorial acceptance: —
```

**Insufficient sample size. Every economic and quality question this step was built to
answer is currently unanswerable, and no number here is estimated.**

That is the accurate state, not a gap in the instrumentation:

- Production has never ingested — `NEWS_INGESTION_ENABLED=false` since deployment.
- The dev and test databases were cleaned after each supervised validation.
- Exactly **one** successful generation exists anywhere on record, from the Phase 3
  supervised run: 1,424 input + 824 output = **2,248 tokens**. All three Step 4 attempts
  failed provider-side.

The only honest projection available: at 2,248 tokens per article and 3 articles a day,
roughly **200k tokens a month**. That rests on n=1 and should be treated as an
order-of-magnitude figure, which is exactly why the tool refuses to print it as a per-article
cost.

## 7. Limitations

| Limitation | Consequence |
|---|---|
| **n=1 successful generation** | Cost per article, tokens per article and every projection are withheld. This is the binding limitation. |
| **Provider availability** | Three consecutive Step 4 failures (timeout, 504, 503) plus Phase 3's 503→429. A generation sample cannot be collected until this improves. |
| **No pricing configured** | Currency figures are unavailable until `NEWS_LLM_COST_PER_1M_*` are set. Deliberate: an invented rate looks authoritative. |
| **Quality figures are proxies** | Self-reported confidences, deterministic policy scores, and what editors did. Nothing has been validated against whether a story mattered to a reader. |
| **Editorial acceptance needs resolved articles** | Zero have been published, rejected or archived, so the rate is `None`. |
| **Window-bounded** | Everything is scoped to `--days`; runs and items outside it are excluded. |
| **No admin UI** | CLI and JSON only. `--json` returns exactly the shape a page would render. |

## 8. Recommendation

The instrumentation is complete and the plumbing is proven. **The missing input is data, not
code.**

1. **Set the pricing variables** so currency figures become available the moment a sample
   exists. Two lines in `.env`; nothing else depends on it.
2. **Run a supervised generation batch of 5–10 when the provider is healthy.** Five is the
   projection threshold, chosen so one outlier stops dominating the mean. Until then the
   economic question stays open.
3. **Do not enable scheduled generation to collect the sample.** An unattended pipeline whose
   output has been evaluated once is the wrong way to gather evidence about whether that
   output is worth having.
4. **Re-run `metrics` after the batch.** Every figure in §6 fills in automatically; no
   further instrumentation is needed.

The step's own question — *is AI News economically viable?* — cannot be answered today, and
the most useful thing this report does is say so plainly rather than produce a number from
one observation.
