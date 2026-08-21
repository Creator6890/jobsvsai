"""Create only the new mappings required by the targeted Phase 4C cohort.

The original Phase 4A mapping rows are referenced directly. Added occupations
are processed in descending O*NET importance×frequency order and mapping stops
as soon as validated weighted coverage reaches the unchanged 70% gate.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import asyncpg

try:
    from .generate_phase4a_pilot_mappings import (
        FORBIDDEN_INPUTS,
        capability_payload,
        constraint_payload,
        disposition,
    )
except ImportError:
    from generate_phase4a_pilot_mappings import (
        FORBIDDEN_INPUTS,
        capability_payload,
        constraint_payload,
        disposition,
    )


PROMPT_TEXT = """JobsVsAI Phase 4C targeted validation mapper v1.
Use only the selected added occupation's O*NET task statement, source task
importance/frequency for minimum-scope ordering, Task-to-Capability Rubric v1,
AI Capability Taxonomy v1, Environment Constraint Taxonomy v1 and MVP evidence
policy. Never read AI capability scores, automation outcomes, prior occupation
scores or target score distributions. Stop generating mappings for an added
occupation once structurally validated source-weight coverage reaches 70%.
Do not infer missing task scope or invent requirements.
"""


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


async def generate(
    run_version: str = "phase4c-targeted-mapper-v1-2026q3",
    cohort_version: str = "phase4c-2026q3-v1",
) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        cohort = await connection.fetchrow(
            "SELECT * FROM phase4c_validation_cohorts WHERE cohort_version=$1",
            cohort_version,
        )
        if cohort is None:
            raise ValueError(f"Missing Phase 4C cohort {cohort_version}")
        total_source_tasks = await connection.fetchval(
            """
            SELECT count(*) FROM phase4c_validation_occupations occupation
            JOIN onet_tasks task ON task.occupation_code=occupation.occupation_code AND task.is_current
            WHERE occupation.cohort_id=$1
            """,
            cohort["id"],
        )
        existing_scope = await connection.fetchval(
            "SELECT count(*) FROM phase4c_task_mapping_scope WHERE cohort_id=$1", cohort["id"]
        )
        if cohort["new_mapping_run_id"] is not None and existing_scope == total_source_tasks:
            run = await connection.fetchrow(
                "SELECT * FROM ai_generated_task_mapping_runs WHERE id=$1",
                cohort["new_mapping_run_id"],
            )
            await transaction.commit()
            return {
                "mappingRunId": run["id"],
                "runVersion": run["run_version"],
                "newMappings": run["output_task_count"],
                "externalModelCalls": 0,
                "scopeRows": existing_scope,
                "reused": True,
            }
        if existing_scope:
            raise ValueError("Partial Phase 4C mapping scope exists; refusing to overwrite history")

        policy = await connection.fetchrow(
            """
            SELECT policy.*,rubric.environment_taxonomy_version_id
            FROM task_mapping_evidence_policy_versions policy
            JOIN task_mapping_rubric_versions rubric ON rubric.id=policy.rubric_version_id
            WHERE policy.policy_version='mvp-evidence-policy-v1'
            """
        )
        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4C targeted validation'"
        )
        retained_mapping_run_id = await connection.fetchval(
            "SELECT mapping_run_id FROM phase4a_pilot_cohorts WHERE id=$1",
            cohort["retained_cohort_id"],
        )
        occupations = await connection.fetch(
            """
            SELECT validation.*,source_occupation.title
            FROM phase4c_validation_occupations validation
            JOIN onet_occupations source_occupation
              ON source_occupation.onet_soc_code=validation.occupation_code AND source_occupation.is_current
            WHERE validation.cohort_id=$1 ORDER BY validation.cohort_order
            """,
            cohort["id"],
        )
        tasks = await connection.fetch(
            """
            SELECT task.*,validation.id validation_occupation_id,validation.cohort_role,
                   validation.cohort_order
            FROM phase4c_validation_occupations validation
            JOIN onet_tasks task ON task.occupation_code=validation.occupation_code AND task.is_current
            WHERE validation.cohort_id=$1
            ORDER BY validation.cohort_order,task.task_id
            """,
            cohort["id"],
        )
        retained_mappings = {
            row["onet_task_id"]: dict(row)
            for row in await connection.fetch(
                """
                SELECT mapping.id,mapping.onet_task_id,mapping.mapping_run_id
                FROM ai_generated_task_mappings mapping
                WHERE mapping.mapping_run_id=$1
                """,
                retained_mapping_run_id,
            )
        }

        selected_task_ids: set[int] = set()
        selection_ranks: dict[int, int] = {}
        projected_coverage: dict[int, float] = {}
        tasks_by_occupation: dict[int, list[asyncpg.Record]] = defaultdict(list)
        for task in tasks:
            tasks_by_occupation[task["validation_occupation_id"]].append(task)
        for occupation in occupations:
            if occupation["cohort_role"] != "added_validation":
                continue
            source_tasks = tasks_by_occupation[occupation["id"]]
            weighted = [task for task in source_tasks if task["weighting_eligible"]]
            total_weight = sum(float(task["importance_score"] * task["frequency_score"]) for task in weighted)
            covered_weight = 0.0
            ordered = sorted(
                weighted,
                key=lambda task: (
                    -float(task["importance_score"] * task["frequency_score"]), task["task_id"]
                ),
            )
            for rank, task in enumerate(ordered, 1):
                if total_weight > 0 and 100.0 * covered_weight / total_weight >= 70.0:
                    break
                selected_task_ids.add(task["task_id"])
                selection_ranks[task["task_id"]] = rank
                if disposition(task["statement"])[0] == "none":
                    covered_weight += float(task["importance_score"] * task["frequency_score"])
            projected_coverage[occupation["id"]] = 100.0 * covered_weight / total_weight

        capability_ids = {
            row["slug"]: row["id"]
            for row in await connection.fetch(
                "SELECT id,slug FROM ai_capability_definitions WHERE taxonomy_version_id=$1",
                policy["taxonomy_version_id"],
            )
        }
        constraint_ids = {
            row["slug"]: row["id"]
            for row in await connection.fetch(
                "SELECT id,slug FROM task_environment_constraint_definitions WHERE environment_taxonomy_version_id=$1",
                policy["environment_taxonomy_version_id"],
            )
        }
        prompt_hash = hashlib.sha256(PROMPT_TEXT.encode()).hexdigest()
        source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        allowed_manifest = {
            "allowed": [
                "phase4c_added_cohort_membership",
                "onet_task_id",
                "onet_task_statement",
                "onet_task_importance_frequency_for_minimum_scope_ordering",
                "taxonomy_definitions",
                "mapping_rubric",
                "mvp_evidence_policy",
            ],
            "prohibited": FORBIDDEN_INPUTS,
        }
        run_id = await connection.fetchval(
            """
            INSERT INTO ai_generated_task_mapping_runs (
              run_version,taxonomy_version_id,rubric_version_id,evidence_policy_version_id,
              provider_name,model_name,model_version,model_snapshot_date,prompt_name,prompt_version,
              prompt_sha256,system_prompt_sha256,inference_configuration,allowed_input_manifest,
              prohibited_input_attestation,status,input_task_count,output_task_count,source_id,
              evidence,provenance,created_by
            ) VALUES ($1,$2,$3,$4,'JobsVsAI','rubric-authored deterministic mapper','phase4c-v1',
              DATE '2026-08-20','Phase 4C minimum-scope validation prompt','phase4c-prompt-v1',$5,$5,
              $6,$7,true,'completed',$8,$8,$9,$10,$11,'system:phase4c-targeted-mapper') RETURNING id
            """,
            run_version,
            policy["taxonomy_version_id"],
            policy["rubric_version_id"],
            policy["id"],
            prompt_hash,
            json.dumps(
                {
                    "temperature": 0,
                    "maximumCapabilities": 6,
                    "runtimeExternalModelCalls": 0,
                    "selectionPolicy": "descending_source_weight_until_70_percent_validated_coverage",
                }
            ),
            json.dumps(allowed_manifest),
            len(selected_task_ids),
            source_id,
            json.dumps([{"promptSha256": prompt_hash, "sourceCodeSha256": source_hash}]),
            json.dumps(
                {
                    "phase": "4C",
                    "targetedValidationOnly": True,
                    "scoreBlind": True,
                    "activationAllowed": False,
                    "productionScoreWritesAllowed": False,
                    "sourceCodeSha256": source_hash,
                }
            ),
        )

        generated: dict[int, dict[str, Any]] = {}
        for task in tasks:
            if task["task_id"] not in selected_task_ids:
                continue
            ambiguity_state, mapping_confidence, rationale = disposition(task["statement"])
            mapping_id = await connection.fetchval(
                """
                INSERT INTO ai_generated_task_mappings (
                  mapping_run_id,onet_task_id,mapping_version,task_statement_hash,ambiguity_state,
                  mapping_confidence,initial_validation_status,initial_review_state,rationale,evidence,provenance
                ) VALUES ($1,$2,'phase4c-task-mapping-v1',md5($3),$4,$5,'self_checked','ai_self_checked',
                  $6,$7,$8) RETURNING id
                """,
                run_id,
                task["task_id"],
                task["statement"],
                ambiguity_state,
                mapping_confidence,
                rationale,
                json.dumps([{"source": "onet_task_statement", "statement": task["statement"]}]),
                json.dumps(
                    {
                        "phase": "4C",
                        "scoreBlind": True,
                        "validationOccupationId": task["validation_occupation_id"],
                        "selectionRank": selection_ranks[task["task_id"]],
                        "promptVersion": "phase4c-prompt-v1",
                    }
                ),
            )
            if ambiguity_state == "none":
                for requirement in capability_payload(task["statement"]):
                    await connection.execute(
                        """
                        INSERT INTO ai_generated_task_capability_requirements (
                          ai_task_mapping_id,capability_definition_id,weight,required_capability_level,
                          confidence,rationale,evidence,provenance
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                        """,
                        mapping_id,
                        capability_ids[requirement["slug"]],
                        requirement["weight"],
                        requirement["level"],
                        requirement["confidence"],
                        f"Explicit task-local terms support {requirement['slug']}; weight is normalized across supported dimensions.",
                        json.dumps([{"matchedTerms": requirement["matches"], "source": "onet_task_statement"}]),
                        json.dumps({"mapperVersion": "phase4c-v1", "inferenceBeyondTaskText": False}),
                    )
                for constraint in constraint_payload(task["statement"]):
                    await connection.execute(
                        """
                        INSERT INTO ai_generated_task_environment_constraints (
                          ai_task_mapping_id,constraint_definition_id,constraint_level,confidence,
                          rationale,evidence,provenance
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7)
                        """,
                        mapping_id,
                        constraint_ids[constraint["slug"]],
                        constraint["level"],
                        constraint["confidence"],
                        f"Explicit task-local terms support {constraint['slug']}; absent constraints are not imputed.",
                        json.dumps([{"matchedTerms": constraint["matches"], "source": "onet_task_statement"}]),
                        json.dumps({"mapperVersion": "phase4c-v1", "inferenceBeyondTaskText": False}),
                    )
            event_id = await connection.fetchval(
                "SELECT validate_ai_generated_task_mapping($1,$2,$3,$4,$5,$6)",
                mapping_id,
                policy["id"],
                "phase4c-mapping-validator-v1",
                "JobsVsAI deterministic MVP validator",
                "v1",
                "system:phase4c-targeted-mapper",
            )
            scoring_eligible = await connection.fetchval(
                "SELECT scoring_eligible FROM ai_task_mapping_validation_events WHERE id=$1", event_id
            )
            generated[task["task_id"]] = {
                "mappingId": mapping_id,
                "eligible": scoring_eligible,
                "ambiguityState": ambiguity_state,
            }

        reused_count = 0
        generated_count = 0
        insufficient_count = 0
        after_gate_count = 0
        for task in tasks:
            source_weight = (
                float(task["importance_score"] * task["frequency_score"])
                if task["weighting_eligible"]
                else None
            )
            mapping_id = None
            mapping_run_id = None
            rank = selection_ranks.get(task["task_id"])
            if task["cohort_role"] == "retained_phase4a":
                mapping = retained_mappings.get(task["task_id"])
                if mapping is None:
                    raise ValueError(f"Retained task {task['task_id']} has no Phase 4A mapping")
                decision = "reused"
                mapping_id = mapping["id"]
                mapping_run_id = mapping["mapping_run_id"]
                reason = "Existing Phase 4A mapping row reused by reference without regeneration."
                reused_count += 1
            elif not task["weighting_eligible"]:
                decision = "source_weight_ineligible"
                reason = "Source task lacks legitimate weighting evidence; no mapping was generated."
            elif task["task_id"] in generated:
                mapping = generated[task["task_id"]]
                mapping_id = mapping["mappingId"]
                mapping_run_id = run_id
                if mapping["eligible"]:
                    decision = "generated"
                    reason = "Minimum-scope task selected by descending source weight and passed structural validation."
                    generated_count += 1
                else:
                    decision = "unmapped_insufficient_evidence"
                    reason = "Task was selected for coverage but failed structural evidence policy; no requirements were invented."
                    insufficient_count += 1
            else:
                decision = "unmapped_after_gate"
                reason = "No mapping generated after this occupation reached the unchanged 70% weighted-coverage gate."
                after_gate_count += 1
            evidence = [
                {
                    "source": "onet_task_weighting_and_statement",
                    "sourceWeight": source_weight,
                    "selectionRank": rank,
                    "projectedOccupationCoverage": projected_coverage.get(task["validation_occupation_id"]),
                }
            ]
            exact = {
                "cohortVersion": cohort_version,
                "onetTaskId": task["task_id"],
                "scopeDecision": decision,
                "mappingId": mapping_id,
                "mappingRunId": mapping_run_id,
                "sourceWeight": source_weight,
                "selectionRank": rank,
            }
            await connection.execute(
                """
                INSERT INTO phase4c_task_mapping_scope (
                  cohort_id,validation_occupation_id,onet_task_id,scope_decision,ai_task_mapping_id,
                  mapping_run_id,source_weight,selection_rank,selection_reason,evidence,input_hash,
                  source_id,provenance,created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
                  'system:phase4c-targeted-mapper')
                """,
                cohort["id"],
                task["validation_occupation_id"],
                task["task_id"],
                decision,
                mapping_id,
                mapping_run_id,
                source_weight,
                rank,
                reason,
                json.dumps(evidence),
                canonical_hash(exact),
                source_id,
                json.dumps(
                    {
                        "phase": "4C",
                        "minimumMappingScope": True,
                        "missingEvidenceInvented": False,
                    }
                ),
            )
        await connection.execute(
            "UPDATE phase4c_validation_cohorts SET new_mapping_run_id=$1,status='mapped' WHERE id=$2",
            run_id,
            cohort["id"],
        )
        await transaction.commit()
        return {
            "mappingRunId": run_id,
            "runVersion": run_version,
            "sourceTasks": len(tasks),
            "reusedMappingRows": reused_count,
            "newMappingRows": len(selected_task_ids),
            "newEligibleMappings": generated_count,
            "newInsufficientMappings": insufficient_count,
            "unmappedAfterGate": after_gate_count,
            "externalModelCalls": 0,
            "addedProjectedCoverage": {
                str(occupation_id): round(value, 4)
                for occupation_id, value in projected_coverage.items()
            },
            "reused": False,
        }
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-version", default="phase4c-targeted-mapper-v1-2026q3")
    parser.add_argument("--cohort-version", default="phase4c-2026q3-v1")
    args = parser.parse_args()
    print(json.dumps(await generate(args.run_version, args.cohort_version), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
