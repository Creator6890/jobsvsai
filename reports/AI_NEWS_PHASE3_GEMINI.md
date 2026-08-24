# AI News Phase 3 — Gemini generation

Date: 2026-08-24
Status: **Implemented and live-validated on 3 of 5 planned candidates.** Disabled by default
(`NEWS_ENABLED=false`, `NEWS_LLM_PROVIDER=null`). No scheduler, no auto-publish, nothing
deployed. Migration 031. Prompt `news-generation-v1`, semantic policy
`news-semantic-relevance-v1`.

## 1. Architecture

```
candidate (Phase 2)
   -> ONE structured Gemini call
   -> semantic verdict + brief + tags + job areas + five impact factors
   -> news-impact-v1 computes score and level
   -> draft | review_required
   -> admin review -> manual publish
```

One call per candidate. Splitting relevance, summary, impact and tagging into separate calls
would multiply token spend on a free tier and give the model less context for each judgement.

`app/news/gemini.py` is the only module that imports the SDK. The service depends on the
`NewsGenerationProvider` protocol, so replacing the provider is a registry entry rather than
a change to the service, repository, API or worker.

### Three invariants, each enforced in code and asserted by test

1. **The model never decides publication.** `decide_status()` returns only `draft` or
   `review_required`; `set_status()` refuses `published` outright.
2. **The model never sets the impact level.** Only the five factors cross the provider
   boundary. A volunteered `impact_level` is ignored, and the response schema gives the model
   no field for one.
3. **One candidate, one article.** Checked before the call, so a duplicate request costs no
   quota.

## 2. SDK and model

`google-genai`, pinned `>=1.40,<2` (resolved 1.75.0).

**The provider uses `client.models.generate_content`, not `client.interactions.create`.**
This was not a preference — the first live run failed all five calls with HTTP 400:

> The legacy Interactions API schema is no longer supported. Please upgrade your google-genai
> Python SDK to version >= 2.0.0 … see interactions-breaking-changes-may-2026

The current documentation features `interactions.create`, but the SDK itself emits
`UserWarning: Interactions usage is experimental and may change in future versions`, and that
API changed incompatibly in May 2026. `generate_content` is the long-standing structured-output
surface, works on the pinned version, and is the safer dependency for code meant to run
unattended. Structured output is requested through
`GenerateContentConfig(response_mime_type="application/json", response_schema=...)`.

**Model: `gemini-3.7-flash`**, configurable via `NEWS_LLM_MODEL`. Chosen because it is a
current Gemini 3 Flash model documented for structured JSON output, fast enough to avoid
high-latency reasoning modes, and ample for 2-3 stories a day. `gemini-3.5-flash-lite` is the
cheaper fallback if volume grows, at some cost to judgement quality on the impact rubric.

## 3. Configuration and secret handling

```
NEWS_LLM_PROVIDER=gemini
NEWS_LLM_API_KEY=<secret, .env only>
NEWS_LLM_MODEL=gemini-3.7-flash
NEWS_AUTO_PUBLISH=false
NEWS_DAILY_GENERATION_LIMIT=10
NEWS_GENERATION_BATCH_SIZE=5
NEWS_LLM_TIMEOUT_SECONDS=45
```

`.env` is gitignored. `NEWS_*` had to be added to the compose `environment` blocks because
`.env` is in `.dockerignore` and is not mounted, so pydantic's `env_file` never sees it inside
a container — the key is passed by reference (`${NEWS_LLM_API_KEY:-}`) and never written to a
committed file.

The key never reaches a log, an exception message or a serialised response. `GeminiError`
messages are built from status codes and exception *types*, never from provider payloads,
because an error body can echo request material. The admin status endpoint reports
`apiKeyConfigured: true/false` and never the value. Two tests assert the key cannot leak into
an error.

## 4. Structured output and validation

The schema carries `is_ai_news`, `ai_relevance_confidence`, `relevance_reason`, the brief,
tags, job areas, five factors, `impact_confidence` and `impact_reasoning`. It deliberately has
no field for an impact level, score, status or source URL — a model that invents a source URL
has fabricated a citation, so it is given nowhere to do so.

**Nothing is silently coerced.** An out-of-range factor is an error, not a value to clamp: a
model that returns 140 for a 0-100 field misunderstood the question, and its other answers are
suspect. Unknown tags and job areas are *dropped* rather than fatal, so one invented tag
cannot cost an otherwise good brief.

Controlled vocabularies: 15 tags (cap 5), 15 job areas (cap 6), matched case-insensitively and
deduplicated.

## 5. Confidence and status

| Condition | Result |
|---|---|
| `is_ai_news = false` | no article; item becomes `ignored`, verdict retained |
| `ai_relevance_confidence < 0.70` | article, `review_required` |
| `impact_confidence < 0.80` | article, `review_required` |
| otherwise | article, `draft` |

Never `published`, at any confidence. `NEWS_AUTO_PUBLISH` must stay false.

## 6. Retry policy

429, 5xx and transport timeouts only. Three attempts, exponential backoff with jitter.
Schema-invalid responses and safety refusals are **not** retried — they fail identically on
every attempt and only burn free-tier quota.

## 7. Supervised live validation — 2026-08-24

Run on `jobsvsai_test` only, `NEWS_ENABLED=true` supplied per-process, 168h one-off ingestion
window (the 48h steady-state default yields zero candidates, as Phase 2 established). Feeds
produced 238 entries, 39 stored, 33 candidates. Five were hand-picked: two clear capability
releases, one borderline robotics story, and two known Phase 2 false positives.

### Results: 3 of 5 completed

| # | Source | Det. score | Verdict | Conf | Outcome |
|---|---|---|---|---|---|
| 1581 | OpenAI | 80 | **not AI news** | 0.95 | `ignored` — correct |
| 1590 | OpenAI | 55 | **not AI news** | 0.95 | `ignored` — correct |
| 1574 | Mistral AI | 80 | **AI news** | 0.95 | `draft`, medium (62.25) |
| 1569 | Hugging Face | 80 | — | — | failed: 503 ×2, then 429 |
| 1596 | Ars Technica | 66 | — | — | failed: 503 ×2, then 429 |

**Token usage** (only call with usage recorded): 1,424 input / 824 output = **2,248 total**
for one accepted generation. At 2-3 published stories a day plus rejected candidates, a
realistic daily figure is well under 50k tokens.

### The semantic filter did exactly its job

Both Phase 2 false positives were rejected with precise reasoning:

> **ChatGPT Ads expands across Europe** (det. 80) — "This is an advertising rollout and
> regional market expansion rather than a material change in AI technical capabilities or
> workplace automation functionality."

> **New policy ideas for the Intelligence Age** (det. 55) — "This item covers funding for
> policy research and societal resilience projects, representing a policy/grant initiative
> rather than a technical capability update, model release, or deployable product."

These are the two items the deterministic prefilter was known to over-admit. The two-stage
design — permissive keywords, semantic confirmation — worked as intended on its first live
test. Notably the advertising story carried the *highest* deterministic score (80), so keyword
strength alone would have promoted it.

### Generated article quality (Mistral Agentic Search)

Source excerpt: *"The retrieval layer that helps AI systems navigate, read, and verify
information inside even the most complex documents"*

- **Headline** — "Mistral AI Introduces Agentic Search for Complex Document Retrieval".
  Factual, names the development, no clickbait.
- **What happened** — every claim traces to the excerpt. No invented benchmarks, dates,
  pricing, availability or customers. Reworded rather than copied; only the product and
  company names are reused, which is unavoidable.
- **Why it matters for jobs** — names concrete tasks (searching internal databases, policy
  files, technical records) and roles (administrative, legal, research), and correctly frames
  the effect as **augmentation** rather than substitution. No job-loss prediction, no
  probability claim. This is the field most likely to go wrong and it came back genuinely
  useful.
- **Factors** — cap 55, deploy 75, breadth 65, speed 60, reduction 50. Internally consistent
  with the prose: a retrieval improvement is not a frontier jump, is readily deployable, and
  partially automates a task rather than replacing a role. `impact_confidence` 0.80 on a
  one-sentence excerpt is appropriately cautious.
- **Deterministic handoff verified**: 55(.30) + 75(.25) + 65(.20) + 60(.15) + 50(.10) =
  **62.25 → medium**, matching the stored score and level exactly.

**No hallucination was found.** The only mild criticism is that job areas were generous — five
of a permitted six, including "Customer Support", which is a stretch for document retrieval.
Not worth a prompt change on one observation.

### Two defects found and fixed by the live run

1. **Rejections lost their token accounting.** `parse_provider_response` returned early for
   `is_ai_news=false` without carrying usage, so rejection spend was invisible. On a
   permissive prefilter rejections are the *larger* share of traffic, so recorded spend would
   have been badly understated. Fixed, with a regression test.
2. **Test-isolation defect (pre-existing, latent).** The batch tests called
   `select_generation_candidates` with no explicit IDs, so on a database holding real
   ingested items they reached into the live queue and generated fixture articles against
   four of them. Invisible on a clean test database — and exactly what a supervised
   validation leaves behind. The fixture now parks pre-existing candidates for its duration
   and restores them.

Neither is a prompt or scoring problem. **No prompt retuning was performed and
`news-impact-v1` was not changed**; three stories is nowhere near enough to justify moving a
rubric, and nothing in the sample argued for it.

### The blocking finding: free-tier rate limits

Two candidates never completed. The pattern was 503 (server overload) on the first attempts,
then **429 rate-limit on every subsequent attempt**, including after a 90-second backoff.
Retry classification behaved correctly throughout — both are retryable, attempts stayed
bounded at three, candidates were left `candidate` and retryable, and no partial articles were
created.

But it means: **the free tier could not sustain five generation calls in one session.** The
observed capacity was roughly 3 successful calls before quota pressure set in.

That is survivable for the target volume — 2-3 published stories a day is 2-3 accepted calls
plus rejections — but it is tight, and it will not survive a batch that processes a full
incoming queue. It is the main open risk for production rollout.

## 8. Known limitations

- **Sample size is three.** Both rejections were correct and the single acceptance was good,
  but no conclusion about calibration can rest on this.
- **The 0.70 semantic-confidence threshold was never exercised.** All three verdicts came
  back at 0.95, so the `review_required` path for weak semantic confidence remains untested
  against real model output. Its value is still a guess.
- **Free-tier throughput is unproven above ~3 calls per session.**
- **No Atom source has been live-tested** (Phase 2 carry-over): all nine feeds are RSS 2.0.
- **Token usage is a single data point.** 2,248 tokens for one accepted generation; rejections
  now record usage but none has been measured since the fix.
- **`gemini-3.7-flash` free-tier eligibility is empirical**, not confirmed from documentation.

## 9. Recommendation

Phase 3 is functionally complete and behaves correctly under real conditions, including its
failure paths. Before production automation:

1. **Resolve quota.** Either confirm the paid tier, or set
   `NEWS_DAILY_GENERATION_LIMIT` low (5-8) and `NEWS_GENERATION_BATCH_SIZE` to 2-3 with
   spacing between batches. The current defaults (10 / 5) exceed what the free tier sustained.
2. **Run a second supervised batch** once quota allows, targeting the two unfinished
   candidates plus a few designed to land near 0.70 semantic confidence, so the review path
   gets exercised.
3. **Keep the scheduler off** until both are done. Ingestion cadence and generation cadence
   should be enabled separately, ingestion first.
