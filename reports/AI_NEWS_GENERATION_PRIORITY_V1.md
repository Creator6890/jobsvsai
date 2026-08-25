# news-generation-priority-v1 — ordering the generation queue

**Recommendation: READY FOR LIVE INGESTION.** Reasoning in §13, including why the residual
ranking questions do not block ingestion.

Validated against the same 168-hour production corpus as the first dry run, on release
`59a6578b8305`. Nothing was deployed, nothing was written, generation stayed disabled.

---

## 1. Why AI relevance and JobsVsAI priority are separate

`news-relevance-v1` answers a question about the item: *is this plausibly AI news at all?* It
is deliberately permissive, because a false negative loses a story forever while a false
positive costs one editor glance.

This policy answers a question about us: *how valuable is this candidate to spend one scarce
generation call on?*

The first production dry run proved these are different questions. A datacentre hardware
announcement scored **90** on relevance — the highest of the entire run — because it carried a
dense spread of AI vocabulary (`agentic, ai, inference, announced, breakthrough, agents,
factory`). A Stanford study on AI displacing entry-level workers scored **81**. Both readings
are correct: both are AI news. For a career intelligence platform the ordering is exactly
backwards, and with generation capped at 5 calls a day, ordering is the whole game.

Folding the two together would be the worst option: a filter simultaneously too strict to work
as a safety net and too vague to work as an editor. So relevance still decides what enters the
queue, and priority decides only what leaves it first. **`news-relevance-v1` was not modified.**
No bug was found in it — it was doing its job.

The layering is now:

```
feed → news-relevance-v1 → candidate → news-generation-priority-v1 → Gemini → human review
```

Priority controls order only. It rejects nothing, deletes nothing, changes no status, and has
no public surface.

## 2. Exact deterministic formula

`backend/app/news/priority.py`. Presence-based and title-weighted, matching relevance —
counting occurrences rewards keyword-stuffed corporate posts, which is the failure being
corrected.

| Component | present | in title |
|---|---|---|
| A work / labour | +30 | +55 |
| B automation / agents | +18 | +32 |
| C capability advancement | +16 | +28 |
| D commercial deployment | +10 | +16 |
| E physical automation | +16 | +28 |
| empirical evidence | +5 | +8 |
| configured source (tier ≤ 2) | +4 flat | — |
| each depriority family | −12 | −18 |
| title-only candidate | −5 | — |

Penalties are capped at −40 in total. The result is clamped to 0–100.

**The substance gate:** an item matching none of A–E is capped at `GENERIC_CEILING = 15`,
regardless of how much AI vocabulary it carries. This is what stops announcement language from
ranking.

Bands: **HIGH ≥ 60**, **MEDIUM ≥ 35**, **LOW** below.

### Storage decision — no migration

Priority is **derived, not persisted.** It is a pure function of fields the row already holds
(`original_title`, `original_excerpt`, `feed_categories`) plus the source's `trust_tier`.
Persisting it would add a column that could only ever disagree with the policy, and every
policy revision would need a backfill to stay truthful. The eligible queue is bounded by the
per-run candidate ceiling, so ranking in Python costs nothing that matters. **Migration count
added by this work: zero.**

## 3. Positive signals

- **A. Work and labour** — jobs, employment, workforce, hiring, layoffs, wages, productivity,
  reskilling, displacement, entry-level, future of work. Plus **occupational roles**:
  developer, engineer, analyst, designer, lawyer, paralegal, accountant, journalist,
  translator, radiologist, nurse, teacher, student, classroom, customer support. An item that
  names an occupation is about work even when it never says "jobs" — and occupations are what
  this platform is built on.
- **B. Automation and agents** — automation, autonomous, agentic, ai agent, multi-agent,
  computer use, tool use, task execution, workflow, orchestration, self-driving, back office.
- **C. Capability advancement** — frontier model, model release, reasoning, multimodal, long
  context, code generation, coding, SWE-bench, benchmark, state of the art, open weights,
  codex, copilot, software creation, agent mode.
- **D. Commercial deployment** — enterprise, deployment, rollout, adoption, customers, case
  study, integration, at scale, plus quantified outcomes: cuts, reduced, saves, savings,
  backlog, teams.
- **E. Physical automation** — robot, robotics, humanoid, factory automation, warehouse
  automation, assembly line, autonomous vehicle, robotaxi, drone, embodied.
- **Empirical evidence** — study, research, survey, findings, economists, data. Small on
  purpose: it cannot carry an item alone.

Bare `ai`, `model`, `announced` and `introducing` earn **nothing**. They say only that a post
exists.

## 4. Negative / depriority signals

Four compact families, each subtracting rather than rejecting:

- **promotional** — ads, advertising, sponsorship, subscription, pricing, discount,
  partnership, award, conference, keynote, anniversary.
- **consumer** — teen, kids, parental, game, gaming, geforce, music, photo, recipe, shopping,
  travel, sports.
- **hardware** — gpu, chip, silicon, datacenter, ai factory, rack, superchip, interconnect,
  nvlink, teraflop, per watt, throughput, supercomputer, full production.
- **corporate** — funding round, valuation, ipo, earnings, investor, acquisition, appoints,
  board of directors.

Nothing here is a blacklist that removes an item. The lowest achievable score is 0, which
still leaves the candidate in the queue for manual selection.

Two exclusions are deliberate and were learned from the corpus. **"faster"** and
**"efficiency"** are absent from the deployment family: they read as workplace vocabulary but
are hardware-benchmark vocabulary first. Adding "efficiency" during calibration lifted
NVIDIA's *"Up to 30x More Work Per Watt"* from 23 to 39 (MEDIUM) — the exact category this
policy exists to push down. It is now a regression test. Likewise **bare "factory"** is absent
from physical automation, because "AI factory" is datacentre branding, not robotics.

## 5. Source treatment

Source tier contributes **+4 flat for any configured source (tier ≤ 2) and does not separate
tier 1 from tier 2.** This is deliberate. A first-party vendor announcement must never outrank
substantive labour research because the vendor happens to be a frontier lab. Both a frontier
lab and a quality outlet are credible; what differs between their items is topic, and the
families already carry topic. Two tests pin this: one asserts tier-2 labour research outranks
a tier-1 vendor ad, another asserts the same item scores identically at tier 1 and tier 2.

## 6. Handling missing excerpts

The dry run found 5 of 37 in-window entries with no excerpt: **all four Hugging Face items and
one Mistral item.** Hugging Face supplies no summary in its feed at all.

**Does title-only input materially weaken the pipeline?** Yes, but modestly and unevenly. The
priority policy and the generator both read title plus excerpt, so a title-only candidate is
judged on roughly a third of the text — the median excerpt is 149 characters against a
headline of perhaps 60. For a descriptive headline ("Measuring benchmark optimization in
speech recognition") little is lost. For an opaque one the excerpt is the only disambiguator.
The generator would produce a thinner brief from a headline alone, but the semantic stage
still gets a real subject and can still refuse.

The handling is therefore a **−5 penalty and a visible flag**, not a rejection. Five points
rarely crosses a band boundary, so a major release on a bare headline still ranks; the CLI
marks such rows with `!` so the operator can see the judgement rests on a headline. No article
pages were scraped, and none should be: the feeds genuinely do not carry summaries, and that
fact is kept visible rather than papered over.

## 7. Old top 15 — relevance only

The order generation would have consumed before this change.

| # | AI | Source | Title |
|---|---|---|---|
| 1 | **90** | NVIDIA | With Groq 3 LPX in Full Production, NVIDIA Extends Vera Rubin |
| 2 | 81 | Ars Technica | AI is hitting entry-level jobs hardest, Stanford study finds |
| 3 | 80 | Google DeepMind | From Atari to EVE Online: Building on 15 Years of AI Research |
| 4 | 80 | Hugging Face | Measuring benchmark optimization in speech recognition |
| 5 | 80 | Hugging Face | Up to 3.2x Faster Inference with LFM2.5-DSpark |
| 6 | 80 | Mistral AI | Agentic Search |
| 7 | 80 | OpenAI | Introducing AI Futures |
| 8 | 80 | OpenAI | Stampli cuts launch hours by 68% using ChatGPT Work |
| 9 | 80 | OpenAI | Replit expands access to software creation with GPT-5.6 |
| 10 | 80 | OpenAI | ChatGPT Ads expands across Europe |
| 11 | 80 | OpenAI | Pacing model development in an era of cyber-critical capabilities |
| 12 | 80 | OpenAI | Introducing ChatGPT for Teens |
| 13 | 75 | Hugging Face | Wire It, Run It, Deploy It: AI Workflows in Gradio |
| 14 | 75 | NVIDIA | How XPUs Meet a World-Class AI Factory |
| 15 | 70 | OpenAI | Advancing price-performance for developers with GPT-5.6 |

Ten of the fifteen are tied at 80, so the effective ordering inside the block was publication
date — an accident, not a judgement. Datacentre marketing led the queue; advertising and a
teen product feature outranked the only labour-market study in the corpus.

## 8. New top 15 — generation priority

| # | AI | Priority | Band | Title | Signals |
|---|---|---|---|---|---|
| 1 | 67 | **87** | HIGH | Asana cleared 5 years of engineering work in 2 weeks with Codex | engineering work, codex |
| 2 | 81 | **67** | HIGH | AI is hitting entry-level jobs hardest, Stanford study finds | employment, entry-level, jobs, occupations, research |
| 3 | 70 | 59 | MEDIUM | Advancing price-performance for developers with GPT-5.6 | developers |
| 4 | 61 | 59 | MEDIUM | How to encourage smarter AI use in the classroom | classroom, students |
| 5 | 80 | 52 | MEDIUM | Agentic Search | agentic, retrieval |
| 6 | 70 | 50 | MEDIUM | Offering Zero Data Retention for frontier models | frontier model, customers |
| 7 | 80 | 36 | MEDIUM | Stampli cuts launch hours by 68% using ChatGPT Work | codex, cuts |
| 8 | 55 | 34 | LOW | Partnering with CodeAI to prepare the first AI generation | students |
| 9 | 80 | 32 | LOW | Replit expands access to software creation with GPT-5.6 | software creation |
| 10 | 80 | 32 | LOW | Pacing model development in an era of cyber-critical capabilities | capabilities |
| 11 | 46 | 32 | LOW | Microsoft Copilot reveals secret input that allowed it to be hacked | copilot |
| 12 | 75 | 31 | LOW | Wire It, Run It, Deploy It: AI Workflows in Gradio | workflows |
| 13 | 46 | 30 | LOW | Flight attendants freaked out that Google is buying employee data | workers, data |
| 14 | 80 | 27 | LOW | Measuring benchmark optimization in speech recognition | benchmark |
| 15 | 67 | 27 | LOW | How Much Memory Does Your Agent Actually Need? | memory |

Band distribution across the 33 candidates: **HIGH 2, MEDIUM 5, LOW 26** (plus 4 relevance-
ignored items, all 0).

## 9. Notable improvements

- **The headline inversion is fixed.** NVIDIA Groq/Vera Rubin went from **rank 1 to rank 21**
  (relevance 90, priority 20). All three NVIDIA hardware posts are now outside the top 15.
- **Applied productivity evidence rose to the top.** The Asana Codex story — AI compressing
  five years of engineering work into two weeks — went from **rank 21 to rank 1**. It scored
  4 on the first calibration pass and was the worst false negative of the exercise; adding
  occupational roles fixed it. Stampli's quantified 68% reduction moved from the 80-point tie
  into MEDIUM.
- **The queue now shows the intended mixture.** The top seven contain applied enterprise
  adoption, direct labour research, coding capability, education/teaching, agent capability
  and measured productivity outcomes.
- **Promotional and consumer content collapsed.** ChatGPT Ads 80 → **0**, ChatGPT for Teens
  80 → **0**, GeForce gaming → **0**, "Introducing AI Futures" 80 → **4**.
- **Generic vocabulary no longer ranks.** "Introducing AI Futures" cleared 80 on relevance from
  two signals (`ai`, `introducing`). The substance gate caps it at 15.

## 10. Remaining false positives

- **"Offering Zero Data Retention for frontier models" (priority 50, rank 6)** — the clearest
  one. A data-governance announcement matching `frontier model` and `customers`. It is genuine
  AI substance but low work relevance, and it currently outranks the Stampli productivity
  story.
- **"Microsoft Copilot reveals secret input that allowed it to be hacked" (32)** — a security
  story lifted by `copilot`. Adding `copilot` as a coding-capability term was net positive but
  catches security coverage as a side effect.
- **"Flight attendants freaked out that Google is buying employee data" (30)** — matches
  `workers` and `employee data`, but it is a privacy story, not a labour story. LOW is roughly
  the right place; it is only mildly overranked.

## 11. Remaining false negatives

- **"Kids outlearn AI—and we still don't know why" (priority 0)** and **"We still don't know
  how people are really using AI" (priority 9)** — both MIT Technology Review, both substantive
  independent research about how people actually use AI. These are the ones that bother me
  most. They score near zero because the policy has no vocabulary for AI *usage* research that
  never names an occupation or an automation mechanism. The evidence bonus alone cannot lift
  them past the substance gate. Worth addressing before generation is enabled.
- **"From Atari to EVE Online: 15 Years of AI Research" (0)** — a DeepMind research
  retrospective, deprioritised as gaming content. Defensible for a careers platform, but the
  mechanism is crude: it lost on `game`/`games` in a research post.
- **"AI's recursive self-improvement might not come so quickly" (0)** — capability-trajectory
  commentary with no matching family term.

## 12. Tests

`backend/tests/test_news_priority.py`, 21 tests, using real headlines and paraphrased
summaries from the 2026-08-25 production dry run as regression fixtures.

All nine required cases are covered and passing:

1. Stanford labour study ranks HIGH.
2. NVIDIA datacentre marketing does not outrank it, and is deprioritised for what it is.
3. A frontier agent release with no employment language still ranks HIGH; robotics too.
4. Advertising is deprioritised.
5. Gaming stays LOW.
6. Generic "AI + introducing" cannot exceed the substance ceiling, even from a tier-1 source.
7. Scoring is deterministic across repeated calls, and presence-based rather than count-based.
8. `select_generation_candidates` orders by priority — a DB test with two rows whose relevance
   ordering is the reverse of their priority ordering, asserting the labour study is selected
   first despite the lower relevance score.
9. Architectural isolation, asserted on **imports** rather than prose — the policy legitimately
   scores the word "occupations", so a word-search would be worthless. The module may import
   only `__future__`, `dataclasses`, `typing` and `app.news.relevance`, and must contain no SQL.

Plus regression tests for the power-efficiency lift, the Asana false negative, source-tier
neutrality, and title-only handling.

**Full suite: 421 passed, 0 failed** via `./scripts/run-tests.sh` against `jobsvsai_test`.
Baseline was 400; the 21 new tests account for the difference and no existing test changed
behaviour.

`relevance._matches` was renamed to `relevance.matches` so the priority policy could reuse the
phrase-aware matcher rather than duplicate it. Mechanical rename, no behaviour change, no
external callers.

## 13. Recommendation

### READY FOR LIVE INGESTION

The reasoning turns on a distinction worth stating plainly: **priority governs generation
order, and generation remains disabled.** Live ingestion stores internal triage rows with no
public route and calls no model. The residual ranking questions in §10 and §11 therefore
cannot cause harm at ingestion time — they can only matter at the moment generation is
enabled, which is a separate gate that must be opened deliberately.

That being so, the case for ingesting now is stronger than the case for another calibration
pass in the abstract. Every calibration so far has been run against a corpus I cannot store,
re-examine, or diff. Real candidate rows in the admin queue would let the next pass work
against persisted data — particularly for the MIT research false negatives, which need
judgement about what "AI usage research" is worth to this platform rather than another
vocabulary guess.

Three things should be true before generation is ever switched on, and none of them block
ingestion:

1. Resolve the AI-usage-research gap (§11). Two substantive MIT pieces scoring 0 and 9 is the
   real remaining defect.
2. Decide whether "Zero Data Retention" at rank 6 is acceptable, or whether governance
   announcements need a depriority family of their own.
3. Re-examine the band thresholds once a larger corpus exists. Two HIGH out of 33 is honest
   for this week's news but is a thin sample to calibrate on.

**The dedupe threshold was not touched.** This run again produced zero exact, near, and
in-run duplicates, so there is still no production evidence for or against 0.55 — it remains
calibrated only on constructed cases. Documented, and deliberately left alone.

### What was not done, by instruction

Nothing was deployed. No live ingestion, no generation, no Gemini call, no publishing, no cron,
no occupation or scoring change, no frontend change, no auto-publish change. Production content
counts are unchanged (`news_ingest_items` 0, `news_articles` 0, `news_ingestion_runs` 0,
`news_sources` 9, source health never written), scoring is unchanged at 507/507/JVS 1.0.3, and
the running containers still resolve all three safety flags false.

The three recalibration runs executed in throwaway `docker compose run --rm` containers with
the changed files mounted read-only, so the deployed release at
`/opt/jobsvsai/releases/59a6578b8305` was never modified. No one-off containers were left
behind.
