# Phase 4D Direct Structural Proxy Reconstruction Report

Date: 2026-08-20  
Status: validation complete; **ready for a separately approved bounded corpus-scale scoring run**  
Scope: the unchanged Phase 4C cohort of 25 occupations

## Executive verdict

Phase 4D replaced only the four weak structural proxy families—physical presence, environment variability, duty-of-care/accountability, and clinical consequence severity—with direct, versioned formulas over existing O\*NET 30.3 evidence. The run did not add occupations, regenerate task-capability mappings, call an external AI service, enable the Occupational Archetype Layer, or write production/public scores.

The reconstruction materially reduced predeclared absolute proxy-band failures from 13 to 3. All ten failures that belonged to the four reconstructed families were resolved. Pairwise validation improved from 22 passes and two weak-separation warnings to 23 passes and one warning, with zero reversals. Eleven absolute checks improved, none regressed, all calculations reconcile, and an independent replay reproduced the results exactly.

The completion target is met. JobsVsAI is methodologically ready for a **bounded, monitored corpus-scale scoring run** with the existing 70% coverage gate and hard isolation from production. This is not approval for unbounded corpus scoring, public activation, production replacement, or corpus-wide mapping; those actions still require explicit approval.

## Isolation and cohort controls

| Control | Result |
|---|---:|
| Occupations scored | 25, unchanged from Phase 4C |
| Task assessments per run | 407, reused without remapping |
| Task Capability Fit changes | 0 |
| New task-capability mappings | 0 |
| External AI calls | 0 |
| Occupational Archetype Layer enabled for scoring | No |
| Production occupation-score writes | 0 |
| Production task-score writes | 0 |
| Production rows before/after | 11 occupation / 23 task, unchanged |

The Phase 4D run uses the existing Task Capability Fit, Frontier AI Index, Augmentation Potential, scoring formulas, confidence framework, and 70% weighted task-coverage gate. Automation Feasibility changes only where one of the four reconstructed structural inputs already feeds the existing formula.

## Versioned method

Current model: `phase4d-direct-structural-proxy-v2`  
Source release: O\*NET 30.3  
Recompute run: `phase4d-direct-proxy-recompute-v2-2026q3`  
Replay run: `phase4d-direct-proxy-replay-v2-2026q3`

An append-only v1 run is retained as method history. It reduced failures from 13 to 9 but allowed generic diagnostic language in non-clinical tasks to activate the clinical enhancer. V2 corrected the rule generally by requiring healthcare-context evidence together with diagnostic/treatment evidence; it did not tune occupation-specific outcomes.

### Physical presence

Direct signals include Performing General Physical Activities; Handling and Moving Objects; Controlling Machines and Processes; standing, walking, and repetitive hand use; outdoor and vehicle exposure; physical conditions and hazards; proximity to others; and a source-task physical-action signal.

The aggregation is:

`0.60 × weighted RMS + 0.20 × weighted mean + 0.20 × mean(top three independent signals)`

The RMS term preserves strong source signals, while the top-three corroboration term prevents a single field from dominating.

### Environment variability

Direct signals include outdoors and non-climate-controlled indoor work; vehicle operation; noise, temperature, contaminants, cramped spaces, vibration, radiation, disease, heights, hazards, and protective equipment; equipment-determined pace; operating machinery; inverse task repetition; and source-task variable-setting evidence.

The aggregation is:

`0.35 × weighted RMS + 0.15 × weighted mean + 0.50 × mean(top three independent signals)`

This captures materially variable shops and vehicle-based work in addition to outdoor/hazard exposure.

### Duty-of-care / accountability

Direct signals include consequence of error; impact, frequency, and freedom of decision making; responsibility for others' health and safety; responsibility for outcomes; decision-making work activities; compliance; coordinating others; caring activities; and source-task duty-of-care evidence.

The aggregation is:

`0.70 × weighted RMS + 0.30 × weighted mean`

### Clinical consequence severity

The general consequence base uses consequence of error, decision impact, responsibility for health/safety, and hazardous-condition/equipment signals:

`0.65 × weighted RMS + 0.35 × weighted mean`

A clinical enhancer can activate only when all three source-backed gates pass:

1. clinical/treatment/diagnostic task evidence is at least 15;
2. caring-for-others activity or disease exposure is at least 20; and
3. consequence-of-error or responsibility-for-health-and-safety evidence is at least 35.

Occupation title and SOC category are explicitly prohibited inputs. Diagnostic language must occur in healthcare context, preventing generic equipment diagnosis, testing, or administration language from being treated as clinical evidence.

The clinical gate activated only for Healthcare Social Workers, Registered Nurses, and Nurse Practitioners. It did not activate for Electricians, Automotive Technicians, Teachers, Hairdressers, or other non-clinical roles.

## Provenance and missing-data policy

Each persisted proxy snapshot records:

- every source O\*NET element or source task used;
- source release and source-record identity/hash;
- raw and normalized values;
- transformations and configured weights;
- normalized weights used after exclusions;
- mean/RMS/top-signal contribution terms;
- sample size, standard error, suppression state, and other available rating metadata;
- missing or excluded status and missing-data policy;
- resulting value, confidence, formula family/version, and complete reconciliation data.

Missing, suppressed, or unavailable source ratings are excluded and the remaining observed weights are renormalized. Confidence is penalized for missing coverage. No value is imputed, inferred from occupation title, or invented. Task-derived signals include the exact matched source tasks and task-record provenance; unrated tasks do not contribute to weighted task signals.

## Phase 4C versus Phase 4D validation

### Absolute proxy-band checks

| Measure | Phase 4C | Phase 4D |
|---|---:|---:|
| Passed | 33 | 43 |
| Failed | 13 | 3 |
| Improved checks | — | 11 |
| Regressed checks | — | 0 |

All ten Phase 4C failures in the reconstructed families now pass. The three remaining failures are in unchanged proxy families:

| Occupation | Proxy | Observed | Expected | Status |
|---|---|---:|---|---|
| Healthcare Social Workers | Regulation | 55.80 | High | unchanged non-target weakness |
| Technical Writers | Adoption pressure | 59.86 | High | unchanged non-target weakness |
| Technical Writers | Labour-market resilience | 48.53 | Low | unchanged non-target weakness |

### Direction and separation

| Measure | Phase 4C | Phase 4D |
|---|---:|---:|
| Pairwise passes | 22 / 24 | 23 / 24 |
| Weak-separation warnings | 2 | 1 |
| Directional reversals | 0 | 0 |

The Registered Nurse–Hairdresser consequence-severity comparison moved from a warning to a pass. The only remaining warning is the unchanged adoption-pressure comparison between Technical Writers and Machinists: observed separation 4.26 versus the predeclared minimum of 15. No new or unexplained directional reversal occurred.

## Distribution changes

### Task-level distributions

| Metric | Phase 4C mean | Phase 4D mean | Phase 4C SD | Phase 4D SD |
|---|---:|---:|---:|---:|
| Task Capability Fit | 72.04 | 72.04 | — | — |
| Automation Feasibility | 60.69 | 58.56 | 15.12 | 15.25 |
| Augmentation Potential | 46.76 | 47.93 | — | — |
| Task AI Exposure | 61.88 | 61.15 | — | — |
| Task confidence | 73.68 | 74.26 | — | — |

### Occupation-level distributions

| Metric | Phase 4C mean | Phase 4D mean | Phase 4C SD | Phase 4D SD |
|---|---:|---:|---:|---:|
| AI Exposure | 62.63 | 61.91 | 8.27 | 8.58 |
| Replacement Risk | 55.63 | 53.78 | 10.18 | 10.14 |
| Confidence | 76.44 | 76.44 | — | — |

Occupation confidence is unchanged because another existing confidence component remains the limiting factor. Task confidence rises slightly because the direct structural evidence is stronger and more completely reconciled.

### Reconstructed proxy distributions

| Proxy | Minimum | Mean | SD | Maximum |
|---|---:|---:|---:|---:|
| Physical presence | 9.84 | 44.14 | 20.84 | 85.71 |
| Environment variability | 12.94 | 42.15 | 20.26 | 81.55 |
| Duty/accountability | 48.48 | 64.95 | 9.79 | 82.38 |
| Clinical consequence severity | 29.17 | 52.62 | 15.62 | 81.66 |

## Score changes and outliers

Largest absolute Phase 4C-to-4D score movements are shown below. Negative values reflect stronger structural barriers reducing automation/replacement estimates; they are calibration outputs, not production-score changes.

| Occupation | AI Exposure Δ | Replacement Risk Δ |
|---|---:|---:|
| Heavy and Tractor-Trailer Truck Drivers | -1.84 | -4.64 |
| Healthcare Social Workers | -3.15 | -3.56 |
| Technical Writers | -0.36 | -3.43 |
| Sales Managers | -1.39 | -3.08 |
| Graphic Designers | -0.19 | -2.91 |
| Police and Sheriff's Patrol Officers | -1.38 | -2.77 |
| Software Developers | -0.33 | -2.54 |
| Automotive Service Technicians and Mechanics | -1.38 | -2.41 |
| Registered Nurses | -1.61 | -2.07 |
| Elementary School Teachers | -1.79 | -2.05 |

No movement is an unexplained directional reversal under the predeclared validation set. Healthcare Social Workers have the largest AI Exposure change because multiple direct human-safety, care, and clinical-context signals now agree; Truck Drivers have the largest Replacement Risk change because vehicle operation and physical/environment dependence are no longer under-represented.

## Coverage and confidence

The weighted-coverage gate remains 70% and its disposition is exactly unchanged:

- 21 occupations pass and are scale-eligible inside this isolated validation layer.
- Graphic Designers: 64.34%, blocked.
- Sales Managers: 65.43%, blocked.
- Hairdressers, Hairstylists, and Cosmetologists: 59.11%, blocked.
- Retail Salespersons: 45.06%, blocked.

Blocked occupations retain inspectable validation calculations with the existing confidence downgrade, but are not promoted or forced through the gate. No missing task evidence was filled.

## Exact reconciliation and deterministic replay

- Proxy component weighted means, RMS terms, corroboration terms, clinical gates, and final family values reconcile exactly to their persisted snapshots.
- All 407 task assessments reconcile to the existing scoring formulas.
- All 25 occupation calculations reconcile.
- Task Capability Fit is bit-for-bit unchanged across the cohort.
- Coverage values, gate outcomes, and blocked occupation set are unchanged.
- The independent replay matches the recompute run exactly, including input hashes, proxy snapshots, task results, occupation results, validation findings, and isolation counters.
- Reconciliation failures: 0.
- Deterministic replay differences: 0.

## Admin and responsive verification

The read-only `/admin/phase4d` inspector exposes the model/run history, formula definitions, validation summary, all 25 occupation snapshots, score and confidence changes, coverage disposition, full source derivations, missing/suppression metadata, transformations, weights, contributions, provenance, and reconciliation.

The page was verified at 360, 390, 430, 768, 1024, and 1440 px. The heading, status, run history, all 25 occupation records, and source details remained accessible at every width. No page-level horizontal overflow was observed. An expanded Registered Nurses derivation at 360 px also produced no overflowing descendant elements.

## Verification results

- Phase 4D integration tests: 5 passed.
- Complete backend suite: 74 passed.
- Frontend lint: passed.
- Frontend production build: passed.
- Admin API and rebuilt Docker services: passed.
- Responsive browser audit at all six requested widths: passed.

## Remaining methodological weaknesses

1. Source-task text signals are deterministic and source-provenanced but still heuristic; they are not a substitute for independent clinical or occupational expert validation.
2. The top-three corroboration behavior should be monitored on a larger bounded sample to ensure stable behavior across sparse O\*NET domains.
3. O\*NET ratings describe occupational context and importance, not observed task time or causal automation barriers.
4. Regulation, adoption pressure, and labour-market resilience were deliberately left unchanged; their three residual absolute failures and one weak-separation warning still require separate versioned reconstruction.
5. The existing occupation-confidence bottleneck masks the small improvement in direct structural-proxy confidence at occupation level.
6. This 25-occupation cohort is deliberately diverse but small; rare domains and incomplete O\*NET evidence patterns remain untested.
7. The clinical enhancer is a conservative source-evidence gate, not a medical safety or malpractice-risk model.

## Recommendation

Proceed only with a separately approved, bounded corpus-scale scoring run that:

- remains isolated from public and production scores;
- preserves the 70% weighted-coverage gate and confidence downgrades;
- stops rather than imputes when source evidence is missing;
- records the same append-only formula, source, reconciliation, and replay artifacts;
- performs distribution, outlier, clinical-gate, and directional audits before any scale or publication decision; and
- keeps the Occupational Archetype Layer disabled for scoring.

Do not begin corpus-wide scoring, corpus-wide remapping, public activation, or production-score replacement without explicit approval.
