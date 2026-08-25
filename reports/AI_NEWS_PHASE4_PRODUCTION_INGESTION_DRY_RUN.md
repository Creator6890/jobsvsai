# AI News — First Controlled Production Ingestion Validation (Dry Run)

**Recommendation: REVIEW FILTER FIRST.** The pipeline is mechanically healthy and wrote
nothing. The reservation is about what the candidate queue would *contain*, not about safety.
See §15.

---

## 1. Timestamp

| | |
|---|---|
| Dry run executed | **2026-08-25 03:26:09 UTC** |
| Duration | 6,442 ms |
| Host | `srv1920920` |
| Verification window | baseline captured 03:20Z, re-verified 03:35Z |

## 2. Deployed release

| | |
|---|---|
| Commit | `59a6578b8305a56dea97c380332a7266f96fdb55` |
| Release directory | `/opt/jobsvsai/releases/59a6578b8305` |
| Migrations | 001–033 applied, 0 pending |
| Relevance policy | `news-relevance-v1` |

## 3. Command used

Run against the production compose configuration. Ingestion was enabled **only as a
process-scoped override on this single `exec`** — `docker compose exec -e` sets variables for
that one process and does not alter the container environment or `.env`:

```
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T \
  -e NEWS_INGESTION_ENABLED=true \
  -e NEWS_GENERATION_ENABLED=false \
  -e NEWS_AUTO_PUBLISH=false \
  backend python -m app.news.cli ingest --dry-run --lookback 168 --all --urls
```

Syntax was taken from the deployed `ingest --help`, not assumed. The supported options are
`--dry-run`, `--lookback HOURS`, `--max-entries N`, `--all`, `--urls`, `--triggered-by`.
**There is no source-filter option.** No secrets were involved; no provider or API key exists
in this release.

The CLI echoed its own resolved state, which is the primary evidence for the run's safety:

```
AI News ingestion · DRY RUN — nothing will be written
  ingestion_enabled = True   generation_enabled = False   auto_publish = False
  lookback = 168h   per-feed cap = 40   relevance policy = news-relevance-v1
```

## 4. Source health

**9 attempted, 9 succeeded, 0 failed.** No HTTP errors, no parser errors, no timeouts.

| # | Source | Tier | Type | In-window entries |
|---|---|---|---|---|
| 1 | OpenAI | 1 | primary | 11 |
| 2 | Google DeepMind | 1 | primary | 1 |
| 3 | Google AI | 1 | primary | 1 |
| 4 | Microsoft Research | 1 | primary | 1 |
| 5 | NVIDIA | 1 | primary | 4 |
| 6 | Hugging Face | 1 | primary | 4 |
| 7 | Mistral AI | 1 | primary | 2 |
| 8 | MIT Technology Review | 2 | secondary | 6 |
| 9 | Ars Technica | 2 | secondary | 7 |

All nine remain enabled with `consecutive_failures = 0`.

## 5. Entries fetched

**238 entries fetched** across the nine feeds (bounded by the 40-per-feed cap).

## 6. 168-hour window

| | |
|---|---|
| Inside window | **37** |
| Outside window | **201** |

The 168-hour window was the right call. The oldest in-window item is 2026-08-18; the
outside-window tail reaches back to 2026-07-16. A 48-hour default would have returned roughly
a tenth of this — confirming the standing note that a cold start needs a wide one-off window.

## 7. Candidate and ignored counts

| Outcome | Count |
|---|---|
| Candidate | **33** |
| Ignored | **4** |
| Not stored (outside window) | 201 |
| Total decisions | 37 |

**Acceptance rate inside the window: 33/37 = 89%.** This is the central observation of the
run — see §11.

## 8. Relevance distribution

| Band | Score range | Count |
|---|---|---|
| Confident (≥60) | 61–90 | 22 |
| Candidate (40–59) | 40–58 | 11 |
| Ignored (<40) | 15–34 | 4 |

Distribution by value: 90 ×1 · 81 ×1 · 80 ×10 · 75 ×2 · 70 ×2 · 67 ×2 · 63 ×1 · 61 ×3 ·
58 ×2 · 55 ×2 · 50 ×1 · 46 ×5 · 40 ×1 · 34 ×1 · 26 ×1 · 15 ×2

**Boundary behaviour is exactly as specified.** The 40 threshold admitted one item at
precisely 40; the item at 34 was ignored. Both `15`s matched **no signals at all** and were
ignored despite being tier-1 first-party sources — direct confirmation that the source floor
requires a positive signal and that origin alone cannot rescue an item.

**Lowest-scoring accepted candidate:** 40 — Microsoft Research, *"Broadening access to Skala
creates a faster path to predictive chemistry"* (signals: `accuracy, benchmark, faster,
performance, research`).

**Highest-scoring ignored item:** 34 — MIT Technology Review, *"Unlocking hidden revenue
streams with market models"* (signal: `artificial intelligence`). Sponsored-feeling business
content; correctly rejected, but only by 6 points.

## 9. Dedupe results

| | |
|---|---|
| Exact duplicates | **0** |
| Near duplicates | **0** |
| Earlier-in-run duplicates | **0** |
| Similarity scores recorded | none (no pair crossed threshold) |

**Dedupe was not exercised.** As in the Phase 2 live sample, the corpus contained no
same-event duplicates — the nine feeds are all first-party or independent outlets covering
different announcements. The 0.55 near-duplicate threshold therefore **remains unvalidated
against real data**, still calibrated only on constructed cases. This is not a defect
revealed by this run; it is a gap this run failed to close.

## 10. Metadata quality

Measured across all 37 in-window entries:

| Field | Present | Status |
|---|---|---|
| `original_title` | 37/37 | complete |
| `external_url` | 37/37 | complete |
| `canonical_url` | 37/37 | complete |
| `source_published_at` | 37/37 | complete |
| `original_excerpt` | **32/37** | **5 missing** |

Excerpt lengths: min 78, median 149, max 388 characters; one excerpt below 80 characters.

**The five missing excerpts are all four Hugging Face entries plus one Mistral AI entry.**
Hugging Face supplies no summary in its feed at all — 0 of 4. All four Hugging Face items
scored as candidates (80, 80, 75, 67), so under a live run they would enter the queue with a
title and no body text. That matters because title plus excerpt is the generation input; a
brief generated from a title alone is materially thinner. No full article bodies were fetched
or stored.

URLs are clean and canonical throughout (e.g.
`https://arstechnica.com/ai/2026/08/ai-is-hitting-entry-level-jobs-hardest-stanford-study-finds/`).

## 11. Candidate-quality observations

The pipeline is working as specified. The concern is what "as specified" admits.

**Only one of 33 candidates matched a jobs-related signal.** *"AI is hitting entry-level jobs
hardest, Stanford study finds"* (81; signals `ai, research, job, jobs`) is the single item
whose relevance derives from work impact. One further item — *"Asana cleared 5 years of
engineering work in 2 weeks"* (67; signals `codex, replace`) — is work-relevant by
implication.

**The score ordering inverts editorial value.** The highest-scoring item in the entire run is
NVIDIA's *"With Groq 3 LPX in Full Production, NVIDIA Extends Vera Rubin…"* at **90** —
datacentre hardware marketing, matching on `agentic, ai, inference, announced, breakthrough,
agents, factory`. It outranks the Stanford labour-market study at 81. Two further NVIDIA
infrastructure posts scored 75 and 63.

Weak candidates by the categories flagged for attention:

- **Product/business announcements scoring 80:** *"ChatGPT Ads expands across Europe"*
  (`chatgpt, expanding, expands`) — advertising business news; *"Introducing ChatGPT for
  Teens"* (`ai, chatgpt, introducing`); *"Replit expands access to software creation with
  GPT-5.6"* (`gpt, expands, introduces, powered by`); *"Introducing AI Futures"* — which
  reached 80 on just two generic signals, `ai, introducing`.
- **Infrastructure:** the three NVIDIA posts above, plus *"How XPUs Meet a World-Class AI
  Factory"* (75).
- **Policy/governance:** *"Strengthening democratic oversight in national security"* (50),
  *"Pacing model development in an era of cyber-critical capabilities"* (80), *"Offering Zero
  Data Retention for frontier models"* (70).
- **Consumer/tangential:** *"5 new ways to level up your learning with Search"* (55, signal
  `ai` alone); *"As demand for Meta AI glasses explodes…"* (46); *"Flight attendants freaked
  out that Google is buying tons of Spirit employee data"* (46 — matched `employee, workers`,
  but is a privacy story, not a jobs story).
- **Security incidents:** *"Grok exfiltrates user data…"* (46), *"Microsoft Copilot reveals
  secret input…"* (46).
- **Philosophy:** *"Debates over AI consciousness are a trap"* (58).
- **Model names without work implications:** *"From Atari to EVE Online: Building on 15 Years
  of AI Research"* (80) — a gaming-framed research retrospective.

**Correctly ignored, and encouraging:** *"Mistral x HUMAIN"* (15, no signals — a bare
partnership announcement), *"Bring the Fire: Play Games on GeForce NOW"* (15, no signals —
gaming), *"Meta ran ads for an app promising to nudify female politicians"* (26).

**Interpretation.** `news-relevance-v1` is a presence-based topical prefilter answering "is
this AI news", not "does this bear on work". That is its documented design, and jobs-relevance
is meant to be settled later by the semantic stage. The finding is therefore not that the
prefilter is broken, but that **on a real corpus it concentrates the queue in vendor
announcements**, and the cost of separating those out falls on the generation stage, which is
the expensive, quota-limited one. The relevance algorithm was **not modified** during this
task.

## 12. Before / after database counts

| Table / measure | Before | After | Δ |
|---|---|---|---|
| `news_sources` | 9 | 9 | 0 |
| `news_ingest_items` | 0 | 0 | 0 |
| `news_articles` | 0 | 0 | 0 |
| `news_ingestion_runs` | 0 | 0 | 0 |
| `news_generation_runs` | 0 | 0 | 0 |
| `news_article_sources` | 0 | 0 | 0 |
| `news_article_tags` | 0 | 0 | 0 |
| `news_article_job_areas` | 0 | 0 | 0 |
| items with `is_ai_news` verdict | 0 | 0 | 0 |
| items with `generation_attempted_at` | 0 | 0 | 0 |
| items with `generation_error_kind` | 0 | 0 | 0 |
| generation input tokens | 0 | 0 | 0 |
| generation output tokens | 0 | 0 | 0 |
| published articles | 0 | 0 | 0 |

**Confirmed: production AI News content did not change.**

Source health was likewise untouched — `last_fetched_at`, `last_success_at` and `last_error`
are all still NULL for all nine sources, `consecutive_failures` sums to 0, and
`max(news_sources.updated_at)` remains **2026-08-24 05:57:47 UTC**, predating the 03:26Z dry
run. The run also reported `run_id = None`, confirming no ingestion run row was created. This
matches the documented guarantee that a dry run writes no items, no run row and no source
health.

## 13. Confirmation of zero generation

- `generation_enabled = False` throughout, as echoed by the CLI at run start.
- No provider exists to invoke: `news_llm_provider = 'null'`, `api_key_present = False`.
- No generation audit rows: `news_generation_runs` still 0.
- No token usage: input and output token sums both 0.
- No semantic AI verdicts: `is_ai_news IS NOT NULL` count still 0.
- No articles: `news_articles` still 0; published still 0.
- `ingest`, `generate` and `regenerate` were not run live; only `ingest --dry-run` executed.

The run exercised **deterministic ingestion, relevance and dedupe only**. No Gemini or other
provider call was made.

**The process-scoped override did not leak.** Re-checked after the run via `get_settings()`
inside the live containers: backend and worker both still report `ingestion_enabled = False`,
`generation_enabled = False`, `auto_publish = False`. On disk, `.env` still carries each of
the three flags exactly once with value `false`, mode 600, and its mtime is **02:57:01** — the
deployment, not the dry run. No AI News cron is installed.

## 14. Scoring integrity

| Check | Before | After |
|---|---|---|
| Public occupations | 507 | **507** |
| Live production scores | 507 | **507** |
| Active scoring model | JVS 1.0.3 | **JVS 1.0.3** |
| Non-fixture promotion runs | 1 | 1 |
| Legacy `occupation_scores` | 11 | 11 |
| Editorial `occupations` | 512 | 512 |

No change to occupation scores, AI Exposure, Replacement Risk, model versions, publication
snapshots or promotion state. The architectural separation held: no `news_*` table references
occupation or scoring data, and the dry run touched nothing outside AI News.

## 15. Recommendation

### REVIEW FILTER FIRST

Everything mechanical passed: nine of nine sources healthy, complete metadata on the fields
that matter, correct window arithmetic, threshold boundaries behaving exactly as documented,
the source floor correctly refusing signal-free posts, and provably zero writes. On safety
grounds alone there is no obstacle to live ingestion.

The reservation is editorial and economic. An 89% in-window acceptance rate produces a queue
of 33 candidates in which one item concerns jobs, while datacentre hardware marketing takes
the top score. Generation is capped at **5 per day** with a batch size of 2, and the free tier
sustains roughly 3 calls per session — so draining this queue would take about a week of quota
and spend most of it discovering that vendor announcements are not labour-market news. A
failing call also occupies 80–140 seconds, so the cost of a mismatched queue is measured in
wall-clock time as well as tokens.

Reviewing the prefilter — or introducing a cheap jobs-relevance gate between candidacy and
generation — is substantially cheaper than generating 33 briefs to learn the same thing.

**Two qualifications, stated plainly.** First, live ingestion is itself cheap and safe: it
invokes no LLM, stores internal triage rows with no public route, and is separately gated from
generation. If you would rather have the 33 rows on disk to triage in the admin console, that
is a defensible call and this run gives no safety reason to refuse it — the filter question
would simply move to the generation gate, where it must be answered regardless. Second, the
dedupe threshold is still unvalidated on real data; a corpus with no duplicates cannot confirm
0.55 is right, so that gap persists into whatever is decided next.

**Not done, by instruction:** live ingestion was not run. No candidates were persisted, no
provider enabled, no API key added, no article generated, nothing published, no cron
installed, no feature flag changed.
