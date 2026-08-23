# AI News Phase 2 — RSS/Atom ingestion

Date: 2026-08-23
Status: **Implemented, disabled by default.** `NEWS_ENABLED=false`; no scheduled run is
active. Migration `030_ai_news_phase2_ingestion.sql`. Policies `news-relevance-v1`,
`news-dedupe-v1`.

## 1. Scope

    trusted RSS/Atom feeds -> fetch -> normalise -> exact dedupe -> near dedupe
      -> relevance prefilter -> candidate | ignored | duplicate -> admin incoming queue

Phase 2 produces **candidates for a human**. It does not write prose, call any model, assign
impact factors, create articles, or publish. Nothing it does can reach a public page: there
is no public route that serves an ingest item and no public schema that can serialise one.

### What Phase 2 deliberately does NOT do

- No LLM of any kind. `NullGenerationProvider` still refuses.
- No article body scraping. Feed-provided metadata only.
- No automatic article creation — conversion is an explicit admin action.
- No story clustering. Near-duplicates are *marked and linked*, not merged into a cluster
  entity. A real cluster model needs semantic similarity, which is Phase 3+.
- No automatic publishing. `NEWS_AUTO_PUBLISH` stays false.

## 2. Source strategy

Free, public RSS/Atom only. No paid news APIs, no Google News scraping, no social media, no
HTML scraping of any kind.

**Every seeded feed URL was fetched and confirmed to return a parseable RSS document before
it was written into the migration.** None was guessed.

| Source | Tier | Type | Feed |
|---|---|---|---|
| OpenAI | 1 | primary | `openai.com/news/rss.xml` |
| Google DeepMind | 1 | primary | `deepmind.google/blog/rss.xml` |
| Google AI | 1 | primary | `blog.google/technology/ai/rss/` |
| Microsoft Research | 1 | primary | `microsoft.com/en-us/research/feed/` |
| NVIDIA | 1 | primary | `blogs.nvidia.com/feed/` |
| Hugging Face | 1 | primary | `huggingface.co/blog/feed.xml` |
| Mistral AI | 1 | primary | `mistral.ai/rss.xml` |
| MIT Technology Review | 2 | secondary | `technologyreview.com/topic/artificial-intelligence/feed/` |
| Ars Technica | 2 | secondary | `arstechnica.com/ai/feed/` |

### Skipped, with reasons

| Source | Why skipped |
|---|---|
| **Anthropic** | No public feed found. `/rss.xml`, `/news/rss.xml`, `/feed.xml` and `/news/feed.xml` all returned 404. Not scraped — documented as a future candidate. |
| **Meta AI** | Same. `ai.meta.com/blog/rss/` and `/feed/` both 404. |

Both are worth re-probing periodically. Adding either is an `INSERT` into `news_sources`,
not a code change.

**All nine seeded feeds are RSS 2.0.** Atom parsing is implemented and tested against
fixtures, but no seeded source currently serves Atom — worth stating plainly rather than
implying the format is exercised in production.

## 3. Fetching

`backend/app/news/feeds.py`. `HttpFeedFetcher` implements the Phase 1 `NewsSourceFetcher`
seam.

- 20s timeout, redirects followed.
- **5 MB response cap, enforced while streaming** — a hostile or broken feed cannot exhaust
  memory, because the limit trips before parsing rather than after.
- `User-Agent: JobsVsAI-NewsBot/1.0 (+https://jobsvsai.com/about)` — a pipeline reading free
  feeds should be attributable.
- Both feed date formats parse: RFC 822 (RSS) and ISO 8601 (Atom). **An unparseable date
  becomes `None`, never a guess** — a wrong date silently corrupts both the lookback and the
  near-duplicate window.
- One malformed *entry* is skipped; one malformed *document* fails that source only.

### Parser choice: `defusedxml` + stdlib, not `feedparser`

Measured, not assumed. Stdlib `ElementTree` **expands internal entities** — a billion-laughs
document parses successfully — while refusing external ones. That is a denial-of-service
vector on input we do not control, so `defusedxml` (small, maintained, purpose-built) does
the parsing and refuses entity declarations outright.

`feedparser` was considered and rejected: we need six fields per entry, and its liberal
coercion of malformed input is a liability in a pipeline whose defining property is
determinism.

### Source failure handling

Every source is fetched, parsed and recorded independently. A failure increments
`news_sources.consecutive_failures`, writes `last_error`, and is appended to the run's
`errors` array — so a persistently broken feed is *visible* rather than silently empty. A
success resets the counter. **One failing source never costs another source's items**, which
is asserted by test rather than assumed.

## 4. URL normalisation

`canonicalise_url` — deterministic, and the basis of exact dedupe.

- Scheme normalised to `https` (http and https of one article are one article).
- Host lowercased, leading `www.` removed.
- Fragment removed; trailing slash removed.
- Tracking parameters stripped: all `utm_*`, `gclid`, `fbclid`, `mc_*`, `ref`, `source`,
  `at_*`.
- **Meaningful query parameters preserved** (`?id=42&page=2`), because older CMSs select the
  article with them.
- **Path case preserved.** Plenty of sites serve different articles from paths differing only
  in case, and over-normalisation merges real stories — the failure that cannot be undone.

## 5. Content hash

SHA-256 over `source_id` + normalised title + normalised excerpt. Nothing time-varying is
included, so **re-fetching an unchanged entry reproduces the same hash** and the UNIQUE
constraint absorbs it.

Scoped by source, matching `UNIQUE (source_id, content_hash)`: the same wording from two
outlets is two legitimate pieces of provenance about one event. Collapsing them here would
discard that; cross-source overlap is the near-duplicate check's job.

## 6. Exact deduplication

Two axes, both enforced by the schema and both probed before insert:

1. `canonical_url` — globally unique.
2. `(source_id, content_hash)` — unique within a source.

Inserts use `ON CONFLICT DO NOTHING`, so a concurrent run or a feed repeating an entry
mid-document cannot fail the batch. A no-op insert is counted as an exact duplicate. **No
duplicate row is created for an exact match** — the existing row already is the record.

## 7. Near-duplicate detection — `news-dedupe-v1`

Catches one event announced under different headlines. No embeddings, no vector store, no
LLM.

1. Normalise: lowercase, strip punctuation, remove stop words — including launch verbs
   (*introducing*, *announcing*, *launches*, *available*, *unveils*), which appear in nearly
   every announcement and therefore identify nothing.
2. Compare the surviving tokens as a set **and** as 2-word shingles.
3. Score = mean of the two Jaccard values. Token overlap alone treats reordered headlines as
   identical; shingles alone are brittle against one inserted word.
4. Compare only against items fetched in the **last 48 hours**, excluding items already
   marked duplicate (chaining duplicates builds a drift chain where the last item resembles
   the first not at all).
5. Take the **best** match above threshold, not the first.

**Threshold 0.55**, calibrated rather than guessed:

| | Score range |
|---|---|
| Genuine restatements ("OpenAI launches GPT-X" / "Introducing GPT-X" / "GPT-X is now available") | 0.58 – 1.00 |
| Different events sharing company, verb and product family ("NVIDIA announces H200 GPU" vs "…B300 GPU") | 0.00 – 0.38 |

The populations are widely separated, so the exact value inside the gap matters far less
than being inside it.

**Deliberately biased toward false negatives.** Merging two unrelated stories destroys a
candidate no later stage can recover; missing a duplicate costs one editor glance. A
consequence worth stating: a heavily-framed restatement ("Introducing X, our most capable
model yet") may score below threshold and survive as a separate candidate. That is the
intended trade, not an oversight.

Duplicates are **kept, not dropped** — `duplicate_of_ingest_item_id` links the row to what it
duplicates, and `near_duplicate_similarity` records how sure we were.

## 8. Relevance prefilter — `news-relevance-v1`

A **prefilter**, not an editorial judgement. Its only question is whether an item is
plausibly worth a Phase 3 generation call.

### Scoring (0–100)

| Band | Max |
|---|---|
| AI-specific terminology | +40 |
| Technical / product / capability language | +25 |
| Automation & work relevance | +20 |
| Trusted AI-focused source | +15 |
| Corporate / financial negatives | down-weighted, capped, never absolute |

**Presence-based, not count-based.** Counting hits was implemented first and rewarded exactly
the wrong text: a real headline ("Introducing GPT-5") carries one or two vocabulary hits while
a keyword-stuffed corporate post carries many. What matters is whether a *category* of
evidence is present, and whether it reached the **title** — title hits score roughly double.

**Ambiguous words** (*model*, *agent*, *assistant*, *vision*, *reasoning*) score only with
supporting AI context or an AI-specific source. "Fashion model announces new agency
partnership" scores 0.

**The source floor.** An item from a tier-1 AI-specific source clears the candidate bar even
when its wording is opaque — this is what lets *"Introducing Operator"* through, the case no
keyword filter can reach. It is withheld when negative signals are present, **and requires at
least one positive signal**: origin alone is not evidence. "Lab opens new office in Dublin"
from a frontier lab is correctly ignored.

**Negatives are down-weighting, never disqualifying.** "OpenAI raises $5B and launches GPT-6
frontier model" is a model story that happens to mention funding, and scores 80.

### Thresholds

| Score | Outcome |
|---|---|
| `< 40` | `ignored` |
| `>= 40` | `candidate` |
| `>= 60` | candidate, flagged **confident** (queue sorts these first) |

Both thresholds are module constants, versioned with the policy, and tested at their
boundaries.

### Calibration

| Story | Score | Outcome |
|---|---|---|
| "Introducing GPT-5, our most capable model" | 80 | candidate, confident |
| "Our AI agent can now use a computer to complete tasks" | 90 | candidate, confident |
| "Humanoid robot learns warehouse picking autonomously" | 75 | candidate, confident |
| "New benchmark shows LLM agents automating support tasks" | 91 | candidate, confident |
| "Introducing Operator" (tier-1 AI source) | 40 | candidate |
| "Introducing Operator" (generic source) | 25 | ignored |
| "AI company raises $5B in Series D funding" | 16 | ignored |
| "OpenAI appoints new chief financial officer" | 0 | ignored |
| "Fashion model announces new agency partnership" | 0 | ignored |

## 9. Status lifecycle

```
feed entry
   ├─ outside lookback window ──────────────> not stored (counted)
   ├─ exact duplicate ──────────────────────> not stored (counted)
   ├─ near duplicate ───────────────────────> stored as `duplicate`, linked
   ├─ relevance < 40 ───────────────────────> stored as `ignored`
   ├─ relevance >= 40 ──────────────────────> stored as `candidate`
   └─ relevance >= 40 but past run ceiling ─> stored as `new` (next run picks it up)
```

`processed` is reserved for **conversion into an article** and is not settable from triage —
an item becomes processed by being converted, never by an opinion about it. Admin triage can
set `candidate`, `ignored` or `new` only; the repository refuses anything else.

## 10. Volume control

Feeds carry years of history — **the OpenAI feed alone holds 1,143 entries**. Without limits
the first production run would ingest the entire archive.

| Control | Default | Setting |
|---|---|---|
| Lookback window | 48 h | `NEWS_LOOKBACK_HOURS` |
| Entries inspected per feed per run | 40 | `NEWS_MAX_ENTRIES_PER_FEED` |
| Candidates promoted per run | 60 | `NEWS_MAX_CANDIDATES_PER_RUN` |

An entry with **no usable date is admitted** — a feed that omits or malforms dates would
otherwise be silently invisible, and exact dedupe absorbs the repeat. Past the candidate
ceiling, an item is stored as `new` rather than dropped, so the next run picks it up without
re-fetching.

## 11. Scheduling

Existing Redis/RQ worker. No Celery, no Kafka, no new scheduler process.

`worker/news_jobs.py`:
- `fetch_news_sources(triggered_by)` — the RQ job.
- `enqueue_ingestion(queue, triggered_by)` — enqueues one run; returns `None` immediately
  when news is disabled.
- `fetch_interval_seconds()` — reads `NEWS_FETCH_INTERVAL_MINUTES` (default 120) at call
  time, so cadence is configuration, not compiled in.

**`NEWS_ENABLED=false` makes a run a safe no-op**: it returns `skipped` without opening a
feed connection or writing a run row. Verified by test.

**No production schedule is active.** The capability exists; turning it on is a separate,
deliberate act.

## 12. Observability

`news_ingestion_runs` — one row per run: sources attempted/succeeded/failed, items
fetched/new/exact-duplicate/near-duplicate/ignored/candidate/outside-window, duration,
policy version, window settings, per-source `errors`, and who triggered it. Counters only;
no feed content is stored.

Per-source health lives on `news_sources`: `last_fetched_at`, `last_success_at`,
`last_error`, `consecutive_failures`.

## 13. Admin incoming queue

`/admin/news/incoming`, behind the existing admin auth. Tabs: Candidates · New · Ignored ·
Duplicates · Processed, with counts and a last-run summary.

Each card shows source, trust tier, relevance score, matched signals in readable form,
near-duplicate similarity and target, original title, plain-text excerpt, source publication
date, fetched time, and a link to the original.

Actions: **Ignore** · **Restore candidate** · **Create draft** · **Fetch feeds now**.

**Create draft** produces an empty draft with the source already attached — headline seeded
from the source title for findability, `what_happened` and `why_it_matters_for_jobs` empty,
no impact assessment, no generation provider. Phase 2 writes no prose. The ingest item
becomes `processed`.

## 14. Security and sanitisation

- Feed XML parsed by `defusedxml`; entity declarations refused.
- Response size capped during streaming.
- **Feed HTML is reduced to plain text at ingestion**, once, at the boundary — so no feed
  markup is stored and none can reach a template.
- **Decode-then-strip order.** The obvious order is wrong and was a real bug caught by test:
  stripping tags first leaves `&lt;script&gt;` untouched, and the later decode turns it into
  a live `<script>`. Entities are decoded first so the stripper can see the tag, with a
  second pass covering one level of double encoding.
- Excerpts capped at 600 characters.
- Outbound links carry `rel="noopener noreferrer nofollow"`.

## 15. Copyright

No full article text is ingested, stored or rendered. Only the feed-provided title, a bounded
excerpt, the URL and metadata. **Excerpts are internal triage material** — they appear in the
admin queue and nowhere else, and are never republished as JobsVsAI prose. The public page
still carries only JobsVsAI writing plus attribution and a link out.

## 16. Separation from occupation scoring

Migration 030 adds no reference to any occupation or scoring table. The Phase 1 guarantee is
re-asserted for the Phase 2 pipeline by
`test_ingestion_never_touches_occupation_scoring`, which runs a full ingestion and checks
occupation scores, snapshots, publications, promotion runs and the active model are
unchanged.

## 17. Phase 3 handoff

A `candidate` row carries everything a generation call needs: source identity and trust tier,
original title, bounded excerpt, canonical URL, feed categories, and a relevance score with
its matched signals. The handoff is:

```
candidate -> Gemini one structured call -> semantic relevance confirmation
          -> original JobsVsAI brief + tags + job areas + impact factors
          -> news-impact-v1 (unchanged) -> draft | review_required
          -> admin approval -> publish
```

`news-impact-v1` does not learn that a provider exists. Nothing in Phase 3 should need to
modify the ingestion pipeline; it consumes `status='candidate'` and sets `processed`.

---

# Supervised Live Feed Validation — 2026-08-23

One controlled run against real feeds, on `jobsvsai_test` only, with `NEWS_ENABLED=true`
supplied per-process. No env file was edited; the default remains false. No scheduler was
enabled, no LLM was called, production was not touched. All data created was removed
afterwards and the removal verified.

## Headline finding: the 48h lookback yields nothing on a normal day

The first run used every default. **All 9 sources fetched and parsed successfully, and all
238 entries were rejected by the lookback window. Zero items were stored.**

| Source | Newest item | Age at run time | Inside 48h? |
|---|---|---|---|
| Google DeepMind | 2026-08-21 11:59 | 52.8h | no |
| Ars Technica | 2026-08-21 11:00 | 53.7h | no |
| Hugging Face | 2026-08-21 00:00 | 64.8h | no |
| Microsoft Research | 2026-08-20 16:00 | 72.8h | no |
| MIT Technology Review | 2026-08-20 15:42 | 73.0h | no |
| NVIDIA | 2026-08-20 13:00 | 75.7h | no |
| Mistral AI | 2026-08-20 12:00 | 76.7h | no |
| OpenAI | 2026-08-20 07:00 | 81.8h | no |
| Google AI | 2026-08-19 19:00 | 93.8h | no |

The closest item missed the window by under five hours. This is not a defect: **first-party
AI labs publish every few days, not daily.** For steady-state polling every 2 hours a 48h
window gives 24× redundancy against missed runs, so the default is right for its purpose.

What it does mean is that **a cold start ingests almost nothing.** The first production run
should pass a wider one-off window — `run_ingestion(lookback_hours=…)` already takes one —
rather than relying on the polling default. Worth deciding deliberately before enabling
ingestion, not discovering on the day.

Because the default window produced no data at all, relevance and dedupe could not be
observed under it. A **separate observation pass at 168h** was used for the quality review
below. Every other cap stayed at its default (per-feed 40, 5 MB, 20s, sanitisation, dedupe).
The 48h default was not changed.

## Sources exercised

All nine, all **RSS 2.0**, all HTTP 200, all parsed. Zero failures across three runs.

| Source | KB | Entries in feed | Considered | Candidates | Ignored |
|---|---|---|---|---|---|
| OpenAI | 678 | 1,143 | 40 | 11 | 3 |
| Hugging Face | 243 | 846 | 40 | 4 | 1 |
| Mistral AI | 22 | 81 | 40 | 1 | 0 |
| Google DeepMind | 73 | 100 | 40 | 1 | 0 |
| Ars Technica | 71 | 20 | 20 | 4 | 3 |
| Google AI | 31 | 20 | 20 | 2 | 0 |
| NVIDIA | 249 | 18 | 18 | 1 | 1 |
| MIT Technology Review | 137 | 10 | 10 | 4 | 2 |
| Microsoft Research | 266 | 10 | 10 | 1 | 0 |

The per-feed cap did real work: OpenAI's feed alone holds **1,143 entries** and Hugging
Face's 846. Without the cap a single run would have examined nearly 2,000 items.

## Data quality on 39 live items

| Check | Result |
|---|---|
| Missing source date | 0 |
| Future-dated | 0 |
| Timezone handling | all 39 stored tz-aware; all feeds used RFC 822 |
| Excerpts containing any tag | 0 |
| Excerpts containing script/onerror | 0 |
| Excerpts containing undecoded entities | 0 |
| Excerpts with collapsed whitespace violations | 0 |
| Longest excerpt | 388 chars (cap 600) |
| URLs with utm/gclid/fbclid | 0 |
| URLs with a fragment | 0 |
| URLs still carrying `www.` | 0 |
| Non-https URLs | 0 |
| Distinct canonical URLs / content hashes | 39 / 39 — no collisions |
| Source attribution | every source resolved to exactly one host, all correct |

Six titles carried non-ASCII characters (curly apostrophes, U+2019) and survived intact —
`The Defender’s Window`, `We still don’t know how people are really using AI`. Five items had
no excerpt at all, which the pipeline handles as absent rather than empty.

**No parser, date or encoding defect was found.** Nothing here required a code change.

## Relevance quality — and one real calibration

The live sample exposed **two systematic false-negative patterns**, each with multiple
instances. False negatives are the harmful direction: a false positive costs one editor
glance, a false negative never reaches Phase 3 at all.

### Pattern A — model family names were entirely absent from the vocabulary

The single largest gap. A headline naming a model but never the word "model" matched nothing.

### Pattern B — exact token matching could not see morphological or version variants

`robotic` did not match `robot`; `autonomy` did not match `autonomous`; and critically
`gpt-5.6` did not match `gpt`, because real headlines always carry a version suffix.

### Before / after on the live cases that motivated the change

| Live headline | Before | After |
|---|---|---|
| "Replit expands access to software creation with GPT-5.6 Luna" | 15 ignored | 40 candidate |
| "Former SpaceX engineers are building a robotic factory for making steel parts" | 26 ignored | 66 candidate |
| "Grok exfiltrates user data when malicious instructions are encrypted" | 26 ignored | 46 candidate |

The second is the clearest miss: automation of manufacturing work is squarely the subject
JobsVsAI exists to cover.

### The change

Vocabulary only — no weight, threshold or structural change:

- Model families added to `AI_TERMS`: gpt, chatgpt, claude, gemini, llama, grok, qwen,
  deepseek, sora, codex, copilot, whisper, stable diffusion.
- Morphological variants: `robotic`, `robots`; capability verbs `introduces`, `expands`,
  `expanding`, `powered by`, `brings`, `adds`; work terms `autonomy`, `factory`,
  `assembly line`, `fulfilment`.
- **Version-suffix-aware token matching**: a family name matches when followed by a digit,
  hyphen or dot, so `gpt-5.6`, `llama3` and `gemini-1.5` match their family. The suffix rule
  is deliberately narrow — `aid`, `aids`, `sorafenib` and `grokking` all still match nothing,
  which is pinned by test.

### Policy version: still `news-relevance-v1`

Changing scoring under an unchanged version label normally breaks auditability. It does not
here, and only for a specific reason: **no row scored by the previous vocabulary survives.**
All 39 validation items were deleted, and Phase 2 has never run in production, so no stored
triage decision becomes unexplainable.

**Once ingestion runs for real, this reasoning expires — any vocabulary change after that
requires `news-relevance-v2`.**

Six regression tests pin every live case that motivated the change, plus the negative
controls and the over-match guard.

### Distribution after retuning

39 items → **33 candidates, 6 ignored**, up from 29/10.

Still ignored, all defensible: a GeForce NOW gaming post, `OpenAI joins PORTS-Pike project`
(corporate partnership), a sponsored "hidden revenue streams" piece, a robot-ethics essay,
an AI-harms story, and an opaque Hugging Face infrastructure post with no excerpt at all.

### False positives accepted

The filter is permissive by design, and the retune widened it. Known weak candidates:
`What Flock’s defenders are missing` (41, surveillance policy), `New policy ideas for the
Intelligence Age` (55), `Strengthening democratic oversight in national security` (50), and
`ChatGPT Ads expands across Europe` — which the vocabulary change moved from 15 to **80**,
its highest-scoring false positive. An advertising expansion is not a capability story.

These are left in deliberately. Semantic judgement is Phase 3's job; the prefilter's job is
to remove obvious junk without discarding anything a model should get to see.

## Near-duplicate observations

**Zero near-duplicates detected across 39 live items**, and inspection found none that were
missed — the sample contained no two headlines describing the same event. Real cross-source
duplication needs several outlets covering one launch inside the window, which this sample
did not contain.

The threshold is therefore **still calibrated only against constructed cases**, not live
data. It was not changed. This remains genuinely unvalidated in production conditions and is
the weakest-evidenced part of Phase 2.

## Idempotency

Run 2, identical settings, no feed change:

| | Run 1 | Run 2 |
|---|---|---|
| Entries fetched | 238 | 238 |
| Rejected by window | 199 | 199 |
| New items stored | 39 | **0** |
| Exact duplicates | 0 | **39** |
| Candidates / ignored in queue | 33 / 6 | 33 / 6 (unchanged) |

The stored content-hash set was byte-identical before and after, which proves hashes are
stable across re-parsing of the same feed. No duplicate queue noise.

## Admin queue and public non-exposure

The queue returned all 33 candidates with every field it needs: source, trust tier, source
publication date, fetched time, status, relevance score, policy version, matched signals with
their point breakdown, and the original URL.

Draft-from-candidate preserved provenance exactly — source name, URL, original title and
source publication date carried across; `what_happened` and `why_it_matters_for_jobs` empty;
no impact, no generation provider. The candidate moved to `processed`.

Public exposure, checked through the real API: `/api/v1/news` returned 0 articles, the
sitemap 0 entries, `/api/v1/news/incoming` 404, unauthenticated `/admin/news/incoming` 401,
and the created draft 404 by slug. **No ingest item became public by being ingested.**

## Atom

Still **not live-tested**. All nine seeded feeds are RSS 2.0. The Atom parser is implemented
and fixture-tested; no real Atom source has been validated. No source research was done as
part of this task.

## Cleanup

`jobsvsai_test` returned to its exact pre-run state: 9 sources (9 enabled), 0 ingest items,
0 ingestion runs, 0 articles, 0 article-source links. Per-source health fields written by the
run (`last_fetched_at`, `last_success_at`, `last_error`, `consecutive_failures`) were reset;
source *configuration* was preserved.

The dev database was never targeted and is unchanged. Occupation state throughout: 1 real
promotion run, 507 live scores, 507 public occupations, 11 legacy rows, JVS 1.0.3 active.

After the change: **247 tests pass**, frontend builds clean.
