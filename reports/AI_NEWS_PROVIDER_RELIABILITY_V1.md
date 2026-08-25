# AI News — Provider Reliability and Usage Accounting

**Date:** 2026-08-25 · **Scope:** provider reliability only · **Recommendation:** §11

Two defects exposed by the first supervised production batch are fixed: a per-run token
accounting bug, and a client deadline that was almost certainly causing the 504s. Nothing else
changed — no AI News redesign, no semantic-v2 change, no priority change, no provider call, no
publication.

---

## 1. Production failure evidence

Two supervised attempts on candidate 25:

| Attempt | Time (UTC) | Result | Total latency | Recorded kind |
|---|---|---|---|---|
| 1 | 08:21:08 | 504 | 138,245 ms | `server_error` |
| 2 | 08:25:36 | 503 | 126,995 ms | `server_error` |

The totals are the decisive evidence. Each attempt ran the full three-attempt retry cycle, so
subtracting the deterministic backoff (`1.5s + 3.0s`) and dividing by three gives the
per-attempt duration:

```
504 run: (138.2 - 4.5) / 3  =  ~44.6s per attempt
503 run: (127.0 - 4.5) / 3  =  ~40.8s per attempt
configured client deadline  =   45.0s
the one call that succeeded =   10.1s
```

**Every failing attempt ran to within a few seconds of the 45-second deadline, while the only
successful call in production history took 10.1 seconds.** Attempts clustered at the deadline
are the signature of the client cutting the request off, not of a provider that is down. That
matches Google's documented guidance for 504 — relax an overly restrictive client deadline —
and it is why the timeout was changed on evidence rather than on principle.

The 503 is less clear-cut. It may be genuine overload, or the same slow request surfacing
differently. The change below makes the next failure diagnosable either way.

## 2. Token-accounting defect

Confirmed in production:

| Source | input | output |
|---|---|---|
| Summed over `news_generation_runs` | **4,407** | **1,845** |
| Summed over `news_ingest_items` (truth) | **1,469** | **615** |

Runs 3 and 4 failed, returned no usage, and each recorded 1,469 / 615 — precisely the figures
from run 1's single successful call.

**Blast radius was contained.** `repositories/news_metrics.py` aggregates token columns from
`news_ingest_items`, not from run rows, so `cli metrics` reported the correct 2,084 throughout.
The inflation lived only in `news_generation_runs.input_tokens` / `output_tokens`, and would
have misled anyone costing from run rows — which is exactly what a per-run cost analysis would
do.

## 3. Root cause

`generation_service.py`, at the end of `run_generation_batch`:

```python
tokens = await ingest_repo.token_totals_for_items(session, candidates)
counters.input_tokens = tokens["input"]
counters.output_tokens = tokens["output"]
```

The run read its usage **back from the ingest items** rather than accumulating it from the
calls it made. An ingest item keeps the token counts of whatever call last succeeded on it, and
the failure path (`record_generation_failure`) writes no token columns. So any run that failed
against an already-attempted candidate silently adopted that candidate's earlier usage as its
own — and the more times a candidate was retried, the further the run-row total drifted from
reality.

### The fix

```python
counters.input_tokens = sum(o.input_tokens or 0 for o in outcomes)
counters.output_tokens = sum(o.output_tokens or 0 for o in outcomes)
```

`ItemOutcome.input_tokens` / `output_tokens` are set only on the success path, from the brief
the provider actually returned; the failure path leaves them `None`. Summing over this run's
outcomes therefore means a failed call contributes zero and **every run row describes exactly
the calls it made**.

`token_totals_for_items` had exactly one caller and no test references, so it was removed
rather than left as a loaded gun. A test asserts it is gone.

Historical production rows were **not** rewritten — out of scope, and not approved.

## 4. Timeout: before and after

| | Before | After |
|---|---|---|
| `DEFAULT_TIMEOUT_SECONDS` (gemini.py) | 45.0 | **90.0** |
| `news_llm_timeout_seconds` (config) | 45 | **90** |
| `.env.example` / `.env.production.example` | 45 | **90** |
| `docker-compose.yml` default | `:-45` | **`:-90`** |
| Worst case per candidate | ~139s | **~275s** |

90 seconds is roughly nine times the observed successful latency, and the worst case stays
under five minutes for a single candidate. A test asserts that bound, so the value cannot drift
into unlimited waiting.

This is the smallest defensible adjustment: it does not remove the deadline, does not change
`MAX_ATTEMPTS`, and does not touch the model. `NEWS_LLM_TIMEOUT_SECONDS` remains the operator
override.

**The model was not changed.** Gemini 3.7 Flash is GA and there is no evidence implicating it —
the same model returned a clean 10.1s response earlier the same day.

## 5. Retry behaviour

The existing policy was already correct and is preserved: `MAX_ATTEMPTS = 3`, exponential
backoff `1.5 × 2^(n-1)` with `random.uniform(0, 0.5)` jitter so a batch does not retry in
lockstep, and a terminating loop with no `while True`.

| Class | Retryable | `kind` |
|---|---|---|
| 429 / ResourceExhausted / RateLimit | yes | `rate_limited` |
| **504 / DeadlineExceeded** | yes | **`timeout`** (was `server_error`) |
| 500, 502, 503 and other 5xx | yes | `server_error` |
| Transport: Timeout, Connection, Unavailable | yes | `timeout` |
| 401 / 403 | **no** | `credentials` |
| Other 4xx | **no** | `provider_error` |
| Schema-invalid, safety refusal | **no** | `invalid_response` |
| Anything else | **no** | `unknown` |

**One change: 504 is now recorded as `timeout` rather than `server_error`.** The two demand
different operator responses — a 503 means wait for the provider, a 504 means the request did
not finish inside the deadline it was given, which is a knob on our side. Both remain
retryable, and the change reuses the existing stable `generation_error_kind` vocabulary rather
than introducing a value, so no schema or grouping logic moves.

Had this classification existed during the batch, the first failure would have been recorded as
`timeout` and the deadline would have been the obvious suspect immediately.

Credential errors still never echo the provider's message, which can contain request material.

## 6. Daily-cap behaviour — documented, not changed

Unchanged, deliberately.

`_todays_call_count` sums `generation_attempts` on the items rather than reading run rows,
"so a crashed run cannot lose its spend". `record_generation_failure` increments
`generation_attempts`, so **a provider failure consumes daily capacity exactly as a success
does**.

That is defensible as runaway protection: a failing provider cannot be retried indefinitely
inside one day, and a call that reached the provider plausibly cost something even when it
returned an error. It is also what bit this batch — four of five attempts were spent producing
zero articles.

No concrete defect exists in the implementation, so per the brief it was left alone. **If a
separate logical-success cap is wanted later, that is a distinct decision** — the shape would be
a second counter over accepted-or-rejected outcomes, leaving the attempt counter as the
runaway guard. Not recommended without more evidence that failures are common in steady state.

## 7. Paid-tier readiness

**No code branches on billing tier.** Verified by search and pinned by a test: neither
`gemini.py` nor `generation_service.py` contains `free_tier`, `is_free`, `paid_tier` or
`billing`. The same integration serves both, and enabling billing on the API project requires
no code change.

The free-tier-shaped values are **configuration defaults, not assumptions**:
`NEWS_DAILY_GENERATION_LIMIT=5` and `NEWS_GENERATION_BATCH_SIZE=2`. Raising them after billing
is active is an environment change, not a deploy of new logic. They were left at their current
values here.

Credentials remain unpersisted: production `.env` holds no `NEWS_LLM_API_KEY` and no
`NEWS_LLM_PROVIDER`, and supervised process-scoped credentials over stdin continue to work
unchanged.

## 8. Cost configuration

Pricing is already operator-supplied and stays that way: `news_llm_cost_per_1m_input` and
`_output` are `float | None` defaulting to `None`, read only by `app/news/metrics.py`. Nothing
is hard-coded into business logic, which is correct — published rates move, and a constant
would go stale silently.

Both env templates now document the Gemini 3.7 Flash paid Standard rates as commented guidance
— **0.75 per 1M input tokens, 3.75 per 1M output tokens (thinking tokens count as output), for
the period ending 2026-12-31** — with the values still blank. A test asserts both settings
resolve to `None`, so pricing is not silently activated.

Filling them in turns on currency reporting; it does not change what is spent.

## 9. Tests

**495 passed, 0 failed** via `./scripts/run-tests.sh`. Baseline 465; 30 added in
`backend/tests/test_news_provider_reliability.py`. No existing test changed behaviour.

Covering the eight required cases:

1. **Successful run records its own usage** — 1,469/615 from one accepted outcome.
2. **Failed run does not inherit old item tokens** — the production defect reproduced exactly,
   plus a three-run sequence (one success, two failures) asserting the total is 1,469/615 and
   not the 4,407/1,845 that production recorded. A further test asserts the *mechanism* is
   gone: `token_totals_for_items` is absent from the service and from the repository, and the
   outcome-summing expression is present.
3. **503 retryable** as `server_error`.
4. **504 retryable** as `timeout`, distinct from 503, and also matched by exception type name.
5. **Timeout bounded** — 90.0 in both the provider and settings, with worst case asserted under
   300s, and the per-provider override still honoured.
6. **Semantic rejection is not a provider failure** — a rejection is a completed call carrying
   usage and no `error_kind`.
7. **Generation-disabled path reaches no provider** — `generation_enabled` checked at three
   points.
8. **Auto-publish impossible** — zero `.publish(` call sites, no `news_auto_publish` read,
   `decide_status` cannot emit `published`.

Plus: non-retryable 4xx and credential handling, credential messages never echoing the
provider, bounded-loop and jitter assertions, no tier branching, and pricing left inactive.

**No provider call was made at any point in this task.**

## 10. Migration and deployment requirements

**Migration: none.** No schema change. `generation_error_kind` already accepts `timeout` as
part of its existing vocabulary, and the token columns are unchanged. Highest migration remains
`033`.

**Deployment: required for the fixes to take effect, and not performed here.** The changes are
in backend Python plus `docker-compose.yml`, so the next release needs a normal artifact
deployment. Two notes for whoever runs it:

- `docker-compose.yml` changed (`NEWS_LLM_TIMEOUT_SECONDS` default), so backend and worker will
  be recreated.
- Production `.env` does **not** currently set `NEWS_LLM_TIMEOUT_SECONDS`, so it will pick up
  the new 90s compose default automatically. No `.env` edit is needed.

Historical run rows keep their inflated token values until someone decides to correct them;
that was explicitly out of scope.

## 11. Recommendation

### READY FOR PAID-TIER SUPERVISED RETRY

Both defects the production batch exposed are fixed, the fixes are covered by tests that
reproduce the original failures, and neither required a schema change. The retry policy, the
daily cap and the safety surface are unchanged, which is the right outcome — they were not
where the problem was.

Two honest caveats.

**The timeout change is well-evidenced but unproven.** Attempts pinned at 44.6s and 40.8s
against a 45s deadline are a strong signal, and Google's guidance points the same way, but
whether 90s actually converts those failures into successes can only be settled by a real call.
If the next attempt still returns 504 at ~90s, the deadline was not the constraint and the
question moves to the request itself.

**The 503 may be unrelated.** It could be genuine overload, in which case paid Tier 1 capacity
is the fix rather than anything in this change. The new `timeout` classification is what will
let the next failure distinguish the two, which is most of why it was worth making.

### Before the supervised retry

1. **Confirm with the operator that paid billing / Tier 1 is active.** Not verifiable from
   here, and not something to configure on their behalf.
2. Deploy this commit — the fixes are inert until then.
3. Retry candidate 25 as a single supervised `generate --item 25`. The v2 semantic verdict on
   labour-market evidence is still unknown, and remains the most valuable open question.
4. Watch the recorded `generation_error_kind` if it fails again: `timeout` points at the
   deadline or the request, `server_error` at provider capacity.

Note the daily cap will have reset by then, but any attempts already spent that day still
count.

### What was not done, by instruction

No Gemini call. Candidate 25 not requeued again, candidate 24 not retried, nothing published,
generation not enabled globally, no cron, no AdSense change, `news-semantic-relevance-v2` and
`news-generation-priority-v1` both untouched, and no deployment.
