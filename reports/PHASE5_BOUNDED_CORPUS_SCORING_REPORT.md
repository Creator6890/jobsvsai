# Phase 5 Bounded Corpus-Scale Scoring Report

Date: 2026-08-20  
Status: **bounded candidate run complete; public and production activation remain prohibited**  
Population: 878 O\*NET 30.3 occupations marked scoring-eligible under the existing promotion policy

## Executive verdict

Phase 5 completed the first corpus-scale JobsVsAI candidate calculation. All 878 scoring-ready occupations were attempted and received an isolated candidate calculation. Of these, 744 pass both the unchanged 70% weighted task-coverage gate and the existing confidence gate. The remaining 134 are blocked for insufficient weighted task coverage; none were forced through and none received public-activation eligibility.

The score distributions show useful separation without saturation or near-zero variance. AI Exposure has mean 59.86 and standard deviation 11.13; Replacement Risk has mean 51.24 and standard deviation 9.46. Their Pearson correlation is 0.8563, leaving meaningful room for structural constraints to separate exposure from replacement.

The deterministic replay matches exactly across 10,815 task assessments, 878 occupation calculations, 300 anomaly findings, proxy inputs, and the corpus report. No public pages were activated, production scores were unchanged, no external AI calls were made, and the Occupational Archetype Layer remained disabled for scoring.

A first public-launch cohort of 400 occupations has been identified but not activated. Every member passes the coverage and confidence gates, has no anomaly finding, and was ranked ahead of candidates with material provisional-input sensitivity.

## Version and isolation manifest

| Artifact | Version |
|---|---|
| Candidate namespace | `phase5-candidate-2026q3-v1` |
| Mapping scope | `phase5-dependency-aware-minimum-scope-v1` |
| Mapping run | `phase5-bounded-mapper-v1-2026q3` |
| Candidate scoring run | `phase5-bounded-corpus-v2-2026q3` |
| Deterministic replay | `phase5-bounded-corpus-replay-v2-2026q3` |
| Anomaly policy | `phase5-corpus-anomaly-policy-v2` |
| Structural proxy model | `phase4d-direct-structural-proxy-v2` |
| Base provisional proxy model | `phase4b-occupation-proxy-v1` |
| Frontier track | `frontier-ai-index-v1` / commercially deployable |

An earlier append-only Phase 5 analysis run remains in history. The v2 anomaly policy changed only the launch-cohort selection rule: provisional sensitivity is explicitly flagged and deprioritized rather than being treated as a hard exclusion. It did not change mappings, task scores, occupation scores, coverage, confidence, or production state.

Isolation checks:

| Control | Result |
|---|---:|
| Production occupation-score rows | 11, unchanged |
| Production task-score rows | 23, unchanged |
| Public occupation rows | 0 |
| Phase 5 production writes | 0 |
| Phase 5 public activations | 0 |
| External AI calls | 0 |
| Estimated external AI tokens | 0 |
| Archetype scoring | Disabled |

## Population and mapping scope

The current O\*NET store contains 1,016 occupations. Exactly 878 were marked scoring-eligible and frozen into the candidate namespace using an append-only population manifest and hash.

| Mapping disposition | Tasks |
|---|---:|
| Total source tasks in the 878 occupations | 17,843 |
| Existing exact task + statement mapping reused | 393 |
| Existing exact statement-hash mapping reused | 169 |
| New deterministic, structurally validated mapping | 10,253 |
| Ambiguous/insufficient description; no values invented | 2,264 |
| Not mapped after occupation reached its coverage target | 4,559 |
| Missing legitimate source weight; excluded without imputation | 205 |
| Candidate task assessments calculated | 10,815 |

The mapper was blind to Frontier capability values, task and occupation scores, automation outcomes, target distributions, occupation titles, and SOC categories. It used current O\*NET task statements, source importance/frequency for minimum-scope ordering, the approved taxonomy/rubric/evidence-policy versions, and exact dependency hashes. Existing mappings were reused by reference; unchanged mappings were never regenerated.

New mappings were generated locally using the existing deterministic rubric implementation. No external model was called and estimated external token use is zero. Observed/estimated local mapping compute was approximately 21.9 seconds; candidate score computation was approximately 11.4 seconds and replay computation approximately 10.9 seconds on this environment.

## Preserved scoring methodology

Phase 5 preserves:

- the current Task Capability Fit calibration formula;
- current Automation Feasibility and bottleneck behavior;
- current Augmentation Potential;
- the Phase 4D direct physical presence, environment variability, accountability, and clinical consequence reconstruction;
- the commercially deployable Frontier AI Index;
- the 70% weighted task-coverage gate;
- the existing confidence formula and 70-point scale-confidence threshold; and
- disabled archetype scoring.

Regulation, adoption pressure, and labour-market resilience remain explicitly provisional under `phase4b-occupation-proxy-v1`. Each occupation stores a deterministic one-at-a-time neutral-50 counterfactual so their score influence is inspectable rather than hidden.

## Coverage and confidence

| Outcome | Occupations |
|---|---:|
| Candidate calculations completed | 878 |
| Review-ready inside the candidate namespace | 744 |
| Blocked below 70% weighted coverage | 134 |
| Additional confidence blocks after passing coverage | 0 |
| Coverage-gate violations | 0 |

Weighted coverage distribution:

| Minimum | P10 | P25 | Median | P75 | P90 | Maximum | Mean | SD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 23.27 | 66.18 | 70.40 | 71.61 | 72.98 | 74.22 | 100.00 | 70.55 | 6.24 |

Confidence distribution:

| Minimum | P10 | P25 | Median | P75 | P90 | Maximum | Mean | SD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20.30 | 71.52 | 75.61 | 76.40 | 77.04 | 77.66 | 87.77 | 74.78 | 6.25 |

The lowest-coverage blocked cases include Bicycle Repairers (23.27%), Team Assemblers (30.58%), Farm Labor Contractors (30.68%), Bartenders (35.63%), Spa Managers (36.94%), and Robotics Engineers (37.39%). These records retain diagnostic candidate estimates but remain blocked and non-publishable.

## Score distributions

| Metric | Minimum | P10 | P25 | Median | P75 | P90 | Maximum | Mean | SD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| AI Exposure | 22.40 | 43.43 | 53.08 | 61.60 | 68.50 | 72.61 | 80.35 | 59.86 | 11.13 |
| Replacement Risk | 29.14 | 38.37 | 43.72 | 51.50 | 58.33 | 63.50 | 75.03 | 51.24 | 9.46 |

Pearson correlation between AI Exposure and Replacement Risk is 0.8563 across all 878 diagnostic calculations.

Highest review-ready AI Exposure values include:

| Occupation | AI Exposure | Replacement Risk | Confidence | Coverage |
|---|---:|---:|---:|---:|
| Wind Energy Engineers | 79.83 | 69.49 | 78.58 | 74.75% |
| Credit Analysts | 79.69 | 74.12 | 80.21 | 78.56% |
| Data Warehousing Specialists | 79.61 | 75.03 | 77.80 | 73.38% |
| Operations Research Analysts | 78.94 | 73.03 | 76.54 | 70.06% |
| Financial Quantitative Analysts | 78.89 | 74.04 | 76.60 | 70.25% |

Lowest review-ready AI Exposure values include Automotive Glass Installers and Repairers (22.40), Industrial Truck and Tractor Operators (25.49), Helpers to Masonry/Tile Trades (27.38), Fallers (27.81), and Janitors and Cleaners (27.86).

The highest review-ready Replacement Risk values are Data Warehousing Specialists (75.03), Credit Analysts (74.12), Financial Quantitative Analysts (74.04), Environmental Economists (73.72), and Poets/Lyricists/Creative Writers (73.35). The lowest include Electrical Power-Line Installers and Repairers (29.14), Automotive Glass Installers and Repairers (29.16), Pile Driver Operators (29.90), Structural Iron and Steel Workers (31.08), and Fallers (31.09).

Economists have the highest diagnostic AI Exposure value (80.35) but only 68.44% weighted coverage, so that record is correctly blocked and excluded from the review-ready ranking. Team Assemblers are another important diagnostic outlier: AI Exposure 79.40 with only 30.58% coverage and 31.53 confidence. The inspector exposes rather than promotes these unstable estimates.

## Automated anomaly results

The final replay contains 300 warning findings affecting 258 occupations and **zero errors**.

| Anomaly type | Findings | Interpretation |
|---|---:|---|
| Related-SOC discontinuity | 176 occupation findings across 14 SOC families | Review closely related occupations with score ranges of at least 30 points |
| Provisional-input sensitivity | 106 | One provisional regulation/adoption/labour counterfactual changes a score by at least 3 points |
| Single-task dependence | 15 | One covered task contributes at least 25% of covered task weight |
| Exposure–Replacement gap | 2 | Absolute gap is at least 25 points |
| High Replacement Risk despite severe constraint | 1 | Directional review flag, not an automatic correction |

No findings were produced for:

- extreme score saturation;
- near-zero variance;
- values outside 0–100;
- confidence/coverage inconsistencies;
- low Replacement Risk despite highly digital/routine composition; or
- excessive dependence on a single occupation-level factor.

The two large Exposure–Replacement gaps are Painters, Construction and Maintenance (63.71 vs 37.19) and Pesticide Handlers/Sprayers/Applicators (66.77 vs 40.39). The severe-constraint review flag is Credit Counselors: Replacement Risk 70.63 with human dependency 72.85. These values were flagged, not tuned.

## Provisional-input sensitivity

One hundred six occupations cross the configured three-point sensitivity threshold. The largest effects are driven primarily by the unchanged provisional regulation model:

| Occupation | Maximum absolute impact |
|---|---:|
| Regulatory Affairs Specialists | 7.43 |
| Automotive Engineers | 7.25 |
| Arbitrators, Mediators, and Conciliators | 7.04 |
| Business Continuity Planners | 7.04 |
| Document Management Specialists | 6.82 |
| Personal Financial Advisors | 6.57 |
| Regulatory Affairs Managers | 6.45 |
| Data Entry Keyers | 6.24 |

These records remain visible in the candidate corpus but are deprioritized for initial launch review. The sensitivity calculation and exact provisional versions are persisted per occupation.

## Recommended first public-launch cohort

The system identified a ranked cohort of **400 occupations** and stopped without activation.

Selection requires:

- candidate status `review_ready`;
- weighted coverage at or above 70%;
- confidence at or above 70;
- no error anomaly;
- preference for provisional-input sensitivity below three points;
- then fewest anomaly findings, highest confidence, highest coverage, and SOC order.

All 400 selected occupations have zero anomaly findings. Minimum confidence in the recommendation is 76.14 and minimum weighted coverage is 70.02%. The full ordered list, metrics, and selection policy are persisted in `phase5_corpus_reports` and exposed in `/admin/phase5`. `activated` is explicitly false.

This recommendation is a review queue, not an activation instruction. Editorial review and explicit approval remain required before any occupation is made public.

## Reconciliation and deterministic replay

- Task assessments per final run: 10,815.
- Occupation calculations per final run: 878.
- Task reconciliation failures: 0.
- Occupation reconciliation failures: 0.
- Coverage-gate violations: 0.
- Out-of-range values: 0.
- Replay differences: 0.
- Replay status: exact.
- Production score writes: 0.
- Public activations: 0.

Every candidate occupation persists AI Exposure, Replacement Risk, confidence, weighted task coverage, source/eligible/excluded task counts, top exposure-driving tasks, top constraint burdens, augmentation-heavy tasks, complete structural proxy references and derivations, formula/input versions, provisional counterfactuals, warnings, blocking reasons, input hashes, and reconciliation.

## Admin and responsive verification

The read-only `/admin/phase5` inspector supports filters for review-ready/blocked status, AI Exposure, Replacement Risk, confidence, coverage, SOC prefix, warning/anomaly type, and provisional-input sensitivity. It exposes the complete candidate derivation, source-backed Phase 4D proxy details, run history, anomaly queue, distributions, mapping reuse, and the unactivated 400-occupation recommendation.

The live page passed responsive verification at 360, 390, 430, 768, 1024, and 1440 px. It showed 50 paginated occupation cards without page-level overflow at each width. A full driver/proxy derivation was expanded at 360 px with no overflowing descendants. Filter behavior was verified for the impossible blocked-plus-70%-coverage combination (zero matches) and provisional-sensitivity filter (106 matches).

## Verification results

- Phase 5 integration tests: 5 passed.
- Complete backend suite: 79 passed.
- Frontend lint: passed.
- Frontend production build: passed.
- Deterministic replay: exact.
- Live admin filters and responsive checks: passed.

## Remaining methodological and launch risks

1. The 10,253 new mappings are deterministic, score-blind, and structurally validated, but task-text rules remain a provisional MVP mapper rather than a research-grade human-reviewed corpus.
2. The 134 coverage-blocked occupations require better legitimate source descriptions or reviewed mappings; they must not be activated from their diagnostic estimates.
3. Regulation remains the largest provisional sensitivity driver. Adoption pressure and labour-market resilience remain versioned and provisional even where their observed sensitivity is smaller.
4. The 14 related-SOC discontinuity groups require review for evidence/mapping differences before publication; no smoothing or occupation-specific tuning should be applied automatically.
5. Single-task dependence in 15 occupations should be reviewed for genuine task-weight concentration versus missing mappable task evidence.
6. The commercially deployable Frontier AI Index remains provisional and future index versions must trigger dependency-based recomputation rather than overwriting this run.

## Completion decision

All Phase 5 completion criteria are met:

- the bounded 878-occupation candidate calculation completed;
- production and public scores did not change;
- deterministic replay succeeded;
- coverage and confidence gates remained enforced;
- the anomaly report was generated;
- mapping reuse, external-call, token, and local-compute statistics are documented; and
- a 400-occupation first-launch recommendation was identified but not activated.

Stop here. Do not activate the recommended cohort, replace production scores, or score outside this frozen namespace without explicit approval.
