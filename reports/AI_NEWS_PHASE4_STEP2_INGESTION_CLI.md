# AI News Phase 4 — Step 2: ingestion CLI and validation

Date: 2026-08-24
Scope: **Step 2 only.** No scheduler, no generation changes, no UI features, no related
occupations, no auto-publish.

## 1. Commands

```bash
docker compose run --rm backend python -m app.news.cli ingest --dry-run   # write nothing
docker compose run --rm backend python -m app.news.cli ingest             # store results
docker compose run --rm backend python -m app.news.cli candidates         # the queue
docker compose run --rm backend python -m app.news.cli sources            # feeds + health
docker compose run --rm backend python -m app.news.cli runs               # recent runs
```

`ingest` flags: `--dry-run`, `--lookback HOURS`, `--max-entries N`, `--all` (also list
window/exact-dedupe rejects), `--urls`, `--triggered-by`.

Every row reports **source · relevance score · dedupe result · status · published date ·
title**, as required, with `*` marking scores above the confident threshold.

### The CLI cannot generate or publish

It imports neither the generation service nor a provider. That is a property of the module,
not a flag someone could flip — asserted by a test that inspects the import list, because the
guarantee is the *absence of a capability* and a behavioural test could only show it went
unused today.

## 2. Why `--dry-run` exists

A first production ingestion is otherwise unobservable until after it has happened. The dry
run executes the identical pipeline — fetch, window, exact dedupe, near dedupe, relevance —
reaches identical decisions, and writes nothing: no ingest items, no run row, and no
per-source health fields.

## 3. A real bug this step exposed

The first implementation of `--dry-run` **missed near-duplicates inside its own batch.**

A live run commits each insert, so the next entry's lookup sees it. A dry run writes nothing,
so a restatement of an entry it had just accepted was invisible: the fixture feed produced
`items_new=3, near_duplicate=0` in preview against `items_new=2, near_duplicate=1` live.

The preview over-reported candidates — precisely the failure that makes a preview worse than
none. Fixed by accumulating accepted fingerprints in memory during a dry run and matching
against them as well as against stored history. In-batch matches are reported with a negative
id and rendered as `near earlier-in-run@1.0`, so they are distinguishable from a match against
a stored row.

A test now asserts the dry run and the live run reach identical counters **and identical
per-item decisions**.

## 4. Validation results

Run against `jobsvsai_test` with `NEWS_INGESTION_ENABLED=true`,
`NEWS_GENERATION_ENABLED=false`, real feeds, 168h window.

### Gated behaviour

With the default configuration the CLI refuses cleanly and reports why, rather than raising:

```
SKIPPED: NEWS_INGESTION_ENABLED is false.
Set NEWS_INGESTION_ENABLED=true to allow feed ingestion.
```

### Dry run, then live run

| | Dry run | Live run |
|---|---|---|
| sources attempted / ok / failed | 9 / 9 / 0 | 9 / 9 / 0 |
| entries fetched | 238 | 238 |
| outside window | 203 | 203 |
| new | 35 | 35 |
| candidate | 31 | 31 |
| ignored | 4 | 4 |
| exact / near duplicates | 0 / 0 | 0 / 0 |

**The preview matched the run exactly.** After the dry run the database was verified
untouched: `ingest=0 runs=0 sources_with_fetch_time=0`.

### Source quality

All nine feeds returned HTTP 200, parsed, and produced items. No source failed. Every item
carried a source, title, URL and publication date — **no missing metadata**.

### Relevance distribution (31 candidates, 4 ignored)

Correctly ignored: a sponsored "hidden revenue streams" piece (34), an AI-harms story about
nudify ads (26), an opaque Hugging Face infrastructure post with no excerpt (15), and a
GeForce NOW gaming post (15).

Weakest accepted candidates, all consistent with a deliberately permissive prefilter:
`What Flock's defenders are missing` (41), `Strengthening democratic oversight in national
security` (50), `ChatGPT Ads expands across Europe` (80 — the known high-scoring false
positive). Semantic rejection of these is Gemini's job in Step 4, and the supervised Phase 3
run already showed it rejecting the last two at 0.95 confidence.

### Duplicates

**Zero exact and zero near-duplicates across 238 entries.** This is now the second live
sample containing no same-event duplication, so `news-dedupe-v1`'s 0.55 threshold remains
calibrated only against constructed cases. Unchanged, and still the least-evidenced part of
the pipeline.

### Generation stayed closed

After the live ingestion: `articles=0 generation_runs=0 items_with_ai_verdict=0
generation_attempts=0`. Step 1's flag separation is what made this validation possible at all.

## 5. Production run — not performed

The brief asks for this against the production database. **I could not do that**: the
production database is on the VPS, and this machine has no SSH key for it (`~/.ssh` contains
no private keys; `root@200.234.41.59` returns `Permission denied (publickey)`).

Validation therefore ran against `jobsvsai_test` with the same code, the same nine real feeds
and the same 168h window. The exact production sequence, to run on the VPS:

```bash
# 1. Preview. Writes nothing, regardless of configuration.
NEWS_INGESTION_ENABLED=true docker compose run --rm backend \
    python -m app.news.cli ingest --dry-run --lookback 168

# 2. If the preview looks right, store it.
NEWS_INGESTION_ENABLED=true docker compose run --rm backend \
    python -m app.news.cli ingest --lookback 168 --triggered-by first-production-run

# 3. Inspect what landed.
docker compose run --rm backend python -m app.news.cli candidates --status candidate
docker compose run --rm backend python -m app.news.cli runs --limit 1
```

`NEWS_GENERATION_ENABLED` must stay unset or false throughout. No `.env` change is needed —
the flag is supplied per-command, so the deployed default stays disabled.

**Do not use the default 48h window for the first run.** First-party AI labs publish every few
days; in this sample 203 of 238 entries fell outside 168h, and at 48h the earlier supervised
run stored nothing at all. An empty first run is the expected outcome of the default, not a
broken pipeline.

## 6. Files changed

| File | Change |
|---|---|
| `backend/app/news/cli.py` | **new** — the operator CLI |
| `backend/app/news/ingestion.py` | `dry_run` parameter, `ItemDecision` records, in-batch fingerprint tracking |
| `backend/tests/test_news_cli.py` | **new** — 10 tests |

No migration. No change to relevance, dedupe, generation or publication logic.

## 7. Tests

**332 passed** (was 323; +9 net). New coverage:

- the parser exposes the documented commands, and live is the explicit default
- the CLI imports nothing that could generate or publish
- a dry run writes no ingest item, no run row, and no source health field
- a dry run reaches **identical counters and identical per-item decisions** to the live run
- decisions carry source, title, URL, published date, score, dedupe result and status
- a dry run reports exact duplicates against stored history
- a dry run is refused when ingestion is gated, and does not fetch
- the lookback override is honoured in both directions

Frontend build: unchanged and clean.

## 8. Risks

| Risk | Assessment |
|---|---|
| CLI could reach generation later | Guarded by an import-inspection test that fails if the module gains such an import |
| Dry run diverges from live again | Guarded by the decision-equality test |
| Operator uses the 48h default first | Documented here and in the command sequence; the run reports `outside_window` so an empty result is legible rather than mysterious |
| Near-dedupe still unvalidated on real data | Unchanged from Phase 2. Two live samples, zero real duplicates. Only production volume over time will settle it |
| Production validation not yet done | Needs VPS access; the exact sequence is above |

## 9. Next recommended step

**Step 3 — editorial workflow controls.** The architecture review found `Regenerate` and
`Archive` missing, and `Archive` needs a new status value on `news_articles`, so Step 3 is
the first Phase 4 step that requires a migration.

Step 4 (generation validation) should follow Step 3 rather than precede it, so that anything
generated during validation can be archived rather than only rejected.
