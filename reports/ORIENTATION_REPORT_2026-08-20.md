# JobsVsAI — Onboarding Orientation Report

Author: senior product engineer (new joiner)
Date: 2026-08-20
Repository inspected: `C:\Users\Akshay\Documents\jobsvsai` (read-only; no code changed)

Scope of inspection: all six `reports/*.md`, all five `enrichment/*.md` method docs, `ingestion/ONET_MAPPING.md` + `ingestion/reports/onet_30_3_full.md`, the full `scoring/` package, `enrichment/*.py`, 16 of 24 migrations (including every one that defines a formula, gate, taxonomy or namespace), the FastAPI backend and admin API surface, the Next.js public routes and API client, `docker-compose.yml`, and the test file inventory.

I did **not** run the stack or the test suite — there is no database in my environment and no shell available on your machine through this bridge. Every claim below is read from source, not from a live DB. Where I say "cannot verify", that is why.

---

## 1. The business

JobsVsAI is a career intelligence product, not a risk quiz. The acquisition surface is "how does AI affect my job", but the asset being built is a continuously-updated occupational intelligence database whose defensibility comes from the transformation layer sitting on top of public O\*NET data, plus the time series that layer will generate as frontier AI capability moves.

The commercial logic that follows from that: keep the funnel simple (search → occupation page → task-level explanation → safer adjacent careers → transition), monetise first through advertising, education affiliates and job referrals, and hold subscription/B2B until the historical dataset and personalisation actually justify it. Trust is the product. A single obviously-wrong occupation page costs more than a hundred missing ones — which is why the coverage gate, the confidence gate and production isolation are commercial decisions as much as engineering ones.

The core editorial commitment — **exposure ≠ replacement** — is genuinely load-bearing and is implemented, not just asserted. I'll come back to that.

## 2. The proprietary intelligence engine

The pipeline as actually implemented:

```
O*NET task statement
  → deterministic mapper → capability requirement set (1–6 dims, weights sum to 1, per-dim confidence + evidence)
  → Task Capability Fit        (vs Frontier AI Index, commercially deployable track)
  → Automation Feasibility     (capability fit blended with structural constraint resistance)
  → Augmentation Potential     (capability fit × automation-complement curve)
  → Task AI Exposure           = 0.35·Fit + 0.45·Automation + 0.20·Augmentation
  → Occupation AI Exposure     = task-weighted mean, weight = importance × frequency
  → Replacement Risk           = weighted factor model over occupation-level inputs
```

**Capability taxonomy** (`jvs-ai-cap-v1`, migration 008) — 15 dimensions, immutable, append-only. Requirements are stored independently of what AI can currently do, which is what makes a Frontier Index refresh cheap.

**Frontier AI Capability Index** (`frontier-ai-index-v1`, migration 017) — two tracks; `commercially_deployable` populated for 2026-Q3, `technical_frontier` deliberately empty. All 15 values in the onboarding brief match the migration exactly (language generation 97 … fine physical manipulation 10, mobility 12). Benchmark results are stored verbatim as evidence and are explicitly *not* arithmetically converted into the 0–100 index — the index is a JobsVsAI judgement with provenance, which is the right call and worth defending publicly.

**Task Capability Fit** (`calibration.capability_fit_v2`) — for each required capability, `match = logistic((AI_score − required_level) / 14)`, aggregated as a **weight-normalised geometric mean** of matches, then floored by **critical-capability bottleneck caps**. A capability is critical at weight ≥ 0.35, or weight ≥ 0.20 with required level ≥ 70; if a critical capability's match < 50, the task score is capped at `match + 8`. So the bottleneck principle is implemented twice over — geometric aggregation already punishes weak links, and the cap enforces a hard ceiling. Phase 4B replaced Phase 4A's "AI exceeds requirement ⇒ 100" rule, which is what was causing saturation.

**Automation Feasibility** (`automation_feasibility_v2`) — ten fixed-weight constraint domains (human-dependency 0.16, physical-presence 0.14, fine-motor 0.12, consequence-severity 0.12, mobility 0.10, environment-variability 0.10, regulation 0.08, accountability 0.08, data-access 0.05, workflow-integration 0.05). Each level is transformed `100·(level/100)^1.35` (convex — high constraints bite harder), summed into a burden, inverted to resistance, then `0.50·fit + 0.50·resistance`, then capped by per-domain critical bottlenecks above level 65 (physical-presence 0.75, fine-motor 0.80, mobility 0.80, consequence-severity 0.70 …). Constraints come from direct task mappings where available and from versioned occupation proxies otherwise, and using a proxy costs up to 18 confidence points.

**Augmentation Potential** — `fit × (0.15 + 0.85·(1 − automation/100)^0.5)`. A task that is hard to automate but well within AI's capability lands high. This is what lets a surgeon show high fit + high augmentation + low automation feasibility, exactly as the brief describes.

**Structural proxies** — Phase 4D (`phase4d-direct-structural-proxy-v2`, `scoring/phase4d_proxies.py` + migration 023) rebuilt four families directly from O\*NET evidence with explicit aggregation formulas (e.g. physical presence = `0.60·weighted RMS + 0.20·weighted mean + 0.20·mean(top-3 independent signals)`). Occupation title and SOC are **prohibited inputs**. The clinical-consequence enhancer requires three source-backed gates to co-fire and is verified not to trigger for electricians, mechanics, teachers or hairdressers. Missing or suppressed ratings are excluded and remaining weights renormalised — never imputed.

**Occupation-level Replacement Risk** (`phase4b-occupation-score-v2-calibration`, migration 019):

| Factor | Weight | Transform |
|---|---:|---|
| taskAutomationExposure | 0.35 | identity |
| humanDependencyResistance | 0.15 | inverse |
| physicalDependencyResistance | 0.15 | inverse |
| adoptionPressure | 0.15 | identity |
| aiCapabilityProximity | 0.10 | identity |
| labourMarketResilienceResistance | 0.10 | inverse |

Gates: weighted coverage ≥ 70, scale confidence ≥ 70. Confidence = 0.40·coverage + 0.20·mapping + 0.15·frontier + 0.10·source completeness + 0.15·proxy.

Everything is append-only with DB triggers (`prevent_ai_enrichment_history_mutation`), every calculation persists raw inputs, transforms, normalised weights, per-factor contributions, input hashes and reconciliation, and every phase ships a deterministic replay that must match exactly. That is the strongest part of this codebase and it is worth protecting aggressively.

## 3. Technical architecture

Next.js 16.3.1 / React 19 (App Router, TypeScript, zero UI dependencies — impressive discipline) → FastAPI (async SQLAlchemy over asyncpg) → PostgreSQL 17 (+ `pg_trgm` for search) → Redis + RQ worker. Docker Compose for local and prod-ish; migrations mount into `/docker-entrypoint-initdb.d`, so they run **only on a fresh volume** — there is no migration runner, which will matter the moment you deploy.

Scoring is Python in `scoring/`, mounted into both backend and worker. Ingestion is a single 84KB `ingestion/onet_import.py` with an idempotent `import`/`validate` CLI. The admin API is one 83KB `admin.py` with eleven endpoints, all `GET`, all behind HTTP Basic.

Layering is clean and the "no fixture fallbacks, scores precomputed, public requests never calculate" rule in the README holds in the code.

## 4. Current project state

Verified against the repo:

- O\*NET 30.3 fully ingested: 1,016 occupations, 785,599 source records, 988 identities resolved, 28 complex identity cases pending manual review, 878 scoring-ready, 138 insufficient, 179 with at least one incomplete domain, 0 invented allocation weights.
- Validation history reads exactly as the brief describes: 4A pilot (12 occs, saturated) → 4B calibration (no-scale verdict, saturation removed) → 4C 25-occupation validation (directionally right, 13 absolute band failures) → 4D direct proxy reconstruction (13 → 3 failures, all 10 in the reconstructed families resolved, 23/24 pairwise, 0 reversals, 0 regressions, exact replay).
- Phase 5 bounded corpus run complete in namespace `phase5-candidate-2026q3-v1`: 878 attempted, 744 review-ready, 134 coverage-blocked, 10,815 task assessments, 10,253 new deterministic mappings, 562 reused (393 exact task+statement, 169 statement-hash), **0 external AI calls, 0 tokens**, exact replay, 0 reconciliation failures.
- Distributions: AI Exposure μ 59.86 σ 11.13; Replacement Risk μ 51.24 σ 9.46; r = 0.8563.
- 300 warnings / 0 errors: 176 related-SOC discontinuity (14 SOC families), 106 provisional-input sensitivity, 15 single-task dependence, 2 exposure–replacement gap, 1 high-replacement-despite-constraint (Credit Counselors).
- 400-occupation launch cohort identified, `activated = false`.
- Archetype layer: 28 archetypes discovered, flag `occupational_archetype_layer` seeded `enabled=false, production_allowed=false`. Verdict in the report is explicit: do not adopt for scoring.
- Production isolation intact: 11 occupation-score rows, 23 task-score rows, unchanged through 4A→5.

## 5. Frozen methodological decisions I will not touch without explicit approval

1. Exposure and Replacement Risk stay separate metrics with separate formulas.
2. Task capability requirements stay independent of the Frontier Index.
3. Capability ≠ automation; automation ≠ augmentation. Three distinct task outputs.
4. Bottleneck behaviour: geometric aggregation + critical-capability caps + critical-constraint caps.
5. Phase 4D direct structural proxies (`phase4d-direct-structural-proxy-v2`), title/SOC prohibited as inputs.
6. Frontier Index values and their evidence tiers — changed only by a new versioned index that triggers dependency-based recomputation.
7. 70% weighted coverage gate and 70-point scale-confidence gate.
8. Archetype scoring stays disabled.
9. Append-only provenance, deterministic replay, no imputation of missing source data.
10. Production/candidate isolation. No promotion, no activation, without instruction.

## 6. Immediate Phase 6 objective as I understand it

Risk-based triage of the 744 review-ready candidates — starting with the recommended 400 — to produce: a warning taxonomy with severity, counts of affected launch candidates, an exclude list, a safe-to-launch list, unresolved methodological risks, and a final recommended public cohort. Then stop before activation.

The 300 warnings are already typed and persisted, so triage is a query-and-judgement exercise over `phase5_anomaly_findings` and `phase5_occupation_scores`, not a re-run. Given all 400 recommended occupations already have zero anomaly findings, I expect the real work to be (a) auditing whether "zero findings" is actually a strong enough signal, (b) the 14 related-SOC discontinuity families, and (c) the truncation-bias question in §7.

---

## 7. Discrepancies and findings

Ordered by how much they matter for launch. Items 1–5 are things I think need a decision before Phase 6 finishes; the rest are context.

### 7.1 The live site already serves nine occupations with hand-written demo scores

This is the most important thing I found, and it contradicts the mental model in §23 of the brief.

"Public occupations: 0" is true of `occupation_publications.activation_status`. But **nothing in the public read path consults that table.** `backend/app/repositories/occupations.py::BASE_SELECT` joins `occupations` → latest `occupation_scores` and filters on neither `occupation_publications.activation_status` nor even `occupations.is_active`. Same for `/rankings` and `/occupations/search`.

Migration `002_seed_demo_data.sql` seeds 9 occupations (graphic-designer, software-developer, accountant, nurse-practitioner, aircraft-mechanic, brand-strategist, ux-researcher, cybersecurity-analyst, financial-advisor) with **hand-authored scores** — `input_versions: {"occupation":"demo-2026-08"}`. Those numbers never came out of the intelligence engine. `sitemap.ts` calls `getOccupations()` and publishes all of them.

So on any deployed instance, `/jobs/accountant` renders a fabricated 78/63 with a "JVS 1.0.3" model-version badge and full SEO metadata. The isolation discipline that Phases 4A–5 protected so carefully was protecting the *candidate* side of a boundary whose *public* side was never gated.

Suggested fix, and I'd do this before anything else in Phase 6: add the publication gate to the read path (`JOIN occupation_publications p ON … AND p.activation_status = 'public'`, plus `o.is_active`), and either delete the demo seed or mark it non-public. That change alone makes "0 public occupations" true in the product, not just in the table, and makes every later promotion step safe by default rather than safe by omission.

### 7.2 Two live replacement-risk formulas, and the brief only documents one

- `scoring/config.py::DEFAULT_MODEL` — **"JVS 1.0.3"**: task_exposure 0.45, ai_capability_proximity 0.15, human_dependency 0.15, physical_dependency 0.10, adoption_pressure 0.10, market_resilience 0.05. Used by `worker/jobs.py::recalculate_occupation`, which reads the legacy `task_ai_scores` / `ai_capabilities` tables and writes production `occupation_scores`. This is what the public site renders.
- `phase4b-occupation-score-v2-calibration` — the Phase 4B/4C/4D/5 model in §2 above. Different factor names, different weights, different upstream pipeline.

They are not reconcilable by renaming: `market_resilience` vs `labourMarketResilienceResistance` differ in weight (0.05 vs 0.10) and the task-exposure weight differs (0.45 vs 0.35). Promotion is therefore a **model migration**, not a data copy, and the `JVS 1.0.3` badge currently shown on occupation pages will become wrong the moment candidates are promoted. We need an explicit decision: register the Phase 5 model as a new `scoring_model_versions` row and retire 1.0.3, or keep both and never let them meet.

### 7.3 Nothing in the codebase can promote or activate anything

All eleven admin endpoints are `GET`. `occupation_promotion_profiles` and `occupation_publications` are written only by the O\*NET importer. There is no promotion service, no activation endpoint, no editorial-approval workflow, no admin mutation of any kind.

This is correct for where the project has been, but it means "promote approved candidate score snapshots safely / activate approved occupation records" in §27 of the brief is **greenfield build**, not a switch. It should be scoped as such, and it should be built with the same append-only + replay discipline as the scoring phases, because a promotion run is exactly the kind of thing that needs to be auditable and reversible.

### 7.4 A Phase 5 candidate does not fit the production score row

`occupation_scores` has `NOT NULL` on `salary_potential`, `future_demand`, `market_resilience`, `trend` (enum Rising/Stable/Falling) and `confidence` as **TEXT enum** `High|Medium|Low`. Phase 5 produces numeric confidence (0–100), `labour_market_resilience`, and no salary, demand or trend at all.

There is no honest default for salary_potential or future_demand. Filling them to satisfy the constraint would violate "missing data is not zero" in a table that feeds public pages. The options are: migrate the columns nullable, or add a separate production table for engine-derived scores. I'd argue for the latter — it keeps the legacy demo schema and the engine schema from silently merging — but it's a call for you to make.

Also `occupations` (editorial: slug, category_id NOT NULL, summary, verdict) has no populated link to `onet_occupations` / `canonical_occupation_identities`. Launching 400 occupations means generating 400 editorial rows — slug, category, summary, verdict — and `occupation_categories` currently holds only the handful of demo categories. Public occupation pages also read tasks from legacy `occupation_tasks` + `task_ai_scores` and related careers from hand-seeded `career_relationships`, neither of which is fed by Phase 5 or by O\*NET `related_occupations`. **This content/data workstream is on the critical path for launch and I don't see it scoped anywhere.** It is probably larger than the triage itself.

### 7.5 The 70% coverage figure is a stopping rule, not a completeness measure

`enrichment/generate_phase5_candidate_mappings.py` orders unmapped tasks by descending `importance × frequency` and **breaks out of the loop as soon as projected coverage reaches 70%**. That is a sound compute-efficiency decision and entirely consistent with "avoid unnecessary work". But it has two consequences worth stating plainly:

1. Coverage clusters just above the gate **by construction** — median 71.61, P25 70.40, P75 72.98. The Phase 5 report presents this distribution without noting that the mapper produced it deliberately. Read naively it looks like "most occupations barely have enough evidence"; it actually means "the mapper stopped as soon as it had enough". The 134 blocked occupations are the genuinely interesting ones — those are where mapping *everything available* still didn't reach 70%.
2. Every occupation score is a weighted mean over the **highest-importance slice** of its tasks (4,559 tasks were never assessed), implicitly assuming the unmapped tail behaves like the mapped head. Lower-importance tasks plausibly skew more routine and administrative — which would bias exposure *downward* — or more incidental-physical, which would bias it up. Nobody has measured which.

Concrete, cheap suggestion: take a stratified sample of ~40 launch-cohort occupations, map 100% of their weighted tasks with the same deterministic mapper (zero external AI cost, ~1 second of compute each based on Phase 5's 21.9s for 10,253 mappings), and compare full-coverage scores against the 70%-truncated scores. If the mean absolute delta is small and unsigned, the truncation is defensible and we can say so publicly in `/methodology`. If it's systematic, we've found a real calibration problem before launch rather than after. This feels like the highest-value single experiment available in Phase 6.

### 7.6 Regulation affects AI Exposure too, not just Replacement Risk

§18 of the brief lists regulation among Replacement Risk's dimensions. In code, regulation is a **constraint domain inside Automation Feasibility** (fixed weight 0.08, bottleneck cap strength 0.55) — so it flows into task exposure, and therefore into *both* published metrics. That's why `provisional_sensitivity()` has to re-run the whole task pipeline for the regulation counterfactual and reports `regulationNeutralAiExposureDelta` alongside the replacement delta, whereas adoption and labour resilience get cheap closed-form deltas.

Not a bug — the code is right and the brief is a paraphrase. But it matters for triage: regulation is the largest provisional sensitivity driver (up to 7.43 points) *and* it is the only provisional input that moves the headline AI Exposure number. The 106 sensitivity-flagged occupations deserve more weight in exclusion decisions than their "warning" severity suggests.

### 7.7 No caching, no structured data, no canonicals

Every public page is `export const dynamic = "force-dynamic"` and the API client uses `cache: "no-store"` with a 5-second timeout. Precomputation is real (scores are read, never calculated), but there is zero HTTP or ISR caching, so every crawler hit is a live Postgres round trip. At 400 indexed pages plus search-engine crawl traffic that is the first thing that will fall over.

There is no JSON-LD anywhere, and no `alternates.canonical` in any `generateMetadata`. `robots.ts` correctly disallows `/admin/` and `/career-finder/results`. `sitemap.ts` is `force-dynamic` and would emit every occupation the unfiltered `/occupations?limit=500` returns — which, per 7.1, currently includes everything in the table.

All of this is listed in §27 of the brief as expected Phase 6 work, so it is a confirmation rather than a surprise. I flag it because the caching item interacts with 7.1: fixing the publication gate first means the sitemap and cache are correct by construction.

### 7.8 Smaller notes

- **Capability slug names** differ from the brief's labels: `information-retrieval` (not "…& synthesis"), `tool-computer-operation` (brief: "Computer/tool operation"), `interpersonal-social-interaction` (brief: "Social & interpersonal understanding"), `persuasion-negotiation` (brief: "Persuasion, negotiation & influence"). Slugs are the contract used in the mapper and Frontier Index; the brief is a readable paraphrase. All 15 **values** match exactly. No action needed, but public-facing copy should use the slugs' real definitions.
- **Migrations 009, 011–014, 016, 021 exist but I did not read them** (naming indicates hardening, name fixes, benchmark/eval infrastructure and a Phase 4C seed correction). I read every migration that defines a formula, gate, taxonomy or namespace. Happy to close the gap if you want full coverage.
- **`frontend/CLAUDE.md` is 11 bytes** — effectively empty. `frontend/AGENTS.md` has content. Worth consolidating.
- **Repo hygiene:** `jobsvsai_phase1_ui_mobile_ready/` and its 50KB `.zip` sit at the repo root next to `testing feedbacks and data/`, and `frontend/.next` and `__pycache__` directories are present in the tree. Cosmetic, but `.next` and `__pycache__` in particular suggest `.gitignore` gaps.
- **No migration runner.** Compose relies on Postgres's init-dir, which fires only on an empty volume. Production deployment needs a real migration step before anything else in §27 can ship safely.
- **Test suite:** 12 test files present, one per phase plus integration/policy/rubric/benchmark. The Phase 5 report claims 79 backend tests passing, frontend lint and production build green. I could not execute any of it here.

---

## 8. What I'd propose doing next

No code changes yet — this report is the deliverable you asked for. When you're ready, my suggested Phase 6 order is:

1. **Close the public read-path gap (7.1).** Small, reversible, and it makes every later step fail safe instead of fail open. I'd do this first even though it isn't triage.
2. **Decide 7.2 and 7.4** — the model-version question and the promotion target schema. These are your calls, not mine; both are one-way doors once data lands.
3. **Run the truncation-bias experiment (7.5).** Cheap, deterministic, no external AI, and it either validates the coverage gate publicly or finds a real problem before launch.
4. **Then the triage itself** — warning taxonomy, severity, affected-candidate counts, exclusions, final cohort — against the persisted `phase5_anomaly_findings`, weighting regulation sensitivity higher than its nominal severity per 7.6.
5. **Scope the editorial/content workstream (7.4, second half)** honestly before committing to a launch date. 400 occupations need 400 slugs, categories, summaries, verdicts and related-career graphs, and today's sources for those are hand-seeded.

I have not promoted anything, activated anything, changed any formula, regenerated any mapping, or written to the repository.
