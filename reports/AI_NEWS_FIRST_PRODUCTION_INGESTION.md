# AI News — First Controlled Live Production Ingestion

**Date:** 2026-08-25 · **Host:** `srv1920920` · **Outcome:** healthy

Two stages, both complete: the generation-priority release was deployed, and the first
persistent AI News ingestion ran. **Generation stayed off throughout.** No provider was
configured, no Gemini call was made, no article exists, nothing was published, no cron was
installed.

**Recommendation: READY FOR SUPERVISED GENERATION** — see §20, including which candidates to
use and one editorial caveat about the top-ranked item.

---

## 1. Deployed commit

| | |
|---|---|
| Commit | `a6cc69481da9abfd8e66588fab8e01174d41c235` |
| Branch | `main`, clean tree, in sync with `origin/main` |
| Contains `a6cc694` | yes (it *is* `a6cc694`) |
| Pre-deploy suite | **421 passed** via `./scripts/run-tests.sh` against `jobsvsai_test` |
| Release directory | `/opt/jobsvsai/releases/a6cc69481da9` (new; nothing overwritten) |

`/opt/jobsvsai/jobsvsai`, `/opt/jobsvsai/jobsvsai-new` and
`/opt/jobsvsai/releases/59a6578b8305` were left untouched. No symlink layout was introduced.

## 2. Artifact

| | |
|---|---|
| Name | `jobsvsai-20260825T035808Z-a6cc69481da9.tar.gz` |
| Built with | `git archive --format=tar.gz --prefix=<release>/ HEAD` |
| Size | 1,961,164 bytes |
| SHA-256 | `74843a4e7eb75bfe8d31e1e8c4ff29cb60dd53417d5f5f894c1d7d51ab7d7c3d` |
| Hash after upload | identical on the VPS |
| Entries | 374 · extracted 307 files, 5.6 MB |

Verified absent, in the archive and again after extraction: `.env`, `.git/`, `node_modules`,
`.next`, `__pycache__`/`.pyc`, `.DS_Store`, `._*` Mac metadata, venvs, tool caches, key
material, and local tarballs. `backend/app/news/priority.py` and its test file are both
present. Highest migration in the artifact is `033`, unchanged.

## 3. Deployment health

Ran via the existing `scripts/update.sh`, without `--pull`.

| Step | Result |
|---|---|
| Database backup | `/var/backups/jobsvsai/jobsvsai-20260825T035853Z.dump`, 874 MB |
| Backup verification | `==> Verifying archive is readable` → `==> OK` |
| Backups retained | 3 (earlier dumps preserved) |
| Migrations | **`Database is up to date; nothing to apply.`** — 0 before, 0 after, 33 applied |
| Build | completed, no errors |
| Healthcheck | **24 passed, 0 failed** |
| Rollback handling | not triggered |

`news-generation-priority-v1` requires no migration, and none appeared. The deployed code was
confirmed live by querying the running container: policy version
`news-generation-priority-v1`, bands HIGH ≥ 60 / MEDIUM ≥ 35 / ceiling 15, and
`select_generation_candidates` confirmed to call `priority.assess`.

### Container working directories

| Container | working_dir |
|---|---|
| backend, worker, caddy | `/opt/jobsvsai/releases/a6cc69481da9` |
| postgres, redis | `/opt/jobsvsai/jobsvsai` (unchanged, not recreated) |
| **frontend** | `/opt/jobsvsai/releases/59a6578b8305` (see below) |

**Finding: the frontend container was not recreated.** `a6cc694` touched only backend Python,
reports and tests, and `diff -rq` confirms the `frontend/` trees of the two releases are
**byte-identical**. The rebuild produced a new image id (`6911c42f`) which the running
container (`ed6a2794`) does not use. Because the source is identical there is no behavioural
drift, all frontend routes return 200, and the healthcheck passes — so it was **not**
force-recreated merely to make the label consistent, in keeping with the same reasoning
applied to postgres and redis.

## 4. Pre-ingestion counts

| | |
|---|---|
| `news_sources` | 9 |
| `news_ingest_items` | 0 |
| `news_articles` | 0 |
| `news_ingestion_runs` | 0 |
| `news_generation_runs` | 0 |
| sources ever fetched | 0 |
| Public occupations / live scores / model | 507 / 507 / JVS 1.0.3 |
| Resolved flags (backend and worker) | ingestion **False**, generation **False**, auto_publish **False**, provider `'null'`, key absent |

The deployment changed none of the AI News counts.

## 5. Live ingestion command

Ingestion was enabled **only as a process-scoped override on this single `exec`**. `.env` was
not modified.

```
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T \
  -e NEWS_INGESTION_ENABLED=true \
  -e NEWS_GENERATION_ENABLED=false \
  -e NEWS_AUTO_PUBLISH=false \
  backend python -m app.news.cli ingest --lookback 168 \
    --triggered-by "first-controlled-production-ingestion"
```

No `--dry-run`. No secrets involved — no provider or API key exists in this release. The CLI
echoed its own resolved state:

```
AI News ingestion · LIVE — results will be stored
  ingestion_enabled = True   generation_enabled = False   auto_publish = False
  lookback = 168h   per-feed cap = 40   relevance policy = news-relevance-v1
```

Persisted run: **id 1**, key `news-ingest-20260825T040457-45fd34bd`, status `completed`,
triggered_by `first-controlled-production-ingestion`, lookback 168h, 6,103 ms.

## 6. Source health

**9 attempted, 9 succeeded, 0 failed.** Every source now carries a `last_fetched_at` around
04:05:00 UTC, `consecutive_failures = 0`, and no `last_error`: OpenAI, Google DeepMind, Google
AI, Microsoft Research, NVIDIA, Hugging Face, Mistral AI, MIT Technology Review, Ars Technica.

This is the first time source health has ever been written — all nine were NULL before, because
every prior run was a dry run.

## 7–11. Ingestion results

| Measure | Value |
|---|---|
| Entries fetched | **238** |
| Inside 168h window | **37** |
| Outside window | **201** |
| Stored new | 37 |
| Candidates | **33** |
| Ignored | **4** |
| Exact duplicates | **0** |
| Near duplicates | **0** |

These match the final dry run **exactly** on every counter. Dry-run parity is therefore
confirmed against production for the first time: the preview and the run it previews agreed
item for item.

Stored `news_ingest_items` = 37, split `candidate` 33 / `ignored` 4. No item reached
`processed`, which is correct — `processed` means converted into an article, and no article
exists.

## 12. Metadata completeness

Across all 37 stored items:

| Field | Present |
|---|---|
| `original_title` | 37/37 |
| `external_url` | 37/37 |
| `canonical_url` | 37/37 |
| `source_published_at` | 37/37 |
| `original_excerpt` | **32/37** |

## 13. Title-only items

Five items carry no excerpt, exactly as the dry run predicted:

| Source | Title |
|---|---|
| Hugging Face | Wire It, Run It, Deploy It: AI Workflows in Gradio |
| Hugging Face | Measuring benchmark optimization in speech recognition |
| Hugging Face | Up to 3.2x Faster Inference with LFM2.5-DSpark |
| Hugging Face | How Much Memory Does Your Agent Actually Need? |
| Mistral AI | Mistral x HUMAIN |

Hugging Face supplies no summary in its feed at all — 4 of 4. Four of the five are candidates
(the Mistral item was relevance-ignored at 15). They carry the `-5` title-only priority penalty
and are flagged `!` in the CLI so the operator can see the judgement rests on a headline alone.
No article pages were scraped.

## 14. Top 15 stored candidates by generation priority

Produced by the deployed policy against the persisted rows.

| # | ID | Source | AI | Prio | Band | Title | Signals |
|---|---|---|---|---|---|---|---|
| 1 | 24 | OpenAI | 67 | **87** | HIGH | Asana cleared 5 years of engineering work in 2 weeks with Codex | engineering work, codex |
| 2 | 25 | Ars Technica | 81 | **67** | HIGH | AI is hitting entry-level jobs hardest, Stanford study finds | employment, entry-level, job, jobs, occupations, research, study |
| 3 | 14 | OpenAI | 70 | 59 | MEDIUM | Advancing price-performance for developers with GPT-5.6 | developers |
| 4 | 32 | MIT Tech Review | 61 | 59 | MEDIUM | How to encourage smarter AI use in the classroom | classroom, students |
| 5 | 9 | Mistral AI | 80 | 52 | MEDIUM | Agentic Search | agentic, retrieval |
| 6 | 17 | OpenAI | 70 | 50 | MEDIUM | Offering Zero Data Retention for frontier models | frontier model, customers, data |
| 7 | 16 | OpenAI | 80 | 36 | MEDIUM | Stampli cuts launch hours by 68% using ChatGPT Work | codex, cuts |
| 8 | 21 | OpenAI | 55 | 34 | LOW | Partnering with CodeAI to prepare the first AI generation | students |
| 9 | 18 | OpenAI | 80 | 32 | LOW | Replit expands access to software creation with GPT-5.6 | software creation |
| 10 | 22 | OpenAI | 80 | 32 | LOW | Pacing model development in an era of cyber-critical capabilities | capabilities |
| 11 | 31 | Ars Technica | 46 | 32 | LOW | Microsoft Copilot reveals secret input that allowed it to be hacked | copilot |
| 12 | 3 | Hugging Face | 75 | 31 | LOW ! | Wire It, Run It, Deploy It: AI Workflows in Gradio | workflows |
| 13 | 29 | Ars Technica | 46 | 30 | LOW | Flight attendants freaked out that Google is buying employee data | workers, data |
| 14 | 4 | Hugging Face | 80 | 27 | LOW ! | Measuring benchmark optimization in speech recognition | benchmark |
| 15 | 6 | Hugging Face | 67 | 27 | LOW ! | How Much Memory Does Your Agent Actually Need? | memory |

Bands over all 33 candidates: **HIGH 2, MEDIUM 5, LOW 26** — identical to the dry-run
calibration.

**`select_generation_candidates(limit=15)` returned `[24, 25, 14, 32, 9, 17, 16, 21, 18, 22,
31, 3, 29, 4, 6]`, which matches the independent ranking exactly.** Persisted-row ordering
therefore reproduces the calibration, and the production selection path is genuinely
priority-ordered rather than relevance-ordered. The two items that would previously have led
the queue on relevance — the NVIDIA hardware post at 90 and the tied 80-point block — are not
in the top seven.

## 15. Post-ingestion dedupe dry run

One dry run over the same 168-hour window, against the now-populated database:

| Measure | Value |
|---|---|
| Entries fetched | 238 |
| Outside window | 201 |
| **Exact duplicates** | **37** |
| Near duplicates | 0 |
| New | **0** |
| Candidate | **0** |
| Ignored | **0** |

**Every in-window entry was recognised as already stored.** A repeat run proposes zero
duplicate candidate rows, which validates persistent dedupe against the real production
database for the first time — previously it had only ever been exercised against an empty
table.

The **0.55 near-duplicate threshold was not retuned** and remains unvalidated: near duplicates
were again 0, because exact dedupe on canonical URL and content hash absorbed every repeat
before similarity was ever consulted. Genuine same-event restatements from *different* sources
still have not appeared in any production corpus. Documented and left alone.

## 16. Confirmation of zero generation

| Measure | Value |
|---|---|
| `news_generation_runs` | **0** |
| Items with `is_ai_news` verdict | **0** |
| Items with `generation_attempted_at` | **0** |
| Sum `generation_attempts` | **0** |
| Input + output tokens | **0** |
| `generation_error_kind` populated | 0 |

`generate` and `regenerate` were never invoked. No provider exists to call — `news_llm_provider`
resolves to `'null'` and no API key is configured. The semantic second stage did not run.

## 17. Confirmation of zero publication

`news_articles` = **0**; articles with status `published` = **0**. No article was created, so
none could be published. `news_article_sources`, `news_article_tags` and
`news_article_job_areas` all remain 0.

## 18. Flag state after the command

Read from the **running containers** via `get_settings()` after ingestion completed:

| Setting | backend | worker |
|---|---|---|
| `ingestion_enabled` | **False** | **False** |
| `generation_enabled` | **False** | **False** |
| `news_auto_publish` | **False** | **False** |
| `news_llm_provider` | `'null'` | `'null'` |
| API key present | False | False |

**The process-scoped override did not leak.** On disk, `.env` carries each of the three flags
exactly once with value `false`, mode 600, and its mtime is **2026-08-25 02:57:01** — the
original file, preserved by `cp -p` through the deployment copy, and untouched by ingestion.
No AI News cron exists in `/etc/cron.d`, `/etc/crontab`, `/var/spool/cron` or
`/etc/systemd/system`.

## 19. Scoring integrity

| Check | Before | After |
|---|---|---|
| Public occupations | 507 | **507** |
| Live production scores | 507 | **507** |
| Active scoring model | JVS 1.0.3 | **JVS 1.0.3** |
| Non-fixture promotion runs | 1 | 1 |
| Snapshots in run 30 | 507 | 507 |
| Legacy `occupation_scores` | 11 | 11 |
| Healthcheck | 24/24 | **24 passed, 0 failed** |

No change to AI Exposure, Replacement Risk, scoring model versions, publication snapshots or
promotion state. The architectural separation held throughout: ingestion wrote only `news_*`
tables.

## 20. Recommendation

### READY FOR SUPERVISED GENERATION

The queue is in good shape for a first supervised sample. Ingestion was clean on every axis —
nine of nine sources healthy, complete metadata on title, URL, canonical URL and timestamp for
all 37 items, exact dry-run parity, and idempotency proven against real stored rows. The
priority ordering reproduces the calibration exactly, and the selection path the generator will
actually use returns the intended order.

**Use candidates 24 and 25** — the two HIGH items, which is also what
`select_generation_candidates` would pick with the default batch size of 2:

- **25 — "AI is hitting entry-level jobs hardest, Stanford study finds"** (Ars Technica,
  priority 67). Independent reporting of empirical labour-market research. This is the ideal
  first test: squarely on-topic, third-party, and exactly the material the platform exists to
  interpret.
- **24 — "Asana cleared 5 years of engineering work in 2 weeks with Codex"** (priority 87).
  **One caveat worth stating before it is generated:** this is OpenAI's own customer-success
  post. It ranks first on genuine substance — it is concrete evidence about AI compressing
  engineering work — but its provenance is first-party vendor marketing, and a brief built on
  it inherits the vendor's framing of its own product. That is a judgement for the human
  reviewer, and it makes a useful test of whether the semantic stage flags promotional framing
  independently of the deterministic score.

Three things remain open, none of which block a supervised sample:

1. **The AI-usage research gap.** Two substantive MIT pieces score 0 and 9 (§11 of the priority
   report). Real stored rows now exist to calibrate against, which was the argument for
   ingesting first.
2. **"Offering Zero Data Retention" at rank 6** is still a governance announcement placed above
   the Stampli productivity story.
3. **Near-dedupe remains unvalidated** at 0.55, now for the third consecutive production
   corpus.

Supervised generation will require adding provider credentials, which is deliberately out of
scope here and should be a discrete, reversible step — the free tier sustains roughly three
calls per session, and a failing call occupies 80–140 seconds, so a two-candidate batch is the
right size.

### What was not done, by instruction

Generation was not enabled globally. No Gemini credentials were added. No scheduled generation,
no cron, no automatic publication, no public expansion. The priority policy was not modified
during this task. Nothing beyond the first persistent ingestion was attempted.
