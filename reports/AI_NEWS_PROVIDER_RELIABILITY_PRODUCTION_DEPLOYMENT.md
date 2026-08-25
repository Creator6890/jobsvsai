# AI News Provider Reliability — Production Deployment

**Date:** 2026-08-25 · **Host:** `srv1920920` · **Outcome:** healthy

The provider reliability fix is live. **No Gemini call was made.** Candidate 25 was not
generated, candidate 24 was not retried, nothing was published, generation stays disabled, and
no historical data was rewritten.

---

## Deployed commit

| | |
|---|---|
| Commit | `d669f082a56e93372e8210e22aeaf399f59289f5` |
| Branch | `main`, clean tree, in sync with `origin/main` |
| Contains | `d669f08` (it is `d669f08`), on top of `ee66124` |
| Pre-deploy suite | 495 passed, 0 failed |

## Release directory

```
/opt/jobsvsai/releases/d669f082a56e
```

New versioned directory. All prior releases preserved — `26e91c0a8650`, `a6cc69481da9`,
`59a6578b8305` — plus `/opt/jobsvsai/jobsvsai` and `jobsvsai-new`. No git operation was run on
the VPS; deployment remains artifact-based.

## Artifact

| | |
|---|---|
| Name | `jobsvsai-20260825T094118Z-d669f082a56e.tar.gz` |
| Built with | `git archive --format=tar.gz --prefix=<release>/ HEAD` |
| Size | 2,008,499 bytes |
| SHA-256 | `d3bc027be9e23cdaa6d1b6110fbca4518fcfe3903bd903c861ecbdea5097db60` |
| Hash after upload | identical on the VPS |
| Entries | 389 · extracted 320 files, 5.7 MB |

Verified absent in the archive and again after extraction: `.env`, `.git/`, `node_modules`,
`.next`, `__pycache__`/`.pyc`, `.DS_Store`, `._*` Mac metadata, key material, nested tarballs.
Highest migration in the artifact is `033`, unchanged.

## Database backup

| | |
|---|---|
| Path | `/var/backups/jobsvsai/jobsvsai-20260825T094228Z.dump` |
| Size | 874 MB |
| Verification | `==> Verifying archive is readable` → `==> OK` |
| Retained | **5** dumps — no prior backup deleted |

## Migration result

```
==> Applying database migrations
==> Database is up to date; nothing to apply.
```

**33 applied, 0 pending, before and after.** This release adds zero migrations, as expected.

## Healthcheck

**24 passed, 0 failed** — before and after deployment.

## Core product

| Check | Before | After |
|---|---|---|
| Public occupations | 507 | **507** |
| Live production scores | 507 | **507** |
| Active scoring model | JVS 1.0.3 | **JVS 1.0.3** |
| Promotion run 30 snapshots | 507 | 507 |
| Migrations applied | 33 | 33 |

No scoring change of any kind.

## Timeout resolved in the running services

Read from the live containers via `get_settings()`, not inferred from source:

| | backend | worker |
|---|---|---|
| `news_llm_timeout_seconds` | **90** | **90** |
| `gemini.DEFAULT_TIMEOUT_SECONDS` | 90.0 | 90.0 |
| `MAX_ATTEMPTS` | 3 | 3 |

Before deployment both resolved to **45**. Production `.env` sets no
`NEWS_LLM_TIMEOUT_SECONDS` line, so the value comes from the new compose default exactly as
predicted — no `.env` edit was needed or made.

### Error classification live

Verified by calling `GeminiGenerationProvider._classify` directly against synthetic exceptions
inside the running containers. This is pure local Python; **no network call and no provider
call were involved.**

| Status | kind | retryable |
|---|---|---|
| 429 | `rate_limited` | True |
| 503 | `server_error` | True |
| **504** | **`timeout`** | True |
| 500 | `server_error` | True |
| 401 | `credentials` | **False** |

Identical on backend and worker. The 503/504 split is live, which is the point: the next
failure will say whether it was provider capacity or our deadline.

### Token accounting fix live

```
summed from run outcomes    : True
token_totals_for_items gone : True
requeue path still present  : True
semantic policy             : news-semantic-relevance-v2
priority policy             : news-generation-priority-v1
```

Semantic-v2 and generation-priority-v1 are confirmed unchanged, as required.

## AI News flags

| Setting | backend | worker |
|---|---|---|
| `ingestion_enabled` | **False** | **False** |
| `generation_enabled` | **False** | **False** |
| `news_auto_publish` | **False** | **False** |
| `news_llm_provider` | `'null'` | `'null'` |
| API key present | **False** | **False** |

### Counts unchanged by the deployment

| Table | Before | After |
|---|---|---|
| `news_sources` | 9 | 9 |
| `news_ingest_items` | 37 | 37 |
| `news_articles` | 0 | 0 |
| `news_ingestion_runs` | 1 | 1 |
| `news_generation_runs` | 4 | 4 |

Ingest split unchanged at 33 `candidate` / 4 `ignored`.

## Candidate 25 and 24

| Item | status | `is_ai_news` | attempts |
|---|---|---|---|
| 24 | `candidate` | NULL | 1 |
| **25** | **`candidate`** | **NULL** | **3** |

Both unchanged and still recoverable. Candidate 25 remains eligible for a single supervised
generation attempt whenever that is approved. Neither was modified.

## Provider / key persistent state

Production `.env` contains **zero** `NEWS_LLM_API_KEY` lines and **zero** `NEWS_LLM_PROVIDER`
lines. Mode 600, mtime **2026-08-25 07:52:04** — unchanged since the AdSense release, so the
file was copied forward untouched. No credential was added. Supervised process-scoped
credentials remain the only path.

## Cron state

**No AI News automation installed.** Nothing matching `news-ingest.sh`, `news-generate.sh` or
`news-metrics.sh` in `/etc/cron.d`, `/etc/crontab`, `/var/spool/cron` or
`/etc/systemd/system`.

## AdSense

`NEXT_PUBLIC_ADS_ENABLED=false`, `NEXT_PUBLIC_ADS_DEBUG=false` in the running frontend.
Untouched by this release — the frontend container was not even recreated, because this commit
changed no frontend source.

## Historical token-row caveat

**Deliberately not corrected.** The pre-existing inflated rows remain exactly as they were:

| Run | status | failed | tokens recorded |
|---|---|---|---|
| 1 | completed | 0 | 1469 / 615 |
| 2 | failed | 1 | **0 / 0** |
| 3 | failed | 1 | **1469 / 615** ← inherited |
| 4 | failed | 1 | **1469 / 615** ← inherited |

| | input | output |
|---|---|---|
| Sum over `news_generation_runs` | **4,407** | **1,845** |
| Sum over `news_ingest_items` (truth) | **1,469** | **615** |

Run 2 is worth noting: it recorded **0/0** correctly, because it was the first failure against
item 24, which had no prior successful call to inherit from. That confirms the mechanism
precisely — the defect only manifested when a failed run targeted an item that already carried
tokens from an earlier success.

**The code fix affects new runs only.** Any generation run created from now on sums usage from
its own outcomes, so a failed call contributes zero. Correcting runs 3 and 4 would be a data
repair on append-only audit rows and needs its own explicit decision; it was not attempted, and
no historical row was touched.

Until that decision is made: **do not cost from `news_generation_runs` token columns.** The
metrics surface is safe — `cli metrics` aggregates from `news_ingest_items` and has always
reported the correct 2,084 total.

## Container working directories

| Container | working_dir |
|---|---|
| backend, worker, caddy | `/opt/jobsvsai/releases/d669f082a56e` |
| **frontend** | `/opt/jobsvsai/releases/26e91c0a8650` |
| postgres, redis | `/opt/jobsvsai/jobsvsai` |

Frontend was not recreated because this commit touched no frontend source and its service
definition is unchanged, so Compose correctly left it running. Postgres and redis likewise
untouched at Up 3 days. All six healthy.

## Rollback information

| Mechanism | Status |
|---|---|
| Verified DB backup | **available** — `jobsvsai-20260825T094228Z.dump`, 874 MB, readability verified |
| Previous release trees | **available** — `26e91c0a8650`, `a6cc69481da9`, `59a6578b8305`, plus `jobsvsai` / `jobsvsai-new` |
| `scripts/rollback.sh` (image restore) | **unavailable** — recorded images already pruned |
| `scripts/restore-db.sh` | present |

The recorded rollback images for backend, worker and frontend are all **MISSING**, as on every
previous deployment. Cause is the pre-existing host cron `docker image prune -af --filter
"until=24h"`, whose `-a` flag collects unused images including the previous release's. This is
longstanding and not caused by this deployment.

Practical rollback path if needed: rebuild from `/opt/jobsvsai/releases/26e91c0a8650`, which is
intact. Note this release applied no migrations, so a code rollback needs no schema reversal.

## What was not done, by instruction

No Gemini call. Candidate 25 not generated, candidate 24 not retried, nothing published,
generation not enabled, no cron installed, `news-semantic-relevance-v2` and
`news-generation-priority-v1` unmodified, AdSense untouched, and no historical generation-run
row rewritten.

## Next step

The next task is **exactly one supervised generation attempt for candidate 25**, and it should
begin only after the owner confirms paid Gemini billing / Tier 1 is active — that confirmation
cannot be made from here.

When it runs, the recorded `generation_error_kind` is now diagnostic: `timeout` points at the
deadline or the request itself, `server_error` at provider capacity. Under the previous
classification both looked identical.
