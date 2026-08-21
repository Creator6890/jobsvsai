# JobsVsAI Task-to-Capability Mapping Rubric v1

## Status and scope

`jvs-task-capability-rubric-v1` is review-stage validation infrastructure for the draft `jvs-ai-cap-v1` and `jvs-task-env-v1` taxonomies. It does not activate either taxonomy, generate corpus mappings, create AI benchmark values, or feed occupation scoring.

The database is the authoritative machine-readable rubric. It stores 75 capability anchors, 50 environment anchors, five confidence states, decision thresholds, and an append-only representative gold dataset.

## Annotation sequence

1. Read only the supplied O*NET task statement. Do not infer occupation-wide duties, tools, setting, stakes, or expertise not stated in the task.
2. Choose `mappable`, `insufficient_description`, or `ambiguous_scope`.
3. For a mappable task, identify only capabilities that materially contribute to successful completion.
4. Select a requirement level by matching the closest adjacent anchors. Intermediate values are allowed only when the text supports interpolation.
5. Allocate weights across mapped capabilities and normalize them to exactly `1.000000`, within `0.000001`.
6. Map only explicit, material environment constraints. An omitted constraint means below the meaningful threshold, not an invented zero observation.
7. Assign confidence independently from requirement or constraint level, cite the supporting phrase, and record reviewer provenance.

## Requirement-level anchors

All 15 dimensions use 0, 25, 50, 75, and 100 anchors. The detailed dimension-specific wording is persisted in `capability_requirement_scale_anchors`.

| Capability | 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|---|
| Language comprehension | None | Short explicit instructions | Ordinary contextual material | Technical or nuanced meaning | Expert consequential interpretation |
| Language generation | None | Short fixed-format text | Coherent routine prose | Nuanced audience-specific language | Expert consequential authorship |
| Information retrieval | None | Known fact, known source | Select among ordinary sources | Synthesize incomplete/conflicting evidence | Open-ended authoritative discovery |
| Quantitative reasoning | None | Direct arithmetic/formula | Standard methods | Complex or uncertain modeling | Novel high-consequence analysis |
| General reasoning | None | Direct familiar rule | Standard multi-fact choice | Unfamiliar multi-factor trade-offs | Novel strategy under deep uncertainty |
| Software/code generation | None | Small known edit | Bounded component | Complex integrated system | Novel or safety-critical architecture |
| Visual understanding | None | Obvious object/label | Ordinary layouts or images | Subtle technical visual evidence | Expert ambiguous visual diagnosis |
| Visual/content generation | None | Template edit | Routine coherent layout | Original polished visual system | Expert art direction |
| Planning/workflow execution | None | Short fixed sequence | Bounded multi-step workflow | Dependencies, exceptions, actors | Long-horizon adaptive orchestration |
| Tool/computer operation | None | One direct familiar action | Several standard functions | Complex toolchain/integration | Dynamic high-consequence systems |
| Interpersonal/social interaction | None | Routine factual exchange | Ordinary adaptation | Emotion, trust, or conflict | Deep consequential relational judgment |
| Persuasion/negotiation | None | Simple recommendation | Routine objections | Conflicting interests | High-stakes multi-party strategy |
| Physical perception | None | Obvious direct observation | Ordinary physical conditions | Subtle changing states | Expert uncontrolled diagnosis |
| Fine physical manipulation | None | Simple repeatable movement | Ordinary controlled dexterity | Precise variable manipulation | Safety-critical exceptional dexterity |
| Mobility/real-world operation | None | Fixed controlled route | Ordinary navigation | Dynamic obstacles or terrain | Highly unpredictable operation |

Generic evidence meaning is consistent across dimensions: 0 is explicitly irrelevant; 25 supports a simple sub-step; 50 is material to routine completion; 75 is a primary complex requirement; 100 is indispensable and exceptional.

## Environment-constraint anchors

Constraint level measures how strongly the environment limits end-to-end execution. It is not AI capability fit. Detailed wording is persisted in `environment_constraint_scale_anchors`.

| Constraint | 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|---|
| Physical presence | None | Occasional setup/verification | Regular material presence | Most steps on-site | Continuous presence inseparable |
| Fine motor control | None | Simple repeatable handling | Ordinary controlled manipulation | Precise variable dexterity | Safety-critical dexterity indispensable |
| Mobility | None | Fixed path | Routine ordinary navigation | Dynamic obstacles/terrain | Unpredictable mobility indispensable |
| Real-world sensing | None | Simple observation | Routine physical observation | Subtle changing signals | Continuous expert sensing |
| Synchronous human interaction | None | Brief scripted exchange | Routine reciprocal interaction | Trust/emotion/social adaptation | Deep live relationship inseparable |
| Legal accountability | None | Routine acknowledgement | Human review/authorization | Licensed accountable judgment | Legally required human core act |
| Safety criticality | Negligible | Minor reversible harm | Material controlled consequence | Serious/irreversible harm | Immediate life-critical consequence |
| Tool access | None | One available tool/permission | Several controlled tools | Complex restricted integration | Exclusive access indispensable |
| Data access | None | Limited ordinary data | Restricted/private data | Highly sensitive/difficult data | Exclusive real-time data indispensable |
| Workflow integration | None | Simple handoff | Several systems/actors | Exception-heavy coordination | Organization-wide adaptive integration |

## Weighting and meaningful thresholds

- Include a capability only when it contributes at least 5% of successful task execution and has a requirement level of at least 10.
- Normalize included capability weights to exactly 1. A weight represents relative importance among mapped capabilities, not time spent.
- A weight of 40% or more is dominant and requires an explicit rationale.
- Map no more than six capability dimensions. If more appear plausible, retain the dimensions that are material to the task’s stated outcome; do not distribute token weights across incidental actions.
- Do not create capability requirement or environment constraint rows below level 10. Absence means “not evidenced as material,” not a measured zero.

## Confidence states

| State | Range | Rule |
|---|---:|---|
| Insufficient evidence | 0–24 | Not allowed in a reviewed mapping; use a non-mappable disposition. |
| Low | 25–49 | Material assumptions remain; second review and assumption notes are required. |
| Moderate | 50–74 | Direct support exists with limited scope/level uncertainty. |
| High | 75–89 | Requirement is explicit and the chosen anchor is well supported. |
| Expert consensus | 90–100 | Independent qualified annotations and adjudication agree. |

Confidence is evidence certainty, not difficulty. Ambiguous task-level evidence cannot exceed 49.

## Insufficient and ambiguous descriptions

- `insufficient_description`: the statement lacks the action, object, outcome, or other minimum evidence needed to identify material capabilities.
- `ambiguous_scope`: the words name an action, but omitted context could materially change the capability mix or levels.
- Both dispositions must have zero capability and zero constraint rows. Reviewers record why the text is inadequate; they never fill gaps from the occupation title or common practice.
- If only one dimension is locally ambiguous but the task remains mappable, annotate the supported dimensions and cap the uncertain row at low confidence. If ambiguity changes the overall weight allocation, mark the whole task `ambiguous_scope`.

## Gold-standard data and comparison

`gold-v1-representative-test` contains only three mappable architecture fixtures plus one ambiguous control task. Every item stores the task-statement hash, two clearly marked fixture reviewer identities, evidence, adjudication rationale, version, and timestamps. It is not training or production data.

Run the comparison tool from the project environment:

```text
python enrichment/compare_mapping_to_gold.py <candidate_mapping_set_id>
```

The JSON report includes per-dimension candidate/gold weights, levels, confidence and presence; per-constraint level/confidence deviations; aggregate mean errors; missing/extra dimensions; threshold violations; and the configured pass/fail tolerances. `--fail-on-deviation` makes the command return a non-zero status when a tolerance is exceeded.

Gold records and rubric definitions are append-only. Corrections create a new rubric or dataset version with supersession provenance.

The expanded 175-task review frame, score-blind draft mapper, independent verifier, aggregate metrics, and research acceptance gates are documented in `MAPPER_BENCHMARK_V1.md`. Automated triage is intentionally kept separate from human gold status. Provisional MVP eligibility is governed independently by `MVP_EVIDENCE_MAPPING_POLICY_V1.md`.
