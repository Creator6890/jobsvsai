# JobsVsAI AI Capability Taxonomy v1

## Status and isolation

`jvs-ai-cap-v1` is a **draft private enrichment taxonomy**. It is not the legacy `ai_capabilities` production input and does not feed `task_ai_scores`, occupation scoring, recommendations, or public pages.

The companion `jvs-task-env-v1` taxonomy separates environmental automation constraints from intrinsic AI capability requirements.

## Capability definitions

1. Language comprehension
2. Language generation
3. Information retrieval
4. Quantitative reasoning
5. General reasoning and problem-solving
6. Software and code generation
7. Visual understanding
8. Visual and content generation
9. Planning and workflow execution
10. Tool and computer operation
11. Interpersonal and social interaction
12. Persuasion and negotiation
13. Physical perception
14. Fine physical manipulation
15. Mobility and real-world operation

Each definition belongs to an immutable taxonomy version and carries source, evidence, provenance, definition version, author, and optional supersession links.

## Task capability requirements

`task_capability_mapping_sets` versions a complete mapping for one O*NET task. Child `task_capability_requirement_mappings` store:

- normalized weight;
- required capability level from 0–100;
- confidence from 0–100;
- rationale and evidence;
- mapping method and method version inherited from the set;
- review state, author, provenance, and supersession history.

Reviewed or test-validated sets must contain at least one mapping and weights must sum to exactly 1 within a tolerance of 0.000001. Capability definitions must belong to the same non-retired taxonomy version as the mapping set.

Only three `architecture_test_fixture` mapping sets are seeded, for O*NET task IDs 299, 21662, and 18382. They are visibly marked `is_test_fixture=true` and are not scoring inputs.

## Environment constraints

The v1 environment taxonomy defines physical presence, fine motor control, mobility, real-world sensing, synchronous human interaction, legal accountability, safety criticality, tool access, data access, and workflow integration.

Constraint levels describe how strongly the environment limits end-to-end automation; they do not alter AI Capability Fit. Seven architecture-only test mappings validate the model.

## Benchmarks and task assessments

Benchmark snapshots can store provider/model/version, benchmark method/version, observation/publication/retrieval timestamps, expected capability count, evidence, provenance, confidence, sample size, error, and confidence intervals. A reviewed snapshot must reconcile its score count with `expected_capability_count`, and all scores must use the snapshot taxonomy version.

No benchmark snapshot or benchmark score is seeded.

`task_ai_enrichment_assessments` separately versions:

- AI Capability Fit;
- Automation Feasibility;
- Augmentation Potential.

All three use 0–100 ranges and retain mapping-set, benchmark-snapshot, input-version, method, evidence, confidence, review, and supersession provenance. No assessment is seeded.

## History and validation

Definitions, mapping sets, mappings, constraints, benchmark snapshots/scores, and task assessments are append-only. Corrections create a new row linked through `supersedes_*`; updates and deletes are rejected.

Database validation enforces:

- valid, non-retired taxonomy versions;
- mapping/snapshot/assessment taxonomy reconciliation;
- normalized task capability weights;
- valid 0–100 levels, scores, and confidence;
- valid confidence intervals;
- reviewed snapshot count reconciliation;
- zero benchmark scores and zero task assessments at the v1 architecture stage.

The admin inspector is available at `/admin/ai-enrichment`.

## Mapping rubric

The review-stage annotation rules, anchored scales, confidence states, meaningful thresholds, and representative gold controls are documented in `TASK_TO_CAPABILITY_MAPPING_RUBRIC_V1.md`. They are validation infrastructure only and do not activate this taxonomy or create new corpus mappings.
