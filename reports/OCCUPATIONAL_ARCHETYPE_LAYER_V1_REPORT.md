# JobsVsAI Occupational Archetype Layer v1 — draft pilot report

Assessment date: 2026-08-20  
Source data: O*NET 30.3  
Model: `occupational-archetype-v1-draft-2026q3`  
Pilot run: `archetype-phase4c-pilot-v1-2026q3`  
Replay: `archetype-phase4c-replay-v1-2026q3`

## Verdict

**Do not adopt the archetype layer for corpus or production scoring. Keep the draft layer disabled and retain it as an experimental, reversible enrichment.**

The implementation is technically sound and isolated: discovery and scoring are deterministic, all stored contributions reconcile, the replay is exact, the 70% coverage gate is unchanged, the same four occupations remain blocked, and there were no external AI calls, regenerated mappings, public changes or production score writes. The methodological value has not yet been established. The overlay does not improve any predeclared validation outcome, leaves all 13 absolute-band failures and both weak pairwise warnings unresolved, and produces one material Technical Writers score shift without validation evidence that the shift is better.

## Discovery methodology

The model uses 231 work-characteristic features:

- normalized O*NET skill-level ratings;
- normalized O*NET ability-level ratings;
- normalized work-activity importance ratings;
- normalized work-context ratings;
- 48 deterministic hashed TF-IDF task-language features.

SOC codes, occupation titles and industry labels are excluded from clustering. Titles are used only after discovery to create readable candidate names and select representative examples. Features are z-normalized and balanced by source domain. Discovery uses deterministic farthest-point initialization followed by Euclidean k-means. It converged in 17 iterations. No random or external model call is used.

Of 1,016 current occupations, 894 meet the explicit 65% O*NET feature-completeness rule and receive a primary membership. The remaining 122 are excluded; they are not represented as zero-filled feature vectors. The model supports one optional secondary membership, with strength, confidence, distance, feature completeness and source evidence persisted for every assignment.

## Candidate archetypes

The requested 20–40 range resolves to 28 candidates. These names are source-derived working labels, not reviewed editorial taxonomy.

| Code | Candidate interpretation | Members |
|---|---|---:|
| A01 | Learning strategies and public-speaking work | 101 |
| A02 | Staffing and administrative work | 62 |
| A03 | Seated and negotiation-heavy work | 63 |
| A04 | Material and financial resource management | 35 |
| A05 | Technology-design and science work | 65 |
| A06 | Seated computer work | 28 |
| A07 | Aggressive-person and enclosed-vehicle work | 27 |
| A08 | Peripheral-vision and enclosed-equipment work | 1 |
| A09 | Programming and technology-design work | 42 |
| A10 | Equipment selection and repair work | 22 |
| A11 | Infection-exposure and public-facing work | 20 |
| A12 | Repair and equipment-maintenance work | 31 |
| A13 | Radiation and infection-exposure work | 28 |
| A14 | Administrative and repetitive work | 26 |
| A15 | Public-facing and standing work | 29 |
| A16 | Caregiving and infection-exposure work | 29 |
| A17 | Repetitive hand-manipulation work | 32 |
| A18 | Dynamic-flexibility and explosive-strength work | 4 |
| A19 | Dynamic-flexibility and balance work | 3 |
| A20 | Clinical caregiving and infection-exposure work | 35 |
| A21 | Installation and repair work | 43 |
| A22 | Night-vision and vehicle-operation work | 26 |
| A23 | Climbing, kneeling and crawling work | 16 |
| A24 | Kneeling, crouching and bending work | 19 |
| A25 | Whole-body vibration and open-equipment work | 37 |
| A26 | Balance and general physical-activity work | 2 |
| A27 | Equipment-paced machine-control work | 65 |
| A28 | Night-vision and peripheral-vision work | 3 |

## Assignment quality

Cluster size ranges from 1 to 101. Mean nearest-versus-second-cluster separation is 0.1972, with a 0.0854 minimum. One cluster is a singleton. There are 844 secondary memberships among 894 occupations, showing that the v1 secondary-membership threshold is too permissive and/or many boundaries are weak. This is stored as a quality warning rather than hidden.

Several Phase 4C assignments are directionally interpretable:

- Software Developers and Statisticians → A09 programming/technology design;
- Nurse Practitioners and Registered Nurses → A20 clinical caregiving/infection exposure;
- Electricians and Automotive Technicians → A21 installation/repair;
- Restaurant Cooks → A17 repetitive hand manipulation;
- Police Patrol Officers → A07 aggressive-person/enclosed-vehicle work;
- Retail Salespersons → A15 public-facing/standing work;
- Heavy Truck Drivers → A22 night-vision/vehicle operation.

Important weak or misleading assignments remain:

- Graphic Designers and Technical Writers → A03 seated/negotiation-heavy work;
- Accountants, Lawyers and Sales Managers → A01 learning/public-speaking work;
- Healthcare Social Workers and Elementary Teachers → A02 staffing/administrative work.

These are evidence that the clusters remain candidates requiring interpretation and stability testing, not production categories.

## Structural prior and adjustment policy

Each archetype stores versioned baselines for 11 structural dimensions:

1. physical presence;
2. physical manipulation;
3. mobility / real-world operation;
4. environment variability;
5. human dependency;
6. regulation;
7. accountability / duty of care;
8. consequence severity;
9. real-time interaction;
10. privacy sensitivity;
11. adoption pressure.

For the 25-occupation pilot, the final proxy is:

`result = priorWeight × blendedArchetypeBaseline + (1 − priorWeight) × occupationSourceEvidence`

The primary and optional secondary baseline are blended by membership strength. Prior weight is deterministic, bounded at 0.28 and reduced when occupation evidence is stronger. The mean applied prior weight is approximately 0.11–0.13 by dimension. Every record stores baseline, source value, source evidence, confidence, prior weight, signed adjustment, result, formula version, warnings and reconciliation. No pilot dimension required a prior-only fallback; all 275 adjustments had direct O*NET-derived occupation evidence. A prior-only missing-evidence policy nevertheless exists and would explicitly warn, cap confidence and never fabricate a source value.

Privacy sensitivity is explicitly low confidence because current O*NET characteristics provide only indirect evidence. Labour-market resilience is not an archetype v1 structural dimension and remains exactly the Phase 4C value.

## Phase 4C comparison

The overlay scores exactly the frozen 25-occupation cohort and reuses all 407 scoring-eligible task mappings and assessments. It makes no new task mappings and preserves all Frontier, rubric, task-weight, formula and coverage dependencies.

### Distributions

| Metric | Phase 4C mean | Archetype mean | Phase 4C SD | Archetype SD |
|---|---:|---:|---:|---:|
| Task capability fit | 72.04 | 72.04 | — | — |
| Task automation feasibility | 60.69 | 60.67 | 15.12 | 14.54 |
| Task augmentation potential | 46.76 | 46.89 | — | — |
| Task AI exposure | 61.88 | 61.89 | — | — |
| Occupation AI exposure | 62.63 | 62.59 | 8.27 | 8.06 |
| Occupation replacement risk | 55.63 | 55.57 | 10.18 | 9.68 |
| Occupation confidence | 76.44 | 76.44 | — | — |

Capability fit is unchanged by design. The overlay slightly compresses automation and occupation-score variance. It does not create an empirical confidence improvement.

Occupation replacement-risk delta ranges from −4.4838 to +1.0794, with a −0.0647 mean. AI-exposure delta ranges from −3.2771 to +0.3729, with a −0.0332 mean. The largest outlier is Technical Writers: −4.4838 replacement risk and −3.2771 AI exposure. That movement is not supported by a validation outcome improvement and is a material caution against adoption.

### Predeclared validations

| Check | Phase 4C | Archetype v1 |
|---|---:|---:|
| Pairwise checks passed | 22 / 24 | 22 / 24 |
| Weak-direction warnings | 2 | 2 |
| Direction reversals | 0 | 0 |
| Absolute-band passes | 33 / 46 | 33 / 46 |
| Absolute-band failures | 13 | 13 |
| Outcome improvements | — | 0 |
| Outcome regressions | — | 0 |

The adoption-pressure warning moves in the desired numerical direction (delta 4.2625 → 5.0851) but remains far below the 15-point minimum. The consequence-severity warning weakens (19.3750 → 17.9037) while preserving direction. Neither changes category.

All Phase 4C absolute failures remain unresolved, including physical-presence expectations for nurses, police, hairdressers, machinists and truck drivers; environment variability for civil engineers and machinists; teacher accountability; nurse consequence severity; social-worker regulation; Technical Writers adoption pressure and structural resilience. Labour-market resilience is intentionally unchanged.

## Coverage and isolation

The 70% weighted-coverage gate is identical before and after. Twenty-one occupations remain scale-eligible. These four remain blocked because no independent task evidence was added:

- Graphic Designers (`27-1024.00`);
- Sales Managers (`11-2022.00`);
- Hairdressers, Hairstylists, and Cosmetologists (`39-5012.00`);
- Retail Salespersons (`41-2031.00`).

Production tables remain at 11 occupation-score rows and 23 task-score rows. The archetype layer writes only to dedicated append-only pilot tables. The global feature flag is disabled and production activation is prohibited by schema constraint.

## Reconciliation, tests and compute cost

- Deterministic replay: exact match across 407 task assessments and 25 occupation scores.
- Archetype adjustments reconciled: 275 / 275.
- Validation rows: 70 / 70 reconciled.
- Complete backend suite: 69 passed.
- Frontend: lint passed; production build passed.
- Admin responsive verification: passed at 360, 390, 430, 768, 1024 and 1440 pixels with no horizontal overflow; expanded provenance remains contained on mobile.
- Approximate local Docker runtime: discovery 14.7 seconds; pilot 5.8 seconds; replay 5.7 seconds.

## Required work before reconsidering adoption

1. Human-review and rename candidate archetypes; reject misleading interpretations.
2. Tighten secondary-membership rules and add an explicit unassigned/weak-boundary state.
3. Resolve the singleton and very small clusters, then evaluate stability across deterministic alternative feature weights and cluster counts.
4. Define archetype-quality acceptance gates before using priors in scoring.
5. Address direct structural evidence gaps rather than expecting archetype priors to repair them.
6. Re-run the same frozen 25-occupation validation and require measurable predeclared improvements without new reversals or material unexplained score outliers.

Until those checks pass, the layer should remain available only through the read-only admin inspector at `/admin/archetypes`.
