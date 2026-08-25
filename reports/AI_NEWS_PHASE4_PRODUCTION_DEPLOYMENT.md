# AI News Phase 4 — Production Deployment

**Date:** 2026-08-25 · **Host:** `srv1920920` (Ubuntu 24.04.4 LTS) · **Outcome:** healthy

This was a **code and migration deployment, not an AI News activation.** Ingestion,
generation and auto-publish remain off. No provider was configured, no feed was fetched, no
article was created, and no cron was installed.

---

## 1. Deployed commit

| | |
|---|---|
| Commit | `59a6578b8305a56dea97c380332a7266f96fdb55` |
| Branch | `main`, clean working tree, in sync with `origin/main` |
| Pre-deploy test suite | 400 passed (via `./scripts/run-tests.sh` against `jobsvsai_test`) |

Git history was left unchanged. The subject line on `59a6578` is misleading but its contents
are correct; it was not amended and `main` was not force-pushed.

## 2. Release directory

```
/opt/jobsvsai/releases/59a6578b8305
```

A new versioned directory. Nothing was renamed or deleted — `/opt/jobsvsai/jobsvsai`,
`/opt/jobsvsai/jobsvsai-new`, the three backup trees and all existing backups are untouched.
Directory consolidation is deferred to a separate task.

The **symlink cutover described in `AI_NEWS_PHASE4_PRODUCTION_SYNC_PLAN.md` was not
performed**, because the layout it assumes does not exist. See §16.

## 3. Artifact

| | |
|---|---|
| Name | `jobsvsai-20260825T024359Z-59a6578b8305.tar.gz` |
| Built with | `git archive --format=tar.gz --prefix=<release>/ HEAD` |
| Size | 1,932,450 bytes (1.8 MB) |
| SHA-256 | `c1cfe5137005aa83a4bb84cd96bc649b586664e7f1d29cf532a866cb18765f77` |
| Hash after upload | identical on the VPS |
| Entries | 369 · extracted tree 302 files, 5.5 MB |

`git archive` was used rather than a tar of the working directory, so the artifact is exactly
the commit tree. Verified absent: `.env`, `.git/`, `node_modules`, `.next`, `__pycache__`,
`.pyc`, `.DS_Store`, `._*` AppleDouble files, venvs, tool caches, and key material
(`.pem`/`.key`/`id_rsa`/`id_ed25519`). Re-verified after extraction on the server — all zero.

One tracked file matched the "archive" pattern: `jobsvsai_phase1_ui_mobile_ready.zip`, a
50 KB static HTML mockup committed in the initial commit `3587fe3`. Its listing contains no
env, key or credential files. It was **retained deliberately** — excluding tracked content
would make the artifact diverge from the commit and break the property that a release is
exactly a reviewable revision.

## 4. Database backup

| | |
|---|---|
| Path | `/var/backups/jobsvsai/jobsvsai-20260825T025729Z.dump` |
| Size | 874 MB |
| Verification | `==> Verifying archive is readable` → `==> OK` |
| Retained | 2 dumps (the previous 2026-08-24 dump was **not** deleted) |
| Free space at backup time | 82,039 MB |

Taken by `scripts/backup-db.sh`, invoked by `update.sh` before anything was changed.

## 5. Pre-deploy migration status

**31 applied (001–031), exactly 2 pending: 032 and 033.**

Before deploying, every applied migration's SHA-256 was compared against the checksum
recorded in `schema_migrations`. **All 31 matched the artifact byte-for-byte.** This check
mattered: `migrate.sh` refuses to run if an applied migration's checksum has drifted, and a
mismatch would have aborted the release after the backup and build.

## 6. Migrations applied

```
==> 2 pending migration(s):
==> Applying 032_ai_news_phase4_editorial.sql
   applied 032_ai_news_phase4_editorial.sql
==> Applying 033_ai_news_phase4_generation_audit.sql
   applied 033_ai_news_phase4_generation_audit.sql
```

Exactly the two expected. No other migration became pending or executed.

## 7. Post-deploy migration status

`scripts/migrate.sh --status` → **Applied: 33, Pending: 0**, range
`001_initial_schema.sql` … `033_ai_news_phase4_generation_audit.sql`. No checksum drift —
the status command performs the drift check first and would have refused.

## 8. Build result

`docker compose build --pull` completed with **zero errors**; frontend, backend and worker
images all rebuilt (`naming to docker.io/library/jobsvsai-frontend:latest done`).

## 9. Healthcheck

**24 passed, 0 failed** — identical to the pre-deploy baseline.

Containers, datastores, data integrity, worker liveness, internal API, seven public routes,
the public API, and ingress hygiene (HTTP→HTTPS 308; data console not exposed on the API
host, 404) all pass.

`update.sh` would have rolled back automatically had this failed. It did not fire.

## 10. Service states

| Service | State | Uptime after deploy |
|---|---|---|
| postgres | healthy | Up 2 days (**not recreated**) |
| redis | healthy | Up 2 days (**not recreated**) |
| backend | healthy | recreated |
| worker | healthy | recreated |
| frontend | healthy | recreated |
| caddy | healthy | recreated |

## 11. Core data verification

| Check | Result |
|---|---|
| Public occupations | **507** |
| Live production scores (`current_production_occupation_scores`) | **507** |
| Active scoring model | **JVS 1.0.3** (`legacy-jvs-1`) |
| `JVS 2.0.0-phase4b` | registered, `is_active = false` |
| Non-fixture promotion runs | 1 — id 30, `phase6-promotion-2026q3-v1`, completed, 507 snapshots |
| Editorial `occupations` rows | 512 |
| Legacy `occupation_scores` rows | 11 (unmodified) |
| Publication split | 507 public / 104 review_required / 405 staged |

Unchanged across the deployment.

### Public routes

`/` 200 · `/rankings` 200 · `/news` 200 · `https://api.jobsvsai.com/health` 200 ·
`/api/v1/occupations` 200

## 12. AI News row counts — before and after

| Table | Before | After |
|---|---|---|
| `news_articles` | 0 | 0 |
| `news_article_job_areas` | 0 | 0 |
| `news_article_sources` | 0 | 0 |
| `news_article_tags` | 0 | 0 |
| `news_generation_runs` | 0 | 0 |
| `news_ingest_items` | 0 | 0 |
| `news_ingestion_runs` | 0 | 0 |
| `news_sources` | 9 | 9 |

**Unchanged.** The only AI News effect of this deployment was schema: migrations 032 and 033
added columns. No feed was fetched, no candidate created, no generation attempted, no
provider call made, no article written, nothing published. `ingest`, `generate` and
`regenerate` were not invoked.

## 13. Resolved safety flags

Read from the **running containers** via `get_settings()`, not inferred from files:

| Setting | backend | worker |
|---|---|---|
| `ingestion_enabled` | **False** | **False** |
| `generation_enabled` | **False** | **False** |
| `news_auto_publish` | **False** | **False** |
| `uses_legacy_news_flag` | False | False |
| `news_llm_provider` | `'null'` | `'null'` |
| API key present | False | False |
| `generations_per_run` / `_per_day` | 2 / 5 | 2 / 5 |

The three flags were written explicitly into the new release's `.env` (mode 600, root:root),
each present **exactly once**:

```
NEWS_INGESTION_ENABLED=false
NEWS_GENERATION_ENABLED=false
NEWS_AUTO_PUBLISH=false
```

`uses_legacy_news_flag = False` confirms these explicit keys are doing the work rather than
the deprecated `NEWS_ENABLED` fallback. `NEWS_ENABLED` was left absent as instructed; compose
defaults it to `false`, so no path resolves true. No provider or API key was added. File
contents were never printed.

## 14. Cron state

**No AI News automation is installed.** The root crontab has no non-comment entries, and no
reference to `news-ingest.sh`, `news-generate.sh` or `news-metrics.sh` exists anywhere in
`/etc/cron.d`, `/etc/crontab`, `/var/spool/cron` or `/etc/systemd/system`. No systemd timers
match. `deploy/news-cron.example` ships as documentation only.

Unrelated pre-existing host cron: `docker-image-prune`, `docker-builder-prune`, `e2scrub_all`,
`monarx-update`, `sysstat`. See §16 for why the first one matters.

## 15. Per-container Compose working directories

| Container | `com.docker.compose.project.working_dir` |
|---|---|
| backend | `/opt/jobsvsai/releases/59a6578b8305` |
| worker | `/opt/jobsvsai/releases/59a6578b8305` |
| frontend | `/opt/jobsvsai/releases/59a6578b8305` |
| caddy | `/opt/jobsvsai/releases/59a6578b8305` |
| postgres | `/opt/jobsvsai/jobsvsai` (older path, unchanged) |
| redis | `/opt/jobsvsai/jobsvsai` (older path, unchanged) |

This split is expected and safe. `docker-compose.prod.yml` is byte-identical between the old
and new trees, and `docker-compose.yml` differs only by NEWS_* environment additions to
backend and worker — the postgres and redis service definitions are unchanged, so their
config hash matched and Compose correctly left them running. They were **not** force-recreated
merely to make labels consistent.

The property that makes this safe is that `name: jobsvsai` is pinned at line 1 of
`docker-compose.yml`, so the project name is independent of the directory. Postgres data lives
in the named volume `jobsvsai_postgres_data`, which is keyed by project name, not working
directory. The stack's only bind mount is Caddy's `Caddyfile`.

## 16. Warnings and findings

**1. The sync plan's symlink layout does not exist.** `AI_NEWS_PHASE4_PRODUCTION_SYNC_PLAN.md`
(line 260) proposes cutting over with
`ln -sfn /opt/jobsvsai/releases/<rev> /opt/jobsvsai/jobsvsai`. On this host
`/opt/jobsvsai/jobsvsai` is a **real directory**, not a symlink, and `find -type l` returns
nothing under `/opt/jobsvsai`. Run against a real directory, `ln -sfn` does not replace it —
it silently creates the link *inside* it at `/opt/jobsvsai/jobsvsai/<rev>`, so the deploy
would appear to succeed while cutting over nothing. **This step was not executed.** The plan
should be corrected before reuse.

**2. Image-based rollback has a ~24-hour shelf life on this host — pre-existing.** `update.sh`
recorded the previous backend/worker/frontend image IDs in `.deploy-state`, but those images
are **no longer on disk**, and there are zero dangling images. `scripts/rollback.sh` inspects
each recorded image and exits 1 if any is missing, so it would refuse.

The cause is a pre-existing host cron:

```
42 4 * * * root docker image prune -af --filter "until=24h"
```

The `-a` flag removes all *unused* images, not just dangling ones, so the prior release's
now-untagged images are collected within a day of every deploy. **This was not caused by this
deployment** — the images recorded by the previous 2026-08-24 release were already missing
before it started. Worth a separate decision: either exclude release images from the prune, or
tag each release image with its revision so rollback targets survive.

**3. The previous release tree was a raw Mac tar.** `/opt/jobsvsai/jobsvsai-new` is owned by
uid 501 (`staff`), contains `._*` AppleDouble files, and is ~1 GB because it carries
`node_modules` and `.next`. The new release directory is 5.5 MB and clean. Retained as-is; it
is currently part of the rollback path.

**4. Production `.env` predates AI News.** Before this deployment it contained no `NEWS_*`
keys at all. Three were added explicitly (§13). The remaining 15 `NEWS_*` settings documented
in `.env.production.example` are still absent and fall back to compose defaults — safe, but an
operator diffing the template against the live file will see drift.

**5. Directory proliferation is unresolved.** `/opt/jobsvsai` now holds `jobsvsai`,
`jobsvsai-new`, `releases/59a6578b8305`, two backup trees, `jobsvsai-pre-analytics`, and two
tarballs (one 806 MB). Deferred by instruction; disk is not under pressure (81 GB free, 17%
used).

## Rollback availability

| Mechanism | Status |
|---|---|
| Verified DB backup | **available** — `/var/backups/jobsvsai/jobsvsai-20260825T025729Z.dump`, 874 MB, readability verified |
| Previous release source trees | **available** — `jobsvsai-new` and `jobsvsai` intact |
| `scripts/rollback.sh` (image restore) | **unavailable** — recorded images pruned (see §16.2) |
| `scripts/restore-db.sh` | present |

Code rollback path if needed: rebuild from the previous tree rather than restoring images.
Note that migrations are forward-only by design — `rollback.sh` reverts code, not schema.

---

## State after deployment

Ingestion **off**. Generation **off**. Auto-publish **off**. Provider `null`, no API key.
No cron installed. No Gemini call made. Nothing published. Old directories untouched.

The next task is controlled production ingestion validation, which is separate and not
started.
