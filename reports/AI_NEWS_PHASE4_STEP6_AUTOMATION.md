# AI News Phase 4 — Step 6: controlled automation layer

Date: 2026-08-24
Scope: **Step 6 only.** No cron installed, no auto-publishing, no occupation relationships,
no frontend scheduler UI.

## 0. A correction to the brief

The brief lists **Step 5 (metrics) as completed**. It was not: there is no Step 5 commit, no
Step 5 report, and no `metrics` command existed. The last commit before this one was Step 4
(`5c98f8a`).

Step 6 asks for `scripts/news-metrics.sh` and a cron entry for it, which needs something to
call. So the minimum Step 5 deliverable — a read-only metrics command — is included here.
It captures nothing new: Step 4 already recorded latency, tokens and a failure category
precisely so these numbers could be derived later.

## 1. Scheduling architecture

```
  host cron
      │
      ├── 10 */6 * * *   scripts/news-ingest.sh    ──> docker compose run backend
      │                                                  python -m app.news.cli ingest
      │
      ├── 0 2 * * *      scripts/news-generate.sh  ──> ... cli generate     (spends money)
      │
      └── 0 4 * * *      scripts/news-metrics.sh   ──> ... cli metrics      (read-only)
```

Each script: loads `.env`, checks its own flag, runs one compose command, logs with a UTC
timestamp, and returns an exit code cron can act on.

## 2. Why cron

`rq-scheduler`, new queue systems and workflow engines were all excluded by the brief, and
the reasoning holds independently:

- RQ's own scheduler handles `enqueue_in`/`enqueue_at` — one-shot delays — **not** cron-style
  recurrence, so `with_scheduler=True` would not give a 6-hourly cadence anyway.
- The repo already automates this way: `scripts/backup-db.sh` carries its cron line in its
  header comment and runs daily at 03:15. A second mechanism for the same job would be a
  second thing to learn and forget.
- The schedule stays visible outside the application. Removing it is deleting three lines
  from a crontab, with no application state to unwind.

Ingestion runs at **:10 past** the hour rather than on the hour, so it does not contend with
the 03:15 backup or with whole-hour traffic.

## 3. Safety controls

| Control | Where | Behaviour |
|---|---|---|
| `NEWS_INGESTION_ENABLED` | script + service | false → `news-ingest.sh` exits **0** without reaching compose |
| `NEWS_GENERATION_ENABLED` | script + service | false → `news-generate.sh` exits **0**, no provider call |
| `NEWS_AUTO_PUBLISH` | script | true → `news-generate.sh` **refuses, exit 2** |
| Per-run cap | service | `NEWS_GENERATION_BATCH_SIZE` / `NEWS_MAX_GENERATIONS_PER_RUN` |
| Per-day cap | service | `NEWS_DAILY_GENERATION_LIMIT` / `NEWS_MAX_GENERATIONS_PER_DAY`, counted from item attempts so a crashed run cannot lose its spend |
| No publication path | service | generation produces `draft` or `review_required` only |

**A disabled pipeline exits 0, not non-zero.** It is a configuration choice, not a failure,
and reporting it as one would train the operator to ignore this job's alerts.

**The auto-publish check is a safety net, not the enforcement point.** The generation service
has no path to `published` regardless. The script check exists so a misconfiguration is
caught *before* spending anything rather than after.

### Two bugs found while building this

**The `.env` load clobbered the caller.** `set -a; . ./.env; set +a` — the pattern
`backup-db.sh` uses — lets the file override an already-set environment variable. That made a
one-off override impossible and, more quietly, made the guards untestable: the auto-publish
refusal silently did not fire the first time it was exercised, because `.env` reset the
variable to false. The scripts now preserve caller overrides across the `.env` load. A test
asserts the mechanism is present in all three.

**Compose passed the optional numerics as empty strings.** `${NEWS_LLM_COST_PER_1M_INPUT:-}`
arrives as `""`, which pydantic cannot parse as `float | None`, and the API refused to start.
The blank-string validator added in Step 1 now covers every optional `NEWS_*` field.

## 4. Environment variables

```
NEWS_INGESTION_ENABLED=false        # feed polling
NEWS_GENERATION_ENABLED=false       # provider calls
NEWS_AUTO_PUBLISH=false             # MUST stay false

NEWS_GENERATION_BATCH_SIZE=2        # canonical per-run cap
NEWS_DAILY_GENERATION_LIMIT=5       # canonical per-day cap
NEWS_MAX_GENERATIONS_PER_RUN=       # alias; wins when set
NEWS_MAX_GENERATIONS_PER_DAY=       # alias; wins when set

NEWS_LLM_COST_PER_1M_INPUT=         # optional; without both, metrics reports tokens only
NEWS_LLM_COST_PER_1M_OUTPUT=
NEWS_METRICS_WINDOW_DAYS=30
```

### On the limits the brief asked me to add

`NEWS_MAX_GENERATIONS_PER_RUN` and `NEWS_MAX_GENERATIONS_PER_DAY` were **not missing** — they
already existed as `NEWS_GENERATION_BATCH_SIZE` and `NEWS_DAILY_GENERATION_LIMIT`. They are
implemented as **aliases resolved by a property**, not as new settings. Two names for one cap
is mildly confusing; two independent settings for one cap is a bug waiting to happen —
someone raises one and the other silently still binds.

**The suggested defaults (5/run, 20/day) were not adopted.** The current 2/run and 5/day were
sized from the Step 4 finding that the free tier sustained roughly three calls per session
before returning 429. Raising them would undo a measurement. They are configurable; raise
them on a paid tier.

## 5. Installation

Nothing is installed by this step. `deploy/news-cron.example` is documentation.

```bash
# 1. Set the flags in /opt/jobsvsai/.env. Both default false; the scripts exit 0 until set.
NEWS_INGESTION_ENABLED=true
NEWS_GENERATION_ENABLED=false      # leave off for the first cycles
NEWS_AUTO_PUBLISH=false            # must stay false

# 2. Verify by hand before scheduling anything.
cd /opt/jobsvsai && ./scripts/news-ingest.sh
cd /opt/jobsvsai && ./scripts/news-metrics.sh

# 3. Only then install the schedule.
sudo crontab -e     # paste from deploy/news-cron.example
sudo crontab -l     # confirm
```

**Enable ingestion first and leave generation off for several cycles.** That is exactly the
state Step 1's flag split exists to make possible, and it costs nothing to observe.

**A first scheduled ingestion at the default 48h lookback will find nothing.** First-party AI
labs publish every few days; in the Step 2 validation 203 of 238 entries fell outside 168h.
Run one wide manual pass first (`--lookback 168`) or the empty result reads as a broken
pipeline.

Log rotation is **not** configured. `/var/log/jobsvsai-news.log` grows unbounded; add it to
logrotate alongside the backup log.

## 6. Rollback

Reversible at three independent levels, cheapest first:

| Level | Action | Effect |
|---|---|---|
| 1 | `NEWS_GENERATION_ENABLED=false` in `.env` | spending stops on the next run; ingestion continues |
| 2 | `NEWS_INGESTION_ENABLED=false` | the whole pipeline goes quiet; scripts exit 0 |
| 3 | delete the three crontab lines | nothing recurs; no application state to unwind |

Nothing needs to be un-migrated and no data needs deleting: candidates and drafts are inert
while the flags are off, and nothing was ever public without an editor publishing it.

To revert the code: `git revert` this commit. The scripts and the metrics command are
additive; no existing behaviour was changed except the `.env` precedence fix, which is a
strict improvement.

## 7. Tests

**377 passed** (was 363; +14). The five required cases:

| # | Case | Test |
|---|---|---|
| 1 | Scheduler disabled | script exits 0 without reaching compose; provider call count 0 |
| 2 | Scheduler enabled | run stops at the configured batch size; alias honoured |
| 3 | Daily cap reached | second run skipped, `provider.calls == 1` |
| 4 | Auto-publish disabled | article is `review_required`, zero published rows, script exits **2** |
| 5 | Script failure | non-zero exit, `FAILED` on stderr |

Plus: the scripts exist and are executable; the cron example is documentation and no script
touches `crontab`; the aliases resolve to the canonical settings; the caller can override
`.env`; and automation never touches occupation scoring.

Script exit codes are tested by **executing the scripts**, because cron reads exit codes and
a guard that failed open would be invisible to a Python-only test. `run-tests.sh` now mounts
`scripts/` and `deploy/` read-only for that. `docker compose` is absent inside the container,
which is what makes "returned before reaching compose" and "reached compose and failed"
distinguishable.

Occupation state verified unchanged: **507 live, 507 public, JVS 1.0.3**.

## 8. Remaining risks

| Risk | Assessment |
|---|---|
| **Provider availability** | The dominant operational risk. Three consecutive failures in Step 4 (timeout, 504, 503) on top of Phase 3's 503→429. A daily scheduled generation may produce nothing for days at a time. |
| **Failing calls are slow** | 80–140s each; a two-candidate all-failing batch took 258s. Documented in the script header and the cron example. |
| **Content quality is under-sampled** | One successful generation ever. Automation would run a pipeline whose *output* has barely been evaluated. |
| **Cost model rests on one data point** | 2,248 tokens for one article. The `metrics` command will answer this properly once a real sample exists. |
| **Log growth** | Unbounded until logrotate is configured. |
| **Production drift** | Now five commits behind, with migrations 032 and 033 unapplied there. |

## 9. Next

The manual newsroom loop is now complete and automatable:

```
Sources -> Candidates -> AI Drafts -> Human Review -> Publish
```

Before enabling any of it, the honest question is the architect's from Step 4: **does the
generated content justify the cost and editorial effort?** That cannot be answered from one
successful generation. A supervised batch of 5–10 when the provider is healthy would settle
it, and `metrics` now reports the answer directly.
