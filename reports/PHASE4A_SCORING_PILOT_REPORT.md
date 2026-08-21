# JobsVsAI Phase 4A End-to-End Scoring Pilot

**Pilot version:** `phase4a-2026q3-v1`  
**Mapping run:** `phase4a-pilot-mapper-v1-2026q3`  
**Initial calculation:** `phase4a-initial-v1-2026q3`  
**Deterministic replay:** `phase4a-replay-v1-2026q3`  
**Formula-only recompute:** `phase4a-formula-recompute-v1-2026q3`  
**Status:** structurally complete; **not yet safe for corpus-wide scaling**

## Executive verdict

The isolated Phase 4A pipeline is technically sound enough for continued methodology work: all 281 source tasks in the 12-occupation cohort have a persisted mapping disposition and deterministic validation event; 230 mappings are scoring-eligible; 51 ambiguous or insufficient descriptions are retained but excluded; 230 task assessments and 12 occupation scores reconcile; deterministic replay is exact; formula-only recomputation reused the same 230 eligible mappings and made zero new mapping calls. The full test suite passes (52 tests).

The score methodology should **not** be scaled to the full corpus yet. The pilot exposes material calibration and input-coverage weaknesses: task scores saturate near 95.5 for many digitally stated tasks, the mapper's environment-constraint levels never reach the critical-constraint bottleneck threshold in the real pilot, adoption pressure and labour-market resilience are explicit neutral placeholders, several requested constraint domains are only incomplete proxies, and weighted mapping coverage is below 70% for Graphic Designers and Sales Managers. These are methodology findings, not reasons to tune constants toward intuitive occupation rankings.

No O*NET source record, production occupation score, legacy task score, public activation state, or technical-frontier value was changed.

## Cross-occupation comparison

All values below are private pilot results. Coverage is the share of source task weight represented by eligible mappings, not the share of task rows.

| # | Occupation | Code | Source | Mapped | Excluded | Weighted coverage | AI Exposure | Replacement Risk | Confidence |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Software Developers | 15-1252.00 | 17 | 14 | 3 | 85.98% | 92.46 | 90.24 | 86.54 |
| 2 | Graphic Designers | 27-1024.00 | 19 | 12 | 7 | 64.34% | 88.05 | 87.26 | 75.56 |
| 3 | Accountants and Auditors | 13-2011.00 | 29 | 24 | 5 | 82.33% | 91.70 | 89.05 | 83.23 |
| 4 | Lawyers | 23-1011.00 | 22 | 17 | 5 | 77.18% | 77.22 | 79.34 | 81.56 |
| 5 | Nurse Practitioners | 29-1171.00 | 27 | 26 | 1 | 96.26% | 89.38 | 84.88 | 90.82 |
| 6 | Secondary School Teachers | 25-2031.00 | 32 | 29 | 3 | 88.87% | 93.13 | 87.79 | 86.77 |
| 7 | Electricians | 47-2111.00 | 21 | 21 | 0 | 100.00% | 69.89 | 76.54 | 92.75 |
| 8 | Automotive Service Technicians and Mechanics | 49-3023.00 | 30 | 22 | 8 | 74.72% | 64.54 | 73.91 | 79.00 |
| 9 | Sales Managers | 11-2022.00 | 17 | 12 | 5 | 65.43% | 94.18 | 90.22 | 75.85 |
| 10 | Statisticians (Data Scientist substitute) | 15-2041.00 | 19 | 18 | 1 | 98.08% | 94.31 | 91.48 | 92.68 |
| 11 | Photographers | 27-4021.00 | 28 | 21 | 7 | 81.50% | 89.71 | 88.84 | 84.17 |
| 12 | Cooks, Restaurant | 35-2014.00 | 20 | 14 | 6 | 74.23% | 81.73 | 84.66 | 80.04 |

Data Scientists (`15-2051.00`) were not used because their 16 current source tasks have no weighting-eligible task ratings. Statisticians were substituted explicitly; no task weights were invented. Software Developers remain pilot-only because their source promotion profile is normalized but not scoring-ready.

## Per-occupation review

Every occupation uses `task-capability-fit-v1`, `automation-feasibility-v1`, `augmentation-potential-v1`, `phase4a-occupation-score-v1`, `mvp-evidence-policy-v1`, and the `commercially_deployable` track of `frontier-ai-index-v1`.

### 1. Software Developers

- **Counts and scores:** 17 source / 14 mapped / 3 excluded; 85.98% weighted coverage; AI Exposure 92.46; Replacement Risk 90.24; confidence 86.54.
- **Highest exposure:** project reports/correspondence (95.50); system-design consultation (95.50); data storage/retrieval/manipulation (95.50).
- **Lowest automation:** system installation/modification analysis (74.92); equipment-function monitoring (88.45); customer/department consultation (97.82).
- **Highest augmentation:** customer/department consultation (70.66); supervising technical staff (70.12); modifying existing software (70.12).
- **Top factors:** task automation exposure 43.63; human-dependency resistance 14.80; AI capability proximity 14.49.
- **Warnings:** 3 policy exclusions; provisional Frontier inputs; neutral adoption and labour-market placeholders; occupation lifecycle is normalized, not scoring-ready.

### 2. Graphic Designers

- **Counts and scores:** 19 / 12 / 7; 64.34% coverage; AI Exposure 88.05; Replacement Risk 87.26; confidence 75.56.
- **Highest exposure:** image/archive maintenance (95.50); studying illustrations/photographs (95.50); graphics/layout development (95.50).
- **Lowest automation:** printer layout instructions (63.25); assembling final layouts (63.25); creating sample layouts (89.72).
- **Highest augmentation:** computer layout keying (70.58); client-discussed illustrations/sketches (70.41); photographing layouts (70.41).
- **Top factors:** task automation exposure 42.06; human-dependency resistance 14.20; AI capability proximity 13.70.
- **Warnings:** 7 policy exclusions and sub-70% weighted coverage; provisional Frontier inputs; neutral adoption and labour-market placeholders.

### 3. Accountants and Auditors

- **Counts and scores:** 29 / 24 / 5; 82.33% coverage; AI Exposure 91.70; Replacement Risk 89.05; confidence 83.23.
- **Highest exposure:** business-operation analysis (95.50); financial/regulatory consultation (95.50); asset/liability review (95.50).
- **Lowest automation:** record examination and worker interviews (84.63); cash/securities inspection (87.85); objective/management-activity audit (87.99).
- **Highest augmentation:** payroll/personnel audit (70.57); client benefits advice (70.41); tax computation and returns (70.41).
- **Top factors:** task automation exposure 43.17; AI capability proximity 14.37; human-dependency resistance 14.22.
- **Warnings:** 5 policy exclusions; 4 tasks lack complete source task ratings; provisional Frontier inputs; neutral adoption and labour-market placeholders.

### 4. Lawyers

- **Counts and scores:** 22 / 17 / 5; 77.18% coverage; AI Exposure 77.22; Replacement Risk 79.34; confidence 81.56.
- **Highest exposure:** juror/motion/witness courtroom work (95.50); public-program and legislation work (95.50); strategy/argument development (95.50).
- **Lowest automation:** agent/trustee/guardian/executor work (39.49); client transaction/liability advice (43.09); probate representation (45.99).
- **Highest augmentation:** legal briefs and appeals (70.56); legal-document drafting/review (70.56); law/ruling interpretation (70.41).
- **Top factors:** task automation exposure 37.82; human-dependency resistance 12.57; AI capability proximity 11.81.
- **Warnings:** 5 policy exclusions; provisional Frontier inputs; neutral adoption and labour-market placeholders. Three tasks exercised critical capability bottlenecks.

### 5. Nurse Practitioners

- **Counts and scores:** 27 / 26 / 1; 96.26% coverage; AI Exposure 89.38; Replacement Risk 84.88; confidence 90.82.
- **Highest exposure:** treatment-plan development (95.50); primary-care procedures (95.50); health-care advocacy (95.50).
- **Lowest automation:** patient self-management education (57.40); acute-problem diagnosis/treatment (61.61); adverse-drug-reaction response (71.87).
- **Highest augmentation:** patient-history and diagnostic interpretation (72.05); prescribing decisions (71.97); patient-care supervision (71.72).
- **Top factors:** task automation exposure 41.46; AI capability proximity 14.04; human-dependency resistance 12.97.
- **Warnings:** 1 policy exclusion; provisional Frontier inputs; neutral adoption and labour-market placeholders. One task exercised a critical capability bottleneck.

### 6. Secondary School Teachers

- **Counts and scores:** 32 / 29 / 3; 88.87% coverage; AI Exposure 93.13; Replacement Risk 87.79; confidence 86.77.
- **Highest exposure:** parent/guardian progress meetings (95.50); course objectives/outlines (95.50); class preparation evidence (95.50).
- **Lowest automation:** administrative monitoring duties (72.82); safety monitoring for equipment/materials (86.62); planning balanced instruction (89.02).
- **Highest augmentation:** student-record maintenance (70.98); student guidance/counselling (70.56); adapting instruction/materials (70.56).
- **Top factors:** task automation exposure 43.62; AI capability proximity 14.63; human-dependency resistance 12.12.
- **Warnings:** 3 policy exclusions; provisional Frontier inputs; neutral adoption and labour-market placeholders. One task exercised a critical capability bottleneck.

### 7. Electricians

- **Counts and scores:** 21 / 21 / 0; 100% coverage; AI Exposure 69.89; Replacement Risk 76.54; confidence 92.75.
- **Highest exposure:** wire/circuit connection (95.50); sketches/cost estimates (95.50); conduit placement (95.50).
- **Lowest automation:** fastening electrical boxes (39.49); ladder/scaffold/roof work (40.69); directing/training workers (40.81).
- **Highest augmentation:** tool/equipment use (70.82); part fabrication (70.78); hazardous-operation advice (70.74).
- **Top factors:** task automation exposure 34.85; human-dependency resistance 14.82; AI capability proximity 10.53.
- **Warnings:** provisional Frontier inputs; neutral adoption and labour-market placeholders. Six tasks exercised critical capability bottlenecks.

### 8. Automotive Service Technicians and Mechanics

- **Counts and scores:** 30 / 22 / 8; 74.72% coverage; AI Exposure 64.54; Replacement Risk 73.91; confidence 79.00.
- **Highest exposure:** component overhaul/replacement (95.50); fuel-system retrofit (95.50); engine tuning (95.50).
- **Lowest automation:** lift-mechanism installation/repair (34.48); injector/carburetor repair (37.30); piston/gear/valve/bearing repair (37.30).
- **Highest augmentation:** wheel/axle/frame alignment (70.17); electronic component testing (70.12); routine maintenance (70.12).
- **Top factors:** task automation exposure 33.13; human-dependency resistance 14.81; AI capability proximity 9.56.
- **Warnings:** 8 policy exclusions; 2 tasks lack complete source ratings; provisional Frontier inputs; neutral adoption and labour-market placeholders. Eight tasks exercised critical capability bottlenecks.

### 9. Sales Managers

- **Counts and scores:** 17 / 12 / 5; 65.43% coverage; AI Exposure 94.18; Replacement Risk 90.22; confidence 75.85.
- **Highest exposure:** dealer/distributor operating advice (95.50); sales staffing/training planning (95.50); location marketing-potential analysis (95.50).
- **Lowest automation:** customer-preference monitoring (87.96); department-head consultation (97.82); customer equipment advice (98.23).
- **Highest augmentation:** department-head consultation (70.66); customer equipment advice (70.53); sales/service accounting coordination (70.29).
- **Top factors:** task automation exposure 44.17; AI capability proximity 14.80; human-dependency resistance 13.80.
- **Warnings:** 5 policy exclusions and sub-70% weighted coverage; provisional Frontier inputs; neutral adoption and labour-market placeholders.

### 10. Statisticians

- **Counts and scores:** 19 / 18 / 1; 98.08% coverage; AI Exposure 94.31; Replacement Risk 91.48; confidence 92.68.
- **Highest exposure:** statistical-result reporting (95.50); research-project design (95.50); chart/graph analysis reporting (95.50).
- **Lowest automation:** probability/inference theory work (71.87); data-collection planning (90.74); live results presentation (97.55).
- **Highest augmentation:** statistical data processing (70.12); supervising data workers (70.12); statistical software development (70.12).
- **Top factors:** task automation exposure 44.49; AI capability proximity 14.80; human-dependency resistance 14.72.
- **Warnings:** substituted for Data Scientists because no Data Scientist source task was weighting-eligible; 1 policy exclusion; provisional Frontier inputs; neutral adoption and labour-market placeholders. One task exercised a critical capability bottleneck.

### 11. Photographers

- **Counts and scores:** 28 / 21 / 7; 81.50% coverage; AI Exposure 89.71; Replacement Risk 88.84; confidence 84.17.
- **Highest exposure:** camera exposure/focus adjustment (95.50); office administration (95.50); light/distance/exposure measurement (95.50).
- **Lowest automation:** equipment/background assembly (45.58); photographic equipment installation (67.25); project-goal/location/equipment planning (98.23).
- **Highest augmentation:** project-goal/location/equipment planning (70.53); visual aids/charts (70.41); film development/printing (70.17).
- **Top factors:** task automation exposure 42.71; human-dependency resistance 14.80; AI capability proximity 13.99.
- **Warnings:** 7 policy exclusions; provisional Frontier inputs; neutral adoption and labour-market placeholders. One task exercised a critical capability bottleneck.

### 12. Cooks, Restaurant

- **Counts and scores:** 20 / 14 / 6; 74.23% coverage; AI Exposure 81.73; Replacement Risk 84.66; confidence 80.04.
- **Highest exposure:** supervisory menu planning (95.50); food portioning/arranging/serving (95.50); emergency/rush assistance (95.50).
- **Lowest automation:** animal/meat preparation (39.32); fruit/vegetable preparation (39.49); food-area inspection/cleaning (62.65).
- **Highest augmentation:** ingredient weighing/mixing (70.12); baking/roasting/broiling/steaming (70.12); temperature regulation (70.00).
- **Top factors:** task automation exposure 39.88; human-dependency resistance 15.00; AI capability proximity 12.57.
- **Warnings:** 6 policy exclusions; provisional Frontier inputs; neutral adoption and labour-market placeholders. Three tasks exercised critical capability bottlenecks.

## Validation results

| Gate | Result | Evidence |
|---|---|---|
| Cohort boundary | Pass | Exactly 12 occupations, 281 source tasks, zero mappings outside cohort |
| Structured mapping persistence | Pass | 281 versioned mappings/dispositions; 230 eligible; 51 policy-excluded |
| Score-blind mapping | Pass | Prohibited-input attestation and manifest persisted; runtime model calls = 0 |
| Mapping validation | Pass | Every mapping has deterministic validation; ambiguous/insufficient cases are ineligible |
| Task score reconciliation | Pass | 230/230 latest task assessments reconcile |
| Occupation score reconciliation | Pass | 12/12 latest occupation scores reconcile |
| Frontier track | Pass | Commercially deployable track only; 15/15 evidenced provisional values |
| Deterministic replay | Pass | 230 task and 12 occupation results match the initial run exactly |
| Formula-only recompute | Pass | Same mapping run reused; 230 mappings reused; zero new mapping calls |
| Production isolation | Pass | Production occupation scores remain 11; legacy task scores remain 23 |
| Public/technical isolation | Pass | No public activation; technical-frontier remains empty |
| Automated tests | Pass | 52 tests passed |
| Responsive admin audit | Pass | 360, 390, 430, 768, 1024, and 1440 px; no document-level horizontal overflow |

## Outliers and unexpected behavior

- **Score saturation:** many unrelated tasks land at task AI Exposure 95.50. This follows the current task-exposure blend when fit and automation approach 100, but it weakens differentiation and deserves calibration against reviewed mappings before scaling.
- **Very high occupation values:** Statisticians, Sales Managers, Teachers, Software Developers, and Accountants exceed 91 AI Exposure. These are outputs of the declared inputs, not target-tuned results. Sales Managers combine a high score with only 65.43% weighted coverage, so the score should not be considered stable.
- **Physical-work separation exists:** Automotive Mechanics (64.54 exposure) and Electricians (69.89) are below the cognitive/digital cohort; their lowest-automation tasks are 34–41. This demonstrates the capability bottleneck path, but does not fully validate environment-constraint calibration.
- **Augmentation clustering:** maximum augmentation is 72.05 and many high-augmentation tasks cluster near 70.1–70.7. The current 70/30 formula distinguishes augmentation from automation, but provides limited spread.
- **Task-language false positives remain possible:** keyword-based pilot mappings can assign high digital capability to a physically executed task containing words such as “connect,” “operate,” or “prepare.” The exact contributions are exposed rather than hidden.
- **Coverage weakness:** Graphic Designers and Sales Managers are below the provisional 70% weighted-coverage threshold; Lawyers, Automotive Mechanics, and Cooks are between 70% and 80%.

## Bottleneck review

Twenty-four task assessments invoked the critical-capability bottleneck. They are concentrated in Lawyers (3), Nurse Practitioners (1), Teachers (1), Electricians (6), Automotive Mechanics (8), Statisticians (1), Photographers (1), and Cooks (3). The minimum fit was 8.33, demonstrating that strong secondary capabilities cannot mask a critical shortfall.

No real pilot task invoked the **critical environment-constraint cap**. Constraint burdens still reduced automation scores, and the isolated unit test proves the cap deterministically at a safety-critical level of 90, but the pilot mapper's generated constraint levels did not reach the configured threshold of 70. This is a calibration gap that must be addressed through reviewed constraint mappings or threshold evidence—not by lowering the threshold to obtain desired rankings.

## Formula and data weaknesses to resolve before scale

1. Replace the explicit neutral adoption-pressure and labour-market-resilience placeholders with versioned, evidenced sources, or exclude Replacement Risk from scale decisions until those inputs exist.
2. Add first-class environment variability, real-time requirement, privacy/sensitivity, regulation/accountability, and consequence-severity dimensions. Current sensing, interaction, data-access, legal, and safety fields are documented but incomplete proxies.
3. Review constraint-level calibration against human-reviewed physical, regulated, interpersonal, and safety-critical tasks; the pilot did not exercise the production constraint cap.
4. Evaluate mapping quality beyond structural validity. The deterministic pilot mapper is intentionally inexpensive and score-blind, but keyword support alone is not a research-quality semantic mapping method.
5. Address sub-70% weighted coverage for Graphic Designers and Sales Managers without imputing ambiguous mappings.
6. Investigate task-exposure saturation and augmentation clustering using frozen reviewed inputs. Do not tune against preferred occupation orderings.
7. Resolve Data Scientist source task ratings before returning that occupation to the cohort.
8. Promote Software Developers through the existing source-readiness lifecycle before any public or production use.

## Stop condition

Phase 4A implementation and validation are complete in the isolated pilot namespace. The methodology verdict is **not safe to scale yet** because the weaknesses above affect semantic validity and score stability even though structural, reconciliation, replay, explainability, isolation, and responsive gates pass.

No corpus-wide task mapping or occupation scoring should begin without explicit approval and a decision on these findings.
