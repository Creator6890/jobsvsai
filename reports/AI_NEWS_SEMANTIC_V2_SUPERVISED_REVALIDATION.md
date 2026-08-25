# Candidate 25 — Paid-Tier Supervised Revalidation

**Date:** 2026-08-25 · **Release:** `d669f08` · **Outcome: PROVIDER STILL UNRELIABLE**

One supervised generation operation was run against candidate 25. It failed at the provider
with a 503. **No article was generated, so semantic-v2 remains unvalidated** and nothing was
published.

Two things did come out of it: the token-accounting fix is **confirmed working in production**,
and the raised deadline changed the failure's shape enough to rule out our own client timeout
as the cause.

---

## Paid-tier prerequisite

The owner confirmed paid Gemini billing / Tier 1 is active before this task began. That
confirmation was taken as given — billing state is not verifiable from this environment, and no
attempt was made to inspect or configure it. See §Recommendation for why it is worth
re-checking.

## Candidate state

**Before:**

| | |
|---|---|
| status | `candidate` |
| `is_ai_news` | NULL |
| `semantic_policy_version` | NULL |
| `generation_attempts` | 3 |
| article links | 0 |
| `news_articles` total | 0 |

**After:** `status=candidate`, `is_ai_news=NULL`, `generation_attempts=4`,
`generation_error_kind=server_error`, still no article. **Candidate 25 remains fully
recoverable.**

## Daily-cap state

| | |
|---|---|
| Before | **4 of 5** used (24 @ 04:22, 25 @ 08:25 and earlier) |
| Available | **exactly 1** |
| After | **5 of 5 — exhausted** |

The cap was neither raised nor bypassed. One operation was available and one was used.

## Provider result

| | |
|---|---|
| Provider / model | gemini / gemini-3.7-flash |
| Run | id 5, `failed`, `triggered_by=supervised-paid-tier-item25` |
| Total latency | **75,034 ms** |
| Internal attempts | 3 (the bounded policy, no manual retry) |
| Outcome | **FAILED** |
| Error kind | **`server_error`** — Provider server error (503) |
| Input tokens | **0** |
| Output tokens | **0** |
| Total tokens | **0** |

Started 10:55:53 UTC, ended 10:57:09 UTC.

### Timing — the deadline was not the constraint this time

Subtracting the deterministic backoff (1.5s + 3.0s) and dividing by three attempts:

| Run | Total | Per attempt | Deadline in force |
|---|---|---|---|
| **This run (503)** | 75.0s | **~23.5s** | 90.0s |
| Previous (503) | 127.0s | ~40.8s | 45.0s |
| Previous (504) | 138.2s | ~44.6s | 45.0s |

This matters. The two earlier failures ran to within a second or two of the 45-second deadline —
the signature of the client cutting the request off. **This attempt returned in ~23.5 seconds,
roughly a quarter of the 90-second budget it now had.** The provider refused quickly and of its
own accord.

So the timeout change did what it was meant to: attempts are no longer pinned at the deadline,
and the remaining failure is genuine server-side unavailability rather than our own impatience.
That is a real diagnostic advance, even though the outcome is still a failure. Under the old
45s deadline and the old classification, this run and the previous ones would have been
indistinguishable.

## Token accounting — the fix validated in production

This is the clearest positive result of the task.

Item 25 carries `generation_input_tokens=1469`, `generation_output_tokens=615` from the single
successful call back on 2026-08-25 04:21. Under the old code, a failed run against that item
re-read and re-recorded those values as its own. Run 5 failed against exactly that item:

| Run | status | failed | tokens recorded | |
|---|---|---|---|---|
| 1 | completed | 0 | 1469 / 615 | genuine usage |
| 2 | failed | 1 | 0 / 0 | no prior tokens on item 24 to inherit |
| 3 | failed | 1 | **1469 / 615** | inherited — the defect |
| 4 | failed | 1 | **1469 / 615** | inherited — the defect |
| **5** | **failed** | **1** | **0 / 0** | **fixed** |

**Run 5 recorded 0/0 where runs 3 and 4 recorded 1469/615 under identical conditions** — same
item, same failure mode, same pre-existing token values on the row. The run row now describes
only the calls it actually made.

Historical rows 3 and 4 were **not** repaired, as instructed. The sum over
`news_generation_runs` is still inflated at 4,407/1,845 against a true item-level 1,469/615, and
correcting append-only audit rows remains a separate explicit decision. Until then, do not cost
from run-row token columns; `cli metrics` reads item-level values and is unaffected.

## Semantic-v2 verdict

**None. The model was never reached.**

`is_ai_news`, `ai_relevance_confidence`, `relevance_reason` and `semantic_policy_version` are
all NULL on item 25. The generation call failed before any semantic judgement was made.

The validation question — *does semantic-v2 accept credible empirical evidence about AI
materially affecting entry-level employment?* — is therefore **still open**, for the fourth
session running. It was not forced, not simulated, and no verdict is reported here because none
exists.

`news-semantic-relevance-v2` was not modified.

## Article generated

**No.** `news_articles` = 0, published = 0. No editorial review was possible, no editorial
decision was made, and no publication was attempted. `/news` remains empty.

## Publication result

Not applicable — nothing to publish. The publication-check and admin publish action were not
invoked.

## Persistent safety state

| Setting | backend | worker |
|---|---|---|
| `ingestion_enabled` | **False** | **False** |
| `generation_enabled` | **False** | **False** |
| `news_auto_publish` | **False** | **False** |
| `news_llm_provider` | `'null'` | `'null'` |
| API key present | **False** | **False** |

Production `.env` holds **zero** `NEWS_LLM_API_KEY` lines and **zero** `NEWS_LLM_PROVIDER`
lines; mode 600, mtime **2026-08-25 07:52:04** — unchanged, so nothing was persisted. The
credential travelled over SSH stdin into a mode-700 runner and never appeared in argv, shell
history or logs; the runner was deleted and verified absent. No cron. AdSense still
`NEXT_PUBLIC_ADS_ENABLED=false`.

## Scoring integrity

| Check | Value |
|---|---|
| Public occupations | **507** |
| Live production scores | **507** |
| Active scoring model | **JVS 1.0.3** |
| Promotion run 30 snapshots | 507 |
| Legacy `occupation_scores` | 11 |
| Healthcheck | **24 passed, 0 failed** |

No AI Exposure, Replacement Risk, model-version or publication-state change.

## Recommendation

### PROVIDER STILL UNRELIABLE

Per the failure rule, generation stopped after this single 503. Candidate 24 was not touched,
no other candidate was attempted, and no configuration was altered.

The provider record now stands at **five attempts, one completed call, four failures** — one
504 and three 503s. The one success was over six hours ago.

**What changed, and what it tells us.** The reliability work was not wasted: this failure is
measurably different from the previous ones. Attempts now return in ~23.5s against a 90s budget
instead of running to a 45s wall, which rules out our client deadline as the cause and points
squarely at provider-side capacity. The 504/503 classification split would have made the same
point independently. We now know what kind of problem this is, which we did not before.

**What is worth checking before the next attempt.** A 503 on a paid Tier 1 account is not the
expected behaviour, and there are three plausible explanations I cannot distinguish from here:

1. **Billing propagation.** Newly enabled billing does not always take effect immediately for an
   existing API key. Simply waiting may resolve it.
2. **Key/project mismatch — worth ruling out first.** The credential in use is the one already
   present in the local development `.env`. If billing was enabled on a different Google Cloud
   project than the one that key belongs to, the key is still on free-tier quota and would
   behave exactly as observed. Confirming the key's project matches the billed project is
   cheap and would explain everything.
3. **Genuine regional or model capacity pressure**, in which case retrying later is the only
   remedy.

**The daily cap is now exhausted** (5 of 5), so the next attempt cannot happen before the UTC
day rolls over regardless. That is a natural pause in which to check item 2.

### Suggested next step

After confirming the API key belongs to the billed project, a single supervised
`generate --item 25` on a fresh daily budget. Candidate 25 is unchanged and still first in the
priority queue, and the open questions remain what they were: whether semantic-v2 accepts
labour-market evidence, and — after that — whether the generated brief attributes vendor claims
correctly.

### What was not done, by instruction

Exactly one candidate-specific generation operation. Candidate 24 not generated, no other
candidate generated, daily limit not raised, semantic-v2 not modified, scheduled generation not
enabled, auto-publish not enabled, no cron installed, AdSense untouched, and historical run rows
3 and 4 not repaired.
