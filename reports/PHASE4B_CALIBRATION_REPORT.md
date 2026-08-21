# Phase 4B Calibration Report

Date: 2026-08-20  
Status: calibration complete; **no-scale verdict**  
Scope: the frozen Phase 4A cohort and mapping run only

## Executive verdict

Phase 4B removed the Phase 4A score saturation without generating task mappings, changing the 12-occupation cohort, calling an AI model, or writing public/production scores. The calibrated formulas produce materially wider and more plausible occupation replacement-risk separation, and every persisted contribution reconciles.

The result is still **no-scale**. Ten occupations pass the provisional 70% weighted-coverage and 70-confidence gates, but Graphic Designers and Sales Managers do not. The adoption-pressure and labour-market-resilience inputs are explicitly provisional structural proxies rather than observed adoption or labour-market measurements. Phase 4B is suitable for further pilot review, not activation or corpus-wide scoring.

## Frozen inputs and isolation

- Cohort: `phase4a-2026q3-v1`, 12 occupations.
- Mapping run: `phase4a-pilot-mapper-v1-2026q3`, database ID 7.
- Source tasks: 281; scoring-eligible mappings: 230; policy exclusions: 51.
- New mapping calls in every Phase 4B run: 0.
- Frontier track: commercially deployable, provisional 2026-Q3 values.
- Production occupation score rows before/after: 11 / 11.
- Legacy production task score rows before/after: 23 / 23.
- Technical-frontier values used: 0.

The authoritative corrected runs are `phase4b-calibration-v1.1-2026q3` and `phase4b-replay-v1.1-2026q3`. The replay matched exactly. The original v1 run is retained as append-only history; its score outputs are identical, but its signed distribution-delta summary used a bounded score-rounding helper and therefore clamped negative deltas to zero. V1.1 corrects only that audit representation and does not alter formulas or scores.

## Saturation diagnosis and distribution change

| Scope | Metric | Phase 4A mean | Phase 4B mean | Mean Δ | Phase 4A median | Phase 4B median | Phase 4A SD | Phase 4B SD | ≥90 before → after |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Task | AI capability fit | 88.24 | 74.08 | -14.16 | 100.00 | 90.63 | 25.21 | 27.43 | 178 → 119 |
| Task | Automation feasibility | 90.71 | 61.48 | -29.23 | 98.64 | 60.69 | 17.59 | 16.25 | 179 → 1 |
| Task | Augmentation potential | 64.55 | 47.60 | -16.96 | 70.00 | 45.77 | 12.40 | 18.89 | 0 → 0 |
| Task | Task AI exposure | 85.30 | 63.12 | -22.19 | 95.22 | 70.02 | 21.37 | 17.30 | 173 → 0 |
| Occupation | AI exposure | 85.52 | 64.16 | -21.36 | 89.55 | 66.77 | 9.59 | 9.57 | 5 → 0 |
| Occupation | Replacement risk | 85.35 | 56.87 | -28.48 | 87.52 | 57.14 | 5.52 | 11.77 | 3 → 0 |
| Occupation | Confidence | 84.08 | 80.10 | -3.98 | 83.70 | 80.41 | 5.75 | 5.65 | 3 → 0 |

Phase 4A saturation came from three compounding behaviors: capability fit became 100 whenever current capability exceeded a requirement; constraint resistance was too weak to offset that fit; and augmentation clustered near 70 even for tasks approaching full automation. The occupation formula then inherited those compressed, high-valued task distributions while adoption and labour factors remained neutral placeholders.

## Deterministic calibration changes

### Capability fit

`task-capability-fit-v2-calibration` applies a logistic transformation to the current-AI-minus-required-level margin with slope 14, then uses a weighted geometric mean. A critical dimension below 50 match applies an eight-point-headroom bottleneck. Meeting a requirement now maps to 50 rather than automatically to 100.

### Automation feasibility

`automation-feasibility-v2-calibration` combines capability fit and nonlinear environment-constraint resistance at 50/50. Constraint levels use exponent 1.35. Critical physical, mobility, variability, human, regulatory, accountability and consequence domains apply explicit caps. Direct task constraints take precedence; only the six approved occupation proxy domains can fill a missing direct constraint.

Across the 230 scored tasks and ten constraint domains per task:

- 251 domain values came from direct task mappings.
- 1,204 came from approved occupation metadata proxies.
- 845 remained explicitly unfilled because no task mapping or approved proxy existed.
- 423 critical caps were applied: 3 from direct mappings and 420 from proxy-derived domain values.
- No absent value was invented or treated as neutral evidence.

### Augmentation

`augmentation-potential-v2-calibration` multiplies capability fit by an automation-complement curve, retaining a 0.15 collaboration floor and 0.85 complement weight. This removes the artificial Phase 4A cluster around 70.

### Occupation aggregation

`phase4b-occupation-score-v2-calibration` uses:

- Task exposure: capability fit 0.35, automation feasibility 0.45, augmentation 0.20.
- Replacement risk: task automation 0.35, capability proximity 0.10, human-dependency resistance 0.15, physical-dependency resistance 0.15, adoption pressure 0.15, and inverse structural labour resilience 0.10.
- Minimum weighted coverage: 70%.
- Below-threshold confidence penalty: 0.75 points for each missing coverage point.
- Minimum scale confidence: 70.

## Provisional metadata proxies

`phase4b-occupation-proxy-v1` derives six missing-constraint domains from versioned O\*NET work-context and work-activity ratings:

1. physical presence;
2. environment variability;
3. human dependency;
4. regulation;
5. accountability; and
6. consequence severity.

Every source rating stores the O\*NET element/scale identifiers, normalized value, sample size, standard error, suppression/relevance flags, source version, source record ID and row hash. Missing and suppressed components are excluded and remaining weights are renormalized. The snapshot records the missing-weight and suppression effects and applies confidence penalties; it never imputes a value.

Adoption pressure uses current degree of automation, computer work, information processing and documentation activity. Structural labour resilience uses human dependency, physical presence, consequence severity, decision/problem-solving importance, decision freedom and inverse current automation. These models explicitly exclude incomplete `phase1_seed` market signals, production scores and downstream automation outcomes. Their confidence ceilings are 68 and 60 respectively; the combined snapshots are capped at 60.

## Occupation comparison and coverage

| Occupation | AI exposure A → B | Replacement risk A → B | Coverage | Final confidence | Coverage penalty | Scale gate |
|---|---:|---:|---:|---:|---:|---|
| Statisticians | 94.31 → 77.37 | 91.48 → 74.91 | 98.08% | 87.77 | 0.00 | Pass |
| Software Developers | 92.46 → 75.82 | 90.24 → 74.49 | 85.98% | 82.84 | 0.00 | Pass |
| Sales Managers | 94.18 → 69.83 | 90.22 → 61.04 | 65.43% | 70.78 | 3.43 | **Blocked** |
| Graphic Designers | 88.05 → 68.88 | 87.26 → 64.19 | 64.34% | 69.78 | 4.25 | **Blocked** |
| Photographers | 89.71 → 68.64 | 88.84 → 52.79 | 81.50% | 80.92 | 0.00 | Pass |
| Accountants and Auditors | 91.70 → 67.03 | 89.05 → 61.73 | 82.33% | 79.90 | 0.00 | Pass |
| Cooks, Restaurant | 81.73 → 66.50 | 84.66 → 55.17 | 74.23% | 77.52 | 0.00 | Pass |
| Secondary School Teachers | 93.13 → 65.00 | 87.79 → 59.12 | 88.87% | 82.78 | 0.00 | Pass |
| Nurse Practitioners | 89.38 → 60.13 | 84.88 → 51.54 | 96.26% | 86.10 | 0.00 | Pass |
| Lawyers | 77.22 → 58.40 | 79.34 → 55.09 | 77.18% | 78.74 | 0.00 | Pass |
| Electricians | 69.89 → 47.55 | 76.54 → 32.97 | 100.00% | 87.65 | 0.00 | Pass |
| Automotive Service Technicians and Mechanics | 64.54 → 44.79 | 73.91 → 39.39 | 74.72% | 76.43 | 0.00 | Pass |

The strongest remaining exposure outliers are Statisticians and Software Developers. The lowest exposures are Automotive Service Technicians and Electricians. Replacement-risk dispersion increased from 5.52 to 11.77 standard-deviation points, materially improving separation. These are useful calibration outcomes, not claims of empirical predictive validity.

## Reconciliation and validation

- 230/230 task assessments reconcile capability, constraint and task-exposure contributions.
- 12/12 occupation assessments reconcile normalized task weights, task contributions, replacement-factor weights and proxy calculations.
- All seven before/after distributions reconcile to identical Phase 4A and Phase 4B row counts.
- The v1.1 deterministic replay matches all 230 task rows and 12 occupation rows exactly, including input hashes.
- 58 backend, integration, ingestion and scoring tests pass.
- Frontend lint passes.
- Next.js production build passes, including `/admin/phase4a`.

## Remaining blockers before scale

1. Resolve or explicitly exclude enough weighted tasks for Graphic Designers and Sales Managers to reach the 70% coverage gate; do not force their scores.
2. Review the high rate of occupation-level fallback (1,204 of 2,300 domain evaluations) and determine which domains require task-local evidence before broader use.
3. Replace or externally validate the provisional structural adoption and labour-resilience models with versioned observed evidence before interpreting replacement risk as a production measure.
4. Conduct semantic review of high-impact proxy bottlenecks and the Statisticians/Software Developers outliers.
5. Repeat calibration on a separately approved cohort before any corpus-wide run. This Phase 4B result does not authorize new mappings, full-corpus scoring, public activation or production-score recalculation.
