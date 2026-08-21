# Phase 4C Targeted Validation Report

Date: 2026-08-20  
Status: validation complete; **not safe for corpus-wide scoring**  
Scope: 25 occupations, comprising the unchanged Phase 4A twelve plus thirteen deliberately diverse validation occupations

## Executive verdict

Phase 4C successfully exercised the Phase 4B methodology outside its original cohort without becoming a scale-up. The original 12 occupations reproduce their Phase 4B values exactly. All 407 persisted task assessments and all 25 occupation calculations reconcile, and the replay is deterministic.

The provisional structural proxies are broadly directionally useful: 22 of 24 predeclared pairwise comparisons meet their minimum separation, the remaining two preserve the expected order, and no pairwise comparison reverses. They are not yet sufficiently calibrated for corpus-wide scoring. Thirteen absolute expectation checks fail, concentrated in physical presence, environment variability, duty-of-care accountability, clinical consequence severity and structural labour resilience. Four occupations also fail the unchanged 70% weighted-coverage gate.

The methodology is therefore suitable for additional targeted validation and proxy revision only. It is **not safe for corpus-wide scoring, public activation or production-score replacement**.

## Cohort design

The cohort retains all Phase 4A occupations unchanged and adds exactly 13 occupations—within the requested 10–15 range. Selection rationales and expected proxy behavior were stored before proxy evaluation.

| Added occupation | Primary stress dimensions |
|---|---|
| General and Operations Managers | human dependency, accountability, adoption pressure |
| Personal Financial Advisors | human dependency, regulation, adoption pressure |
| Information Security Analysts | regulation, accountability, adoption pressure |
| Civil Engineers | physical presence, environment variability, regulation, accountability |
| Healthcare Social Workers | human dependency, regulation, structural resilience |
| Elementary School Teachers | human dependency, accountability, structural resilience |
| Technical Writers | low physical presence, adoption pressure, low structural resilience |
| Registered Nurses | physical presence, human dependency, regulation, accountability, consequence severity, resilience |
| Police and Sheriff's Patrol Officers | physical presence, environment variability, regulation, accountability, consequence severity |
| Hairdressers, Hairstylists, and Cosmetologists | physical presence, human dependency, low adoption pressure, resilience |
| Retail Salespersons | human dependency, adoption pressure, resilience |
| Machinists | physical presence, environment variability, accountability, adoption pressure |
| Heavy and Tractor-Trailer Truck Drivers | physical presence, environment variability, accountability, consequence severity, adoption pressure |

Only these 25 occupations were scored. The full O\*NET corpus was not mapped or scored.

## Mapping scope and evidence policy

- Total source tasks in the 25-occupation cohort: 577.
- Existing Phase 4A mapping rows reused directly: 281.
- Added-occupation source tasks: 296.
- New deterministic mapping rows generated: 218.
- New mappings structurally eligible for scoring: 177.
- New mapping attempts rejected for insufficient or ambiguous task evidence: 41.
- Tasks intentionally left unmapped after an occupation crossed 70% coverage: 78.
- External AI/model calls: 0.

Added-occupation tasks were ordered by their existing O\*NET importance × frequency source weight. Mapping stopped immediately after structurally valid weighted coverage reached 70%. A rejected ambiguous or insufficient description contributed no coverage, and mapping continued only until the gate was reached or every task had been examined. This is the minimum deterministic scope supported by the available evidence under the existing rubric.

The mapper remained blind to Frontier capability scores, task or occupation outcomes, production scores and target distributions. Missing task evidence was never inferred or replaced with an invented value.

## Coverage results

| Occupation | Role | Weighted coverage | Confidence | Gate | Evidence disposition |
|---|---|---:|---:|---|---|
| Graphic Designers | retained | 64.34% | 69.78 | **Blocked** | All existing mappings already assessed; no legitimate task-local remediation available |
| Sales Managers | retained | 65.43% | 70.78 | **Blocked** | All existing mappings already assessed; no legitimate task-local remediation available |
| Hairdressers | added | 59.11% | 62.84 | **Blocked** | Every task examined; short/underspecified descriptions prevented 70% coverage |
| Retail Salespersons | added | 45.06% | 46.94 | **Blocked** | Every task examined; short/underspecified descriptions prevented 70% coverage |
| Other 21 occupations | retained/added | 70.32–100.00% | 75.79–87.77 | Passed | No mapping generated after the gate was reached |

The four blocked occupations retain their calculated pilot values for inspection, but remain explicitly non-scale-eligible and receive coverage-based confidence penalties. Their scores were not forced across the gate.

## Proxy validation results

### Pairwise directional checks

Twenty-two of 24 comparisons pass their predeclared minimum difference. Two preserve direction but do not separate enough:

| Proxy | Expected higher occupation | Expected lower occupation | Observed values | Observed Δ | Required Δ | Finding |
|---|---|---|---:|---:|---:|---|
| Adoption pressure | Technical Writers | Machinists | 59.86 vs 55.60 | 4.26 | 15.00 | Direction correct, separation too weak |
| Consequence severity | Registered Nurses | Hairdressers | 54.13 vs 34.75 | 19.38 | 20.00 | Direction correct, narrowly below minimum |

No predeclared pairwise relationship is reversed. This supports comparative usefulness, but the weak technical-writing/machining separation exposes a substantive adoption-model limitation.

### Absolute expectation failures

Diagnostic band policy: high ≥60; low ≤40; medium 35–65; medium-high ≥50.

| Occupation | Proxy | Expected | Observed | Interpretation |
|---|---|---:|---:|---|
| Civil Engineers | Physical presence | medium | 26.79 | Mixed site/office presence is under-registered |
| Civil Engineers | Environment variability | medium | 34.41 | Just below medium; site variability is weakly represented |
| Healthcare Social Workers | Regulation | high | 55.80 | Regulated-care context is under-registered |
| Elementary School Teachers | Accountability | high | 55.79 | Duty-of-care accountability is under-registered |
| Technical Writers | Adoption pressure | high | 59.86 | Borderline but below the defined high band |
| Technical Writers | Structural resilience | low | 48.53 | Human/contact metadata overstates resilience for digitally substitutable output work |
| Registered Nurses | Physical presence | high | 54.60 | Direct physical care is under-registered |
| Registered Nurses | Consequence severity | high | 54.13 | Clinical consequence severity is under-registered |
| Patrol Officers | Physical presence | high | 59.31 | Borderline; real-world presence is slightly under-registered |
| Hairdressers | Physical presence | high | 53.83 | Fine manual service work is under-registered |
| Machinists | Physical presence | high | 57.73 | Equipment-bound precision work is under-registered |
| Machinists | Environment variability | high | 33.29 | Shop-floor and object variability are not captured by the outdoor/hazard-heavy proxy |
| Heavy Truck Drivers | Physical presence | high | 48.95 | Mobility/vehicle operation is not adequately represented as physical presence |

## Proxy failure diagnosis

### Physical presence

The current proxy emphasizes general physical activity, standing, walking, bending, outdoor work and hazardous equipment. It misses three distinct mechanisms:

1. fine physical manipulation and direct service delivery, exposed by Hairdressers;
2. equipment-bound precision interaction, exposed by Machinists; and
3. sustained mobility/vehicle operation, exposed by Heavy Truck Drivers.

These should become explicit subcomponents or separate domains rather than being inferred from general activity. No values should be backfilled until source elements are selected and versioned.

### Environment variability

The proxy is effective for outdoor and hazardous work—Patrol Officers and Truck Drivers score high—but weak for structured yet materially variable shops and mixed field/office occupations. Machinists and Civil Engineers demonstrate that weather/hazard exposure is not equivalent to task-environment variability.

### Regulation, accountability and consequences

O\*NET compliance activity, consequence-of-error and decision-impact ratings preserve broad comparative direction. They understate domain-specific professional regulation and duty of care for Healthcare Social Workers, Elementary Teachers and Registered Nurses. A future version needs explicit source-backed professional responsibility signals; it must not assume that licensing alone determines task-level feasibility.

### Adoption pressure

Information Security, Technical Writing and Machining all receive fairly high structural adoption values because the current model blends computer work, information processing, documentation and existing automation. The resulting Technical Writer–Machinist difference is only 4.26 points. The model does not sufficiently distinguish digital output substitutability from computer-assisted physical production.

### Structural labour resilience

The proxy broadly separates physical/human occupations from software and statistical work, but Technical Writers score 48.53 rather than the expected low band. Contact-with-others and generic decision metadata can inflate structural resilience without establishing that human interaction is essential to task delivery. The model must distinguish incidental collaboration from irreducible human dependency.

## Score and outlier review

The original twelve values exactly match Phase 4B, demonstrating cohort-extension continuity.

Notable high-exposure occupations are Statisticians (77.37), Software Developers (75.82), Technical Writers (74.20), Personal Financial Advisors (66.46) and Information Security Analysts (66.45). Low-exposure physical/real-world occupations include Automotive Service Technicians (44.79), Electricians (47.55), Heavy Truck Drivers (49.68) and Patrol Officers (50.07).

Replacement-risk extremes are similarly ordered: Statisticians (74.91), Software Developers (74.49), Technical Writers (70.28) and Financial Advisors (66.84) are high; Electricians (32.97), Patrol Officers (40.05), Truck Drivers (43.87) and Hairdressers (44.43) are low. These directions are plausible within the provisional model, but blocked occupations and proxy exceptions prevent production interpretation.

Retail Salespersons are an important coverage outlier: their AI exposure is 65.49, but only 45.06% of source weight is supported by eligible mappings. The value must not be treated as a stable occupation estimate.

## Reconciliation, replay and isolation

- Phase 4C task assessments per run: 407.
- Phase 4C occupation scores per run: 25.
- Task and occupation contribution reconciliation failures: 0.
- Retained Phase 4B continuity mismatches: 0 across 12 occupations and four compared metrics.
- Deterministic replay: exact, including scores and input hashes.
- Pairwise proxy results per run: 24; 22 pass, two warnings, zero reversals.
- Production occupation score rows before/after: 11 / 11.
- Production task score rows before/after: 23 / 23.
- Phase 4C runs with external AI calls: 0.
- Complete backend/integration/ingestion test suite: 65 passed.
- Frontend lint and production build: passed.

## Corpus-safety verdict and blockers

**Verdict: not safe for corpus-wide scoring.**

Before another scale decision:

1. revise and version the physical-presence proxy to represent fine manipulation, equipment-bound interaction and mobility without conflating them;
2. revise environment variability so structured shops and mixed site/office work are not judged only through outdoor/hazard exposure;
3. add source-backed professional regulation, duty-of-care and clinical-consequence signals or explicitly lower confidence when unavailable;
4. separate digital output substitutability from computer-assisted physical production in adoption pressure;
5. distinguish essential human dependency from incidental occupational contact in structural resilience;
6. resolve source-description coverage for Graphic Designers, Sales Managers, Hairdressers and Retail Salespersons using legitimate source evidence only; and
7. rerun this same frozen Phase 4C cohort after proxy changes before approving any larger cohort.

This report does not authorize full-corpus task mapping, full-corpus scoring, public activation or production-score recalculation.
