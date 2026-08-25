# AI News — Temporary Model Switch to Gemini 3.6 Flash

**Date:** 2026-08-25 · **Type:** operational configuration change · **Scope:** model selection only

**Recommendation: READY FOR SUPERVISED CANDIDATE 25 RETRY**

Production AI News generation now resolves to `gemini-3.6-flash`. No code changed, no
migration, no deployment, no Gemini call, no candidate touched, generation still disabled.

---

## Reason for switching

`gemini-3.7-flash` is currently refusing traffic on this project with an explicit capacity
error, while every other part of the stack — credential, project, billing, SDK, and our own
structured generation request — is verifiably healthy. The switch removes the one component
that is failing, and nothing else.

It is **temporary and deliberately reversible**: `NEWS_LLM_MODEL` is an environment variable,
so removing the line returns production to the code default without touching code.

## Diagnostic evidence — gemini-3.7-flash

A minimal probe outside the generation pipeline: `"Reply with exactly: OK"`, no system
instruction, no response schema, no article content.

```
RESULT     : FAILURE
latency    : 86,534 ms
http status: 503
message    : 503 UNAVAILABLE. 'This model is currently experiencing high demand.
             Spikes in demand are usually temporary. Please try again later.'
```

The provider's own text names the cause. Because the request carried no schema and effectively
no input, the failure cannot be attributed to our prompt, our request size, or our structured
output.

A metadata-only `models.list()` call on the same key returned **37 models**, including
`gemini-3.7-flash` itself. That rules out 401/403, credential misconfiguration, key/project
mismatch and entitlement: the model exists and the account may use it. What is failing is
availability under load.

Production history is consistent: four of five generation attempts failed — one 504 and three
503s — against one successful call.

## Diagnostic evidence — gemini-3.6-flash

Same key, same project, same SDK, same moment. Selected from the enumerated supported-model
list as the nearest stable neighbour, avoiding preview, lite, image and TTS variants.

```
RESULT   : SUCCESS
latency  : 1,460 ms
tokens   : prompt=6 total=75
response : 'OK'
```

86,534 ms failing against 1,460 ms succeeding — roughly 59× faster.

## Structured-output result

The decisive test, because it exercises the real generation request rather than a toy one: the
production `RESPONSE_SCHEMA` and the production `build_system_instruction()`, against a small
synthetic story (not candidate 25, nothing persisted).

```
RESULT   : SUCCESS
model    : gemini-3.6-flash
latency  : 6,358 ms
tokens   : prompt=1843 total=2785
response : {"is_ai_news":true,"ai_relevance_confidence":0.95,
            "relevance_reason":"The item provides measured enterprise trial data
              demonstrating a 25% reduction in time spent on routine software
              debugging tasks.", ...}
```

Valid JSON conforming to the schema, in 6.4 seconds. **Our generation request path works on
this model.**

One observation, stated carefully: the model returned `is_ai_news: true` for a
measured-productivity story, reasoning from *"measured enterprise trial data"* — the reasoning
`news-semantic-relevance-v2` was written to produce. **That is not validation of candidate
25.** The fixture describes a measured trial inside a company, satisfying both v2's deployment
and measured-outcome limbs; candidate 25 is a labour-market study with no deployment, which is
the harder case and the one v1 rejected. That question stays open.

## Production environment change

One line added to the authoritative production `.env` at
`/opt/jobsvsai/releases/d669f082a56e/.env`:

```
NEWS_LLM_MODEL=gemini-3.6-flash
```

Present exactly once, with a comment block recording why it exists and that unsetting it
restores the default. Mode **600**, owner root:root — preserved. Contents were not printed.

Deliberately unchanged: **no** `NEWS_LLM_PROVIDER` line, **no** `NEWS_LLM_API_KEY` line, and
**no** `NEWS_LLM_TIMEOUT_SECONDS` line — the timeout continues to resolve to 90 from the
compose default.

### Services recreated

`docker compose up -d --no-deps --no-build backend worker`. Compose passes `NEWS_LLM_MODEL`
only to backend (line 55) and worker (line 104), so those are the only two that needed it.

| Container | id before | id after | |
|---|---|---|---|
| backend | `b046e3e382a6` | **`0ce1103e51a2`** | recreated |
| worker | `9f29a4f09890` | **`4c0b7742d492`** | recreated |
| frontend | `cb832388d797` | `cb832388d797` | untouched |
| postgres | `6ebd35ac42a6` | `6ebd35ac42a6` | untouched |
| redis | `1c6554281632` | `1c6554281632` | untouched |
| caddy | `7ea6a7a908c7` | `7ea6a7a908c7` | untouched |

No image was rebuilt and nothing was recreated for label consistency.

## Running backend and worker model

Read from inside the live containers via `get_settings()`, not inferred from `.env`:

| Setting | backend | worker |
|---|---|---|
| `NEWS_LLM_MODEL` | **`'gemini-3.6-flash'`** | **`'gemini-3.6-flash'`** |
| effective model | **gemini-3.6-flash** | **gemini-3.6-flash** |
| `NEWS_LLM_TIMEOUT_SECONDS` | **90** | **90** |

## Flags

| Setting | backend | worker |
|---|---|---|
| `ingestion_enabled` | **False** | **False** |
| `generation_enabled` | **False** | **False** |
| `news_auto_publish` | **False** | **False** |
| `news_llm_provider` | `'null'` | `'null'` |
| API key present | **False** | **False** |

Generation remains disabled. The provider stays `null` persistently — the model setting names
*which* model would be used if a supervised command enables generation process-scoped, and does
not itself enable anything. No cron. AdSense still `NEXT_PUBLIC_ADS_ENABLED=false`.

**No automatic fallback was implemented.** Zero occurrences of `fallback` in `gemini.py` or
`generation_service.py`. Model selection remains a single explicit operator choice; a silent
failover would hide exactly the signal this investigation depended on.

## Candidate 25 state

Unchanged, and unchanged by this task:

| Item | status | `is_ai_news` | attempts |
|---|---|---|---|
| **25** | **`candidate`** | **NULL** | **4** |
| 24 | `candidate` | NULL | 1 |

## No content mutation

| Table | Before | After |
|---|---|---|
| `news_sources` | 9 | 9 |
| `news_ingest_items` | 37 | 37 |
| `news_articles` | 0 | 0 |
| `news_ingestion_runs` | 1 | 1 |
| `news_generation_runs` | 5 | 5 |

Published articles: 0. No article created, no publication, no generation run.

## Scoring integrity

| Check | Value |
|---|---|
| Public occupations | **507** |
| Live production scores | **507** |
| Active scoring model | **JVS 1.0.3** |
| Promotion run 30 snapshots | 507 |
| Healthcheck | **24 passed, 0 failed** |

## Model provenance is preserved

`generation_model` is recorded per ingest item and per generation run, alongside
`generation_provider`, `generation_prompt_version` and `semantic_policy_version`. Every article
and every verdict therefore stays attributable to the model that produced it, so a later
comparison between 3.6- and 3.7-written output is possible from the data alone. Nothing about
this switch loses history.

That matters more than it might appear. A model change is an **editorial** change as well as an
operational one: the semantic verdict and the five impact factors are judgements, and a
different model will exercise them differently. The calibration work behind
`news-semantic-relevance-v2` and `news-impact-v1` was reasoned about with 3.7 in mind. Nothing
observed so far suggests 3.6 is worse — the structured probe was clean and its reasoning was
sound — but the first supervised article should be read with that in mind rather than assumed
equivalent.

## Temporary, and how to revert

This is expected to be temporary. Google described the 3.7 condition as high demand and
"usually temporary".

To revert once 3.7 capacity stabilises: delete the `NEWS_LLM_MODEL` line from production
`.env` (or set it to `gemini-3.7-flash`) and recreate backend and worker with
`up -d --no-deps --no-build backend worker`. No code change, no deployment, no migration. The
comment block in `.env` records this.

Worth re-testing 3.7 with the same cheap standalone probe before reverting, rather than
discovering its state by spending a generation attempt.

## Recommendation

### READY FOR SUPERVISED CANDIDATE 25 RETRY

Every precondition now holds: the credential and project are verified good, the model in force
is one that has answered both a minimal and a full structured request within seconds, the
timeout is 90s, the token accounting is fixed and proven in production, and candidate 25 is
untouched at `status=candidate` with `is_ai_news=NULL`.

Two notes for whoever runs it. **The daily cap is exhausted at 5 of 5** for 2026-08-25, so the
retry cannot start before the UTC day rolls over. And the open questions are unchanged and
worth stating plainly: whether v2 accepts a labour-market study with no deployment, and — only
if an article is produced — whether the brief attributes vendor claims correctly.

### What was not done, by instruction

No Gemini call, candidate 25 not generated, candidate 24 not retried, `news-semantic-relevance-v2`
and `news-generation-priority-v1` unmodified, no automatic fallback, generation not enabled
globally, no cron, nothing published, AdSense untouched, and no deployment.
