# Phase 5B — Score delta report

Date: 2026-08-21

Compares `phase5b-coverage-completion-2026q3-v1` (run 4) against
`phase5-bounded-corpus-v2-2026q3` (run 2), over the same 878 occupations, the same engine,
and the same formula versions. The only difference is evidence: 2,521 additional task
assessments from the mappings the Phase 5 70% stopping rule had skipped.

**Nothing was tuned.** No score was adjusted because it moved. This report exists to
establish whether the added evidence materially alters the model.

## 1. Evidence reuse — what was recomputed and why

| | |
|---|---:|
| Task assessments, Phase 5 | 10,815 |
| Task assessments, Phase 5B | 13,336 |
| Assessments reusing an identical `(task, mapping)` pair | **10,815** |
| Newly assessed tasks | 2,521 |
| Occupations with no new eligible task | 186 |
| Occupations with new eligible tasks | 692 |
| **Occupations with unchanged evidence whose score moved** | **0** |

That last row is the control. Every Phase 5 assessment was reproduced from the identical
mapping, and the 186 occupations that gained no evidence produced bit-identical exposure and
replacement scores. Score movement occurs only where evidence changed.

The engine has no partial-evaluation path — `calculate()` computes the corpus in one
deterministic pass — so all 878 occupations were arithmetically recomputed. That is CPU
only: no mapping was regenerated, no enrichment re-derived, and no external call made. The
expensive work (mapping) was reused wholesale; the cheap work (arithmetic) was repeated and
verified to reproduce.

## 2. Magnitude of change

| Metric | Value |
|---|---:|
| Mean absolute AI Exposure change | **0.86** |
| Mean absolute Replacement Risk change | **0.29** |
| p95 absolute score delta | 2.94 |
| Maximum Exposure change | 8.87 |
| Maximum Replacement change | 3.07 |
| Occupations moving > 5 points | **5** |
| Occupations moving > 10 points | **0** |

Absolute AI Exposure delta distribution: p25 0.06, p50 0.53, p75 1.26, p90 2.10, p95 2.94,
max 8.87. Replacement Risk moves less because task evidence enters only two of its six
factors directly.

Confidence rose as coverage rose, by construction: mean 74.78 → 78.49.

## 3. Direction — is there systematic drift?

No.

| | |
|---|---:|
| Mean **signed** Exposure delta | +0.07 |
| Mean **absolute** Exposure delta | 0.86 |
| Exposure fell | 288 |
| Exposure rose | 403 |
| Exposure unchanged | 187 |
| Correlation (coverage delta, exposure delta) | **0.02** |

A signed mean of +0.07 against an absolute mean of 0.86, with movement in both directions
and essentially zero correlation between how much coverage an occupation gained and which
way its score went, means Phase 5's truncation introduced **noise, not bias**. Mapping the
highest-weighted tasks first did not systematically favour AI-legible work.

This is direct evidence bearing on the outstanding truncation-bias experiment (orientation
finding 7.5). It does not replace that experiment — this measures 70→85, not the shape of
the bias across the whole curve — but it constrains the answer: at corpus scale, the bias
term is small and unsigned.

## 4. The largest movements

| SOC | Title | Coverage | New tasks | Exposure | ΔExp | ΔRepl |
|---|---|---|---:|---|---:|---:|
| 51-9123.00 | Painting, Coating, and Decorating Workers | 73.6 → 94.1 | +2 | 63.1 → 54.2 | −8.87 | −3.07 |
| 33-2011.00 | Firefighters | 71.2 → 85.6 | +6 | 61.1 → 54.6 | −6.47 | −2.58 |
| 35-2015.00 | Cooks, Short Order | 74.7 → 92.1 | +2 | 68.9 → 63.2 | −5.69 | −1.91 |
| 51-4023.00 | Rolling Machine Setters, Metal and Plastic | 70.8 → 87.3 | +4 | 52.9 → 47.3 | −5.57 | −1.71 |
| 51-2022.00 | Electrical and Electronic Equipment Assemblers | 72.6 → 87.7 | +3 | 49.5 → 54.7 | +5.16 | +1.89 |
| 53-7041.00 | Hoist and Winch Operators | 73.8 → 86.9 | +2 | 31.8 → 36.7 | +4.96 | +1.15 |
| 51-4035.00 | Milling and Planing Machine Setters | 72.3 → 89.6 | +3 | 42.2 → 47.1 | +4.94 | +1.16 |
| 51-9083.00 | Ophthalmic Laboratory Technicians | 73.8 → 87.6 | +3 | 50.9 → 55.4 | +4.55 | +1.88 |
| 47-4021.00 | Elevator and Escalator Installers and Repairers | 70.7 → 85.6 | +4 | 41.2 → 36.6 | −4.54 | −0.76 |
| 53-7063.00 | Machine Feeders and Offbearers | 73.2 → 87.5 | +2 | 51.6 → 47.1 | −4.47 | −1.93 |

### What drove them

**51-9123.00 Painting, Coating, and Decorating Workers — Exposure 63.1 → 54.2.** The two
newly included tasks are the heaviest-weighted work in the occupation and are manual:

- weight 5,048 · task exposure 25.2 · fit 11.9 · automation 42.5 — *"Clean surfaces of workpieces in preparation for coating, using cleaning fluids, solvents, brushes…"*
- weight 4,784 · task exposure 19.4 · fit 4.1 · automation 38.4 — *"Rinse, drain, or wipe coated workpieces to remove excess coating material…"*

Phase 5 stopped before reaching them and scored the occupation on its more legible
remainder. The occupation did not become less exposed; it was previously measured on a
partial task set.

**33-2011.00 Firefighters — Exposure 61.1 → 54.6.** Six new tasks, including
*"Position and climb ladders… or to rescue individuals"* (exposure 13.4, fit 2.7) and
*"Rescue survivors from burning buildings"* (exposure 14.9, fit 4.7), alongside genuinely
more exposed inspection work (exposure 37.2 and 40.8). The mix pulled the weighted mean down.

**35-2015.00 Cooks, Short Order — Exposure 68.9 → 63.2.** *"Perform general cleaning
activities in kitchen and dining areas"* (weight 6,899, exposure 20.1) is the single
heaviest task in the occupation and had never been assessed.

The upward movers are the mirror image: assemblers, machine setters and lab technicians
gained routine, procedural tasks that score *higher* than their previously-measured
remainder. Both directions are the same mechanism — a fuller task set — which is why the
signed mean is near zero.

## 5. Reconciliation and replay

| Check | Result |
|---|---|
| Task contribution reconciliation failures | 0 of 13,336 |
| Occupation factor reconciliation failures | 0 of 878 |
| Scores outside 0–100 | 0 |
| Coverage gate violations | 0 |
| Deterministic replay (`…-replay-v1`, run 5) | **matched** |
| Production score writes | 0 |
| Public activations | 0 |

Score ranges: Exposure 23.62–80.35, Replacement 29.25–74.91, Confidence 20.30–88.70.

## 6. Verdict on materiality

The added evidence **does not materially alter the model**. It sharpens individual
occupations — five move more than 5 points, all of them physical or machine-tending
occupations that Phase 5 had measured on a partial task set — while leaving the corpus
distribution, the factor structure and the direction of every relationship intact. No
occupation moved more than 10 points. No new anomaly type appeared.

The correct reading is not "the scores changed" but "the scores are now computed on the
evidence that was always available".
