# AI News — First Supervised Production Generation

**Date:** 2026-08-25 · **Release:** `a6cc69481da9` · **Scope:** 2 candidates, manual, supervised

**Recommendation: FIX GENERATION QUALITY** — specifically the semantic relevance policy. The
reasoning is in §20, and it is not a tuning problem.

**No article was produced.** Candidate 25 was semantically rejected; candidate 24 failed on a
provider 503. Nothing was published, no flag was changed persistently, and no credential was
written to production.

---

## 1. Candidates selected

| ID | Source | Title | Relevance | Priority | Band |
|---|---|---|---|---|---|
| 25 | Ars Technica | AI is hitting entry-level jobs hardest, Stanford study finds | 81 | 67 | HIGH |
| 24 | OpenAI | Asana cleared 5 years of engineering work in 2 weeks with Codex | 67 | 87 | HIGH |

Both verified clean before any quota was spent: status `candidate`, **0 generation attempts**,
no semantic verdict, no article links.

Source material as stored:

- **25** — excerpt: *"Young employment in AI-impacted fields down 19% compared to more
  AI-resistant occupations."* Published 2026-08-24 21:45 UTC.
- **24** — excerpt: *"Asana used OpenAI Codex to replace an outdated testing system in two
  weeks, completing work expected to take five years for about $12K."* Published 2026-08-18
  07:00 UTC.

## 2. Why candidate 25 was generated first

It is the cleaner editorial test: independent third-party reporting of empirical labour-market
research, from a tier-2 outlet with no commercial stake in the finding. Candidate 24 outranks
it on priority (87 vs 67) but is OpenAI's own customer-success post, so a failure there would
have been ambiguous between a generation problem and a source-provenance problem. Testing the
unambiguous case first was the point.

## 3. Provider configuration

A usable Gemini credential was found in the local development `.env` — presence and length
only were inspected, never the value. Provider `gemini`, model `gemini-3.7-flash`, matching
`gemini.py`'s `DEFAULT_MODEL`.

**The credential was passed as a process-scoped `-e` override on each manual command and was
not written to production `.env`.** This diverges from the brief's suggested "stable
configuration", deliberately and for two reasons: generation must remain disabled, so nothing
scheduled could ever consume a persisted key, and writing a credential into production is a
durable security change that a two-article supervised sample does not require. It also avoided
container recreation entirely, so health never had to be re-established mid-task.

The key travelled over SSH **stdin**, never in argv or shell history, via a mode-700 runner
script that was deleted afterwards. Verified after the run: production `.env` contains **zero**
`NEWS_LLM_API_KEY` lines and **zero** `NEWS_LLM_PROVIDER` lines, and both running containers
still report `provider='null'`, `key_present=False`.

### Generation path verification (before spending quota)

Deployed `generate` supports `--item ID` (repeatable), `--batch-size`, `--triggered-by`. Safety
properties confirmed in the deployed code:

- `generation_enabled` is checked at three points before any provider invocation.
- The daily limit applies (`Daily generation limit reached` guard).
- `decide_status` is documented *"Never `published`"* and returns only `review_required` or
  `draft`.
- **Zero `publish()` call sites and zero reads of `news_auto_publish`** in
  `generation_service.py` — auto-publish is not merely false, it is unreachable from this path.
- `link_ingest_item(..., is_primary=True)` — one candidate maps to at most one article.
- Retries bounded at `MAX_ATTEMPTS = 3`, retryable only for 429/5xx/transport; credentials and
  schema-invalid responses are not retried.

## 4–7. Attempts, outcomes, latency, tokens

| | Candidate 25 | Candidate 24 |
|---|---|---|
| Run | id 1, `completed` | id 2, `failed` |
| Started | 04:21:09 UTC | 04:22:10 UTC |
| Attempts recorded | 1 | 1 |
| Provider / model | gemini / gemini-3.7-flash | gemini / gemini-3.7-flash |
| Outcome | **REJECTED** (semantic) | **FAILED** (provider) |
| Latency | 10,088 ms | 14,663 ms |
| Input tokens | 1,469 | 0 |
| Output tokens | 615 | 0 |
| Total tokens | 2,084 | 0 |
| Error kind | none | **`server_error`** — Provider server error (503) |

Candidate 24 was **not manually retried**, per the failure rule. The service's own bounded
retry policy ran and exhausted normally within 14.7 s.

## 8. Semantic verdict — candidate 25

| | |
|---|---|
| `is_ai_news` | **false** |
| `ai_relevance_confidence` | **0.95** |
| Policy | `news-semantic-relevance-v1` |
| Prompt version | `news-generation-v1` |
| Resulting status | `ignored` (verdict retained) |

Reason returned by the model, verbatim:

> "This is an academic study analyzing labor market trends and youth employment impacts rather
> than a material development in AI capabilities, model releases, or system deployments."

## 9–11. Impact factors, score, generated content

**None exist.** The prompt computes impact factors and writes the brief only when
`is_ai_news` is true (`CONTENT_RULES`: *"Step 2 — Write the brief (only when is_ai_news is
true)"*; `IMPACT_RUBRIC` likewise). Candidate 25 was rejected at Step 1, so no headline, no
`what_happened`, no jobs analysis, no tags, no job areas, no five factors, no impact
confidence, no deterministic `news-impact-v1` score and no band were produced. Candidate 24
never reached the model at all.

There is consequently **no generated content to review editorially**, and none is invented
here.

## 12. Source-fidelity findings

Not assessable — no prose was generated. The vendor-attribution test planned for candidate 24
(whether *"AI reduced five years of engineering work to two weeks"* would be properly
attributed to OpenAI/Asana rather than asserted as established fact) **remains untested**. It
is still the right test and should be the first thing checked when candidate 24 is retried.

## 13. Candidate 25 editorial recommendation

No editorial action was taken, and none is available: there is no article to accept,
regenerate or reject.

On the *decision itself*: **the rejection was policy-correct and product-wrong.**

`news-semantic-relevance-v1` defines AI news as "a material development in what AI can do or
where it is deployed". Every accept criterion is a capability or deployment change — model
release, agent capability, robotics, inference breakthrough, coding automation, deployable
system. Every reject criterion is an absence of capability change, including explicitly
"policy, opinion or think-piece posts with no accompanying development". A Stanford study
measuring AI's effect on youth employment is not a capability change. **Gemini applied the
policy faithfully, and 0.95 confidence is appropriate.**

The problem is that this is not what JobsVsAI is for. The platform answers *"how is AI likely
to affect my job, and what should I do about it?"* Empirical labour-market evidence is its
native material — which is exactly why `news-generation-priority-v1` ranked this item HIGH.

**Two deployed policies therefore encode different definitions of the product**, and the
pipeline routes its highest-priority candidates into a gate built to reject them. This is an
architectural conflict, not a threshold to nudge. It was invisible until a real generation call
was made, and finding it cost 2,084 tokens — a good trade.

## 14. Was candidate 24 attempted?

Yes. Justified because candidate 25 did not fail: the call completed in 10 s with no provider
error, no rate limiting and no safety issue. The stop rule covers a candidate that *fails after
its normal service attempts*, which describes a provider failure, not a semantic rejection.
With the provider healthy, candidate 24 was the single most informative next data point —
testing whether the semantic gate accepts capability material while rejecting labour material.

That hypothesis is **still untested**: candidate 24 failed on a 503 before reaching the model.

## 15. Candidate 24 source-attribution quality

Not assessable — the provider returned 503 and no content was generated. See §12.

## 16. Post-run metrics

From `python -m app.news.cli metrics`:

```
GENERATION
  Attempts             : 2
  Accepted / rejected  : 0 / 1
  Failed               : 1
  Success rate         : 50%   (a rejection is a successful call)
  Provider failure rate: 50%   timeouts 0%   retries 0%
  Latency mean         : 12376ms
  Latency median (p50) : 10088ms
  Latency p95 / max    : 14663ms / 14663ms
    server_error      1

TOKENS
  Input 1469   Output 615   Total 2084   Tokens/attempt 1042.0
  Tokens / article : —

COST
  No currency estimate: set NEWS_LLM_COST_PER_1M_INPUT and NEWS_LLM_COST_PER_1M_OUTPUT.
  INSUFFICIENT SAMPLE SIZE: 0 successful generation(s); 5 needed.
  Per-article figures and projections are withheld rather than estimated.

EDITORIAL
  Articles created 0 · draft 0 · review_required 0 · published 0
  rejected 0 · archived 0 · regenerated 0 · impact overrides 0

QUALITY
  Semantic acceptance  : 0%
  Editorial acceptance : —
  Impact distribution  : low 0  medium 0  high 0
  Avg confidence       : impact —   semantic 0.950
```

**The projection threshold held.** With 0 successful generations against a threshold of 5,
per-article cost and all projections were withheld rather than caveated, and pricing was
declared unavailable rather than guessed. Zero-denominator rates render as `—`, never `0%`.
The rule was not weakened.

Ingestion counters shifted from 33/4 to **32 candidates / 5 ignored** — item 25 moving to
`ignored` on the semantic verdict. That is correct behaviour, not drift.

## 17. Confirmation of zero publication

`news_articles` = **0**. Published = **0**, draft = **0**, review_required = **0**. No article
was created, so none could be published. No automatic publication path ran — and per §3 none
exists in the generation service.

## 18. Flag state after the commands

| Setting | backend | worker |
|---|---|---|
| `ingestion_enabled` | **False** | **False** |
| `generation_enabled` | **False** | **False** |
| `news_auto_publish` | **False** | **False** |
| `news_llm_provider` | `'null'` | `'null'` |
| API key present | **False** | **False** |

**No leakage.** On disk, `.env` carries each of the three flags exactly once as `false`, holds
no provider or key line, mode 600, mtime **2026-08-25 02:57:01** — unchanged since the earlier
deployment copy. No AI News cron exists anywhere. No scheduled generation or ingestion. The
temporary runner script was removed from the VPS.

## 19. Scoring integrity

| Check | Value |
|---|---|
| Public occupations | **507** |
| Live production scores | **507** |
| Active scoring model | **JVS 1.0.3** |
| Non-fixture promotion runs | 1 |
| Snapshots in run 30 | 507 |
| Legacy `occupation_scores` | 11 |
| Editorial `occupations` | 512 |
| Healthcheck | **24 passed, 0 failed** |

No scoring table changed, no model activation changed, no occupation publication state changed.

## 20. Recommendation

### FIX GENERATION QUALITY

The blocking problem is the **semantic relevance policy's definition of AI news**, not the
model, not the provider, and not the priority policy.

As deployed, `news-semantic-relevance-v1` will reject labour-market research by design. That
category is simultaneously what `news-generation-priority-v1` ranks highest and what JobsVsAI
exists to interpret. Left as is, the pipeline will spend its scarce generation budget being
told "not AI news" about precisely the stories the platform most wants, while accepting vendor
capability announcements. No amount of retrying or reordering fixes that.

The change belongs in `news-semantic-relevance-v1` (prompt version `news-generation-v1`), and
it is narrow: credible empirical evidence about AI's effect on work, employment or occupations
should be in scope, while the existing rejections — funding, appointments, sponsorships,
advertising, contentless partnerships — stay exactly as they are. The current rejection of
"policy, opinion or think-piece posts with no accompanying development" is right and should
survive; a Stanford payroll study is evidence, not a think piece, and the revised criteria need
to distinguish those two clearly or the gate will simply fail in the other direction.

I have **not** made that change — modifying the priority policy or the relevance policy was out
of scope for this task, and this one deserves its own supervised validation.

**Provider reliability is a real but secondary concern.** One 503 in two calls is a 50% failure
rate on a sample far too small to characterise, and it is consistent with the 429s seen during
Phase 3 validation. The retry policy behaved correctly — bounded, classified as
`server_error`, and it left candidate 24 fully recoverable (`status='candidate'`,
`is_ai_news` NULL, 1 attempt recorded, still first in the selection queue). This does not
warrant `FIX PROVIDER RELIABILITY` yet; it warrants more samples once the semantic policy
admits the right material.

### Suggested next steps, in order

1. Revise `news-semantic-relevance-v1` to admit empirical work/labour evidence, with test
   fixtures drawn from candidate 25 and from a think-piece that must still be rejected.
2. Re-run candidate 25 under the revised policy. It is now `ignored`; restoring it to
   `candidate` for a retry is a deliberate act and should be recorded as one.
3. Retry candidate 24 — the vendor-attribution test in §12 is still the most important
   unanswered quality question.
4. Only then continue toward the 5 successful generations needed before cost projections or
   any scheduled generation become trustworthy.

### What was not done, by instruction

No global generation enablement. No credential written to production. No cron. Nothing
published. No candidate beyond 25 and 24 attempted. Priority policy, relevance policy and
occupation scoring all unmodified. No public expansion started.
