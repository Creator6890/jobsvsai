# Gemini Provider Isolation Test

**Date:** 2026-08-25 · **Type:** diagnostic only · **Verdict: production-model capacity problem**

Three standalone probes, run outside the generation pipeline. No database write, no candidate
touched, no generation attempt consumed, no configuration changed, nothing deployed.

**Conclusion: Gemini works, the credential works, the project works, and our structured
generation request works. `gemini-3.7-flash` specifically is capacity-constrained.**

---

## Configuration under test

| | |
|---|---|
| Effective production model | **`gemini-3.7-flash`** (`NEWS_LLM_MODEL` unset → `DEFAULT_MODEL`) |
| SDK | `google-genai` 1.75.0 |
| Client deadline | 90 s |
| Billing | paid plan, ~₹1,000 credits, confirmed by the owner |

## Test 1 — minimal request, exact production model

Prompt: `"Reply with exactly: OK"`. No system instruction, no response schema, no article
content, no pipeline.

```
RESULT     : FAILURE
model      : gemini-3.7-flash
latency    : 86,534 ms
exc type   : ServerError
http status: 503
classified : kind=server_error retryable=True
message    : 503 UNAVAILABLE. {'error': {'code': 503,
             'message': 'This model is currently experiencing high demand.
                         Spikes in demand are usually temporary.
                         Please try again later.', 'status': 'UNAVAILABLE'}}
```

**Google's own error text names the cause.** A request that carries no schema, no prompt and
essentially no input still fails — so the failure cannot be attributed to our structured
output, our request size, or our prompt.

## Credential and project check

Before testing an alternate model, a metadata-only `models.list()` call — not a generation:

```
total generateContent models: 37
flash family (18): gemini-2.5-flash, gemini-2.5-flash-lite, gemini-3-flash-preview,
  gemini-3.1-flash-lite, gemini-3.5-flash, gemini-3.5-flash-lite, gemini-3.6-flash,
  gemini-3.7-flash, gemini-flash-latest, gemini-flash-lite-latest, ...
```

Two things follow. The key authenticates and enumerates models successfully, so **401/403,
credential misconfiguration and key/project mismatch are all ruled out** — the key/project
question raised after the previous session is answered, and answered in the negative.

And `gemini-3.7-flash` **is** present in the account's supported list. The model identifier is
valid and the model is provisioned; it is availability under load that is failing, not
existence or entitlement.

## Test 2 — minimal request, alternate stable Flash model

`gemini-3.6-flash`, chosen from the enumerated list as the nearest stable neighbour, avoiding
preview, lite, image and TTS variants so the comparison is like-for-like.

```
RESULT   : SUCCESS
model    : gemini-3.6-flash
latency  : 1,460 ms
tokens   : prompt=6 total=75
response : 'OK'
```

**86,534 ms failing versus 1,460 ms succeeding** — roughly 59× faster, on the same key, same
project, same SDK, same moment.

## Test 3 — real production schema on the working model

The brief's flow stops after Test 2, but one gap remained in the stated objective: structured
output was still untested, because 3.7 fails even minimally. This closes it — the **real**
`RESPONSE_SCHEMA` and the **real** `build_system_instruction()`, against a small synthetic
story (not candidate 25, nothing persisted).

```
RESULT   : SUCCESS
model    : gemini-3.6-flash
latency  : 6,358 ms
tokens   : prompt=1843 total=2785
response : {"is_ai_news":true,"ai_relevance_confidence":0.95,
            "relevance_reason":"The item provides measured enterprise trial data
              demonstrating a 25% reduction in time spent on routine software
              debugging tasks.",
            "headline":"Enterprise trial shows AI coding assistant cuts routine
              software debugging time by 25%",
            "what_happened":"An enterprise company evaluated an AI coding assistant
              during an internal trial wi...
```

Valid JSON, conforming to the schema, in 6.4 seconds. **Our generation request path is sound.**

### A secondary observation, stated carefully

The model returned `is_ai_news: true` at 0.95 confidence for a measured-productivity story,
with a reason explicitly citing *"measured enterprise trial data"*. That is encouraging for
`news-semantic-relevance-v2` — it is exactly the reasoning the v2 criteria were written to
produce.

**It is not validation of candidate 25.** The synthetic fixture describes a measured trial
inside a company, which satisfies both the deployment and the measured-outcome limbs of v2.
Candidate 25 is a labour-market study with no deployment at all — the harder case, and the one
v1 rejected. That question is still open.

## Interpretation

Against the brief's decision table:

> Production model 503 + alternate Flash SUCCESS → **current production model
> availability/capacity problem.**

| Hypothesis | Verdict |
|---|---|
| 1. Gemini generally | **Ruled out** — alternate Flash model succeeded in 1.5s |
| 2. The specific production model | **CONFIRMED** — 503 with an explicit high-demand message |
| 3. Structured output / our request | **Ruled out** — real schema succeeded in 6.4s; and 3.7 fails even with no schema at all |
| Credential / project / billing | **Ruled out** — model list succeeds, 37 models enumerated |
| Quota (429) | **Not observed** — no 429 in any probe |

The earlier reliability work also holds up. The raised deadline is not masking anything: this
503 arrived from the server with an explicit capacity message, and the 504/503 classification
split is what let the two causes be told apart at all.

## Options — not actioned

**No production configuration was changed.** The model remains `gemini-3.7-flash`.

Two paths exist, and the choice is the owner's:

1. **Wait.** Google describes the condition as temporary. Costs nothing and preserves the
   current model, but there is no visibility into when capacity returns, and four of five
   production attempts have now failed across roughly seven hours.
2. **Point `NEWS_LLM_MODEL` at `gemini-3.6-flash`.** This is already an environment variable
   with no code change required — set it in production `.env`, recreate backend and worker,
   done. Both probes on that model succeeded, including the full structured path.

Two caveats if option 2 is taken. A different model will exercise judgement differently on the
semantic verdict and the impact rubric, so it is an editorial change as well as an operational
one — the first articles would be written by a different model than the calibration work
assumed. That is mitigated by `generation_model` being recorded per item and per run, so
attribution stays intact and a later comparison is possible. And it is a `.env` change plus
container recreation, which is a small deployment rather than a restart.

## Production state after the probes

| Check | Value |
|---|---|
| Candidate 25 | `status=candidate`, `is_ai_news=NULL`, attempts **4** — unchanged |
| Candidate 24 | `status=candidate`, `is_ai_news=NULL`, attempts 1 — unchanged |
| `news_generation_runs` | 5 — **no new run created** |
| `news_articles` | 0 |
| Attempts today | 5 of 5 — **unchanged by the probes** |
| Production model | `gemini-3.7-flash` — unchanged |
| Flags | ingestion / generation / auto_publish all **False**, provider `null`, no key |
| `.env` | zero `NEWS_LLM_API_KEY` lines, mtime `2026-08-25 07:52:04` — untouched |
| Healthcheck | **24 passed, 0 failed** |

The probes ran as standalone SDK calls with the credential supplied process-scoped over SSH
stdin, never in argv, history or logs. The probe scripts were verified to contain **zero**
literal key material — they read the key from the environment — and were removed from both the
host and the container afterwards.

## What was not done, by instruction

Candidate 25 not generated, candidate 24 not touched, no generation attempt consumed, daily cap
neither altered nor spent, production model not changed, nothing deployed, nothing published,
`news-semantic-relevance-v2` not modified, AdSense untouched.
