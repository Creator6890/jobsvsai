# AI News Phase 4 — Step 4: generation validation

Date: 2026-08-24
Scope: **Step 4 only.** No scheduler, no cron, no auto-publish, no related occupations, no
public changes.

## 1. Generation flow

```
  candidate (status='candidate', is_ai_news IS NULL)
        │
        ├── NEWS_GENERATION_ENABLED=false ──────────> skipped, provider never reached
        ├── already linked to an article ───────────> skipped, provider never reached
        ├── daily cap reached ──────────────────────> skipped, provider never reached
        │
   ONE provider call  (timed; latency recorded either way)
        │
        ├── failure ──> attempt + category + latency recorded
        │               candidate stays 'candidate', retryable
        │
        ├── is_ai_news=false ──> no article; item 'ignored'
        │                        verdict, confidence, reason, tokens retained
        │
        └── is_ai_news=true
                 │
            news-impact-v1 (five factors -> score -> level)
                 │
            decide_status()  ->  draft | review_required      never 'published'
```

The runner is `python -m app.news.cli generate`. It selects unassessed candidates by
deterministic relevance score, respects both the batch size and the daily cap, and prints a
per-item breakdown plus run-level rates.

```bash
docker compose run --rm backend python -m app.news.cli generate
docker compose run --rm backend python -m app.news.cli generate --batch-size 1
docker compose run --rm backend python -m app.news.cli generate --item 5505 --item 5506
```

**The CLI cannot publish.** `generation_service` is imported inside `cmd_generate` only, and
no part of the module references the publication path — asserted by a test on the module's
own source, because the guarantee is the absence of a capability.

## 2. Model and provider configuration

| Setting | Value | Where |
|---|---|---|
| `NEWS_GENERATION_ENABLED` | `false` | gates every path, checked in `generate_for_candidate` before the item is loaded |
| `NEWS_LLM_PROVIDER` | `null` (default) / `gemini` | `resolve_provider()` — the only place Gemini is constructed |
| `NEWS_LLM_MODEL` | `gemini-3.7-flash` | overridable |
| `NEWS_LLM_TIMEOUT_SECONDS` | `45` | passed to the SDK as `HttpOptions(timeout=…)` |
| `NEWS_GENERATION_BATCH_SIZE` | `2` | sized to observed free-tier capacity |
| `NEWS_DAILY_GENERATION_LIMIT` | `5` | counted from item attempt counters, so a crashed run cannot lose its spend |
| `NEWS_AUTO_PUBLISH` | `false` | reported by the CLI; the service has no path to `published` regardless |

`app/news/gemini.py` is the only module importing the SDK. Everything above it consumes
`GeneratedBrief`.

## 3. Prompt location

`backend/app/news/prompts.py`, version **`news-generation-v1`**, persisted on every row it
produces. Four parts: system instruction, relevance criteria, content rules, impact rubric,
plus `RESPONSE_SCHEMA` kept in the same module so the prompt text and the enforced structure
cannot drift apart. Semantic policy is versioned separately as
`news-semantic-relevance-v1`.

## 4. Cost assumptions

One successful generation has been measured, in the Phase 3 supervised run:

| | Value |
|---|---|
| Input tokens | 1,424 |
| Output tokens | 824 (derived from `total_token_count`, so reasoning tokens are counted) |
| **Total** | **2,248** |

At the target of 2–3 published stories a day, plus rejections at roughly the observed rate,
a realistic daily figure is well under 50k tokens. That is a projection from **one** data
point and should be treated as an order-of-magnitude estimate, not a budget.

Rejections cost tokens too — a fix from Phase 3 — and on a deliberately permissive prefilter
they are the larger share of traffic. Any cost model that counts only accepted articles will
understate spend.

## 5. Failure modes

Every failure is recorded against the candidate and leaves it retryable. Categories are a
stable vocabulary (`generation_error_kind`), so Step 5 can group failures without parsing
messages:

| Kind | Cause | Retried? |
|---|---|---|
| `rate_limited` | 429 | yes, bounded at 3 |
| `server_error` | 5xx | yes |
| `timeout` | transport timeout / connection | yes |
| `invalid_response` | non-JSON, schema-invalid, empty (safety refusal) | **no** — identical on retry, only burns quota |
| `credentials` | 401/403 | no |
| `provider_error` | other 4xx | no |
| `unknown` | anything unclassified | no |

A category and a message always appear together, enforced by a CHECK: a category without a
message is unactionable, a message without one is ungroupable.

### Live observations, 2026-08-24

Three real calls were made against `jobsvsai_test`. **All three failed provider-side** —
`ReadTimeout`, `504`, then `503` — the same availability trouble seen during the Phase 3
session. No successful generation was produced today.

That is a poor result for content evaluation and a good one for failure-path validation:

| Item | Attempt | Category | Latency |
|---|---|---|---|
| Google DeepMind candidate | 1 | `timeout` | 139,996 ms |
| Hugging Face candidate | 1 | `server_error` | 117,947 ms |
| Google DeepMind candidate (retry) | 2 | `server_error` | 82,721 ms |

Confirmed by inspection afterwards: both candidates were still `status='candidate'`,
`is_ai_news` still NULL, attempt counters incremented, zero articles created, zero tokens
recorded.

**The operationally important finding is latency.** A *failing* call occupies 80–140
seconds, because the 45s timeout is multiplied by up to three attempts plus jittered backoff.
A batch of two all-failing candidates took **258 seconds**. Any scheduled job in Step 6 needs
a timeout budget several minutes above the naive estimate, or it will be killed mid-batch and
leave attempts uncounted.

## 6. Data captured for Step 5

Step 5 must answer whether generated content justifies its cost and editorial effort.
Everything needed is now recorded at the point of generation:

| Question | Source |
|---|---|
| Cost per article | `generation_input_tokens` + `generation_output_tokens` per item |
| Acceptance rate | `is_ai_news = true` over `generation_attempts` |
| Rejection rate | `is_ai_news = false`, with `ai_relevance_reason` for the why |
| Regeneration rate | `news_articles.regeneration_count` (032) |
| Quality proxies | `impact_score`, `impact_confidence`, `ai_relevance_confidence` |
| Model failures | `generation_error_kind`, grouped without parsing text |
| Latency | `generation_latency_ms`, on success and failure alike |
| Model and prompt in force | `generation_model`, `generation_prompt_version` |

Migration **033** added only the two that could not be derived: latency and failure category.
Everything else already existed.

The CLI prints acceptance / rejection / failure rates and tokens-per-accepted-article per
run, because a single run is the unit an operator is deciding about.

## 7. Tests

**363 passed** (was 346; +17). The five required cases:

| # | Test | Asserts |
|---|---|---|
| 1 | `test_disabled_generation_never_calls_the_provider` | provider call count 0, no attempt recorded, no latency |
| 2 | `test_enabled_generation_turns_a_candidate_into_a_draft` | one call, article created, status `draft`, score 62.5 medium |
| 3 | `test_generated_articles_are_never_published` | with `NEWS_AUTO_PUBLISH=true` forced, status is not `published` and zero published rows exist |
| 4 | `test_a_failed_call_leaves_the_candidate_recoverable` | still `candidate`, `is_ai_news` still NULL, attempt counted |
| 5 | `test_a_candidate_cannot_produce_two_articles` | second request skipped, one link, **provider not called again** |

Plus: a second attempt after failure succeeds and clears the previous error; latency and
tokens recorded on success; rejections record reasoning and cost; failures categorised for
all four status codes; category and message always paired; batch counters reflect one
accepted / one rejected / one failed; the daily cap bounds a batch and the run row records
it; and generation never touches occupation scoring.

Tests use a provider that sleeps, so latency is a real reading rather than a rounded zero.

Frontend build: unchanged and clean.

## 8. Remaining risks

| Risk | Assessment |
|---|---|
| **Provider availability** | Three consecutive failures today, on top of the Phase 3 session's 503→429 pattern. This is now the dominant operational risk, ahead of quota. |
| **Failing calls are slow** | 80–140s each. Step 6 must budget for it explicitly. |
| **Content quality remains under-sampled** | One successful generation ever (Phase 3). The architect's question — does the output justify the cost — cannot be answered from n=1. |
| **The 0.70 semantic threshold is still unexercised live** | Every real verdict has returned 0.95. Routing is proven by test at 0.62/0.699/0.70; the value itself is still a guess. |
| **Free-tier quota** | ~3 calls per session observed. Defaults are 5/day and batch 2, sized to that. |
| **Cost model rests on one data point** | 2,248 tokens for one article. Treat as order-of-magnitude. |
| **Production is four commits behind** | `f1188f1`, `95c6b3f`, `97fa3d5` and this one, plus migrations 032 and 033 unapplied there. |

## 9. Next step

**Step 5 — cost and metrics tracking**, which is now purely a read over data the pipeline
already records. No new capture should be needed.

Before Step 6 (scheduling), two things want resolving: provider availability, and a decision
on whether to run a larger supervised batch to get the content-quality sample the architect's
question actually requires.
