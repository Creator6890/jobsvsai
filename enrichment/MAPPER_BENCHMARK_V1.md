# JobsVsAI Mapper Benchmark and Draft Candidate Pipeline v1

## Current benchmark status

`gold-v1-175-pending-human-review` is a versioned review frame containing 175 O*NET tasks across 28 occupations. The occupations span management, business, software, engineering, science, counseling, law, education, design, media, health care, protective service, food preparation, groundskeeping, personal service, sales, administration, farming, construction, maintenance, production, and transportation.

Task selection is deterministic and stratified across short, medium, and detailed statements. The initial disposition is automated triage only:

- 52 proposed mappable cases;
- 113 proposed ambiguous-scope cases;
- 10 proposed insufficient-description cases.

These labels are not represented as human gold annotations. The dataset remains `draft`, its provenance says `not_human_reviewed`, and it has zero human-reviewed or adjudicated tasks.

## Human review and adjudication

Each review event is immutable and stores:

- reviewer identifier, kind, organization, and review round;
- proposed disposition;
- structured capability requirements and environment constraints;
- evidence and task-local rationale;
- adjudication status and notes;
- supersession and timestamp provenance.

Automated, assistant, and fixture reviews never count toward human-review gates. Benchmark acceptance requires at least two independent human reviewers per counted task. Disagreement is resolved through a separate human adjudication event. The accepted annotations are materialized only into a new dataset version; the draft frame is never overwritten.

The research-grade gate requires at least 150 independently human-reviewed tasks spanning 25 occupations. Until those records exist, research evaluations are `ineligible` regardless of mapper metrics. This preserved gate is not a prerequisite for provisional MVP scoring eligibility; that decision is governed separately by the versioned evidence-based policy in `MVP_EVIDENCE_MAPPING_POLICY_V1.md`.

## Draft score-blind mapper

`draft_candidate_mapper.py` consumes only:

- benchmark task membership;
- O*NET task identifier, occupation code, statement, and statement hash;
- draft capability and environment definition identifiers;
- Mapping Rubric v1 thresholds.

It explicitly prohibits AI benchmark tables, AI Capability Fit, Automation Feasibility, Augmentation Potential, legacy task AI scores, and occupation scores. The current deterministic mapper emits only a disposition and structured capability/constraint requirement rows. It does not write `task_capability_mapping_sets`, activate taxonomy data, or produce scoring inputs.

The v1 run emitted 175 candidate task records. Non-mappable records contain no inferred capability or constraint rows.

## Independent verification

`verify_candidate_mapping.py` is a separate implementation and does not import the mapper rules. It verifies:

- task-statement hash reconciliation;
- capability taxonomy and environment taxonomy consistency;
- normalized weights and dimension-count limits;
- minimum meaningful weights and levels;
- no requirement/constraint rows on ambiguous or insufficient tasks;
- run input/output reconciliation;
- the prohibited-input attestation.

The corrected immutable verification run `independent-structure-v1.1` passed all 175 tasks with zero errors and zero false-inference findings. The earlier failed verification is retained as history rather than overwritten.

## Aggregate evaluation metrics

`evaluate_candidate_mapper.py` records:

- mean capability-set Jaccard agreement;
- mean absolute capability-weight deviation;
- mean absolute requirement-level deviation;
- mean absolute constraint-level deviation;
- confidence agreement;
- counts and rates for extra and missing capability dimensions;
- disposition agreement;
- false-inference count and rate on ambiguous/insufficient cases.

Evaluation against the small architecture controls is retained as `ineligible`: the mapper has not met the human-review or occupation-coverage prerequisites, and most quality metrics are below the review-stage gates. This is expected for a first deterministic draft and prevents accidental promotion.

## Configurable research acceptance gates

`mapper-acceptance-gates-v1` currently requires:

- at least 150 independently human-reviewed tasks;
- at least 25 occupations;
- capability-set agreement at least 0.80;
- mean weight deviation no more than 0.08;
- mean requirement-level and constraint deviations no more than 10 points;
- confidence agreement at least 0.75;
- extra and missing dimension rates no more than 0.10;
- false-inference rate no more than 0.02;
- a passing independent verification run.

Gate configurations and evaluations are append-only and versioned. They remain available for future research-grade validation but do not block MVP per-task eligibility. Passing a research gate does not activate a taxonomy or mapping; activation remains a separate step.
