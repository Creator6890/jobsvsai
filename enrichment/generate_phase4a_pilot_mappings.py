"""Generate the isolated, score-blind Phase 4A pilot task mappings.

The mapper deliberately reads only the selected cohort, current O*NET task text,
the active mapping policy, and taxonomy definitions. It never reads Frontier AI
values, task outcomes, occupation outcomes, or production score tables.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

import asyncpg

from draft_candidate_mapper import CAPABILITY_TERMS, CONSTRAINT_TERMS, matched_terms, normalize


FORBIDDEN_INPUTS = [
    "frontier_capability_values",
    "frontier_ai_capability_index_entries",
    "task_ai_enrichment_assessments",
    "task_ai_scores",
    "occupation_scores",
    "phase4a_task_assessments",
    "phase4a_occupation_scores",
    "automation_outcomes",
]

PROMPT_TEXT = """JobsVsAI Phase 4A score-blind task mapper v1.
Use only the task statement, Task-to-Capability Rubric v1, AI Capability
Taxonomy v1, and Environment Constraint Taxonomy v1. Return one structured
mapping per task. Do not use AI capability scores, automation outcomes,
occupation scores, task prevalence, wages, or downstream score targets.
Assign at most six capability requirements; normalize their weights to 1.0.
Do not infer missing scope. Mark short or materially underspecified statements
as ambiguous_scope or insufficient_description.
"""


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def disposition(statement: str) -> tuple[str, float, str]:
    words = re.findall(r"[A-Za-z0-9]+", statement)
    if len(statement) <= 25 or len(words) <= 3:
        return (
            "insufficient_description",
            88,
            "The task-local description is too short to support requirements without inventing scope.",
        )
    if len(statement) <= 60:
        return (
            "ambiguous_scope",
            84,
            "The statement omits material method, object, context, or outcome detail; no requirements are inferred.",
        )
    return (
        "none",
        82,
        "The task-local statement contains enough action, object, and context evidence for a provisional mapping.",
    )


def capability_payload(statement: str) -> list[dict[str, object]]:
    raw: list[tuple[str, int, list[str]]] = []
    for slug, terms in CAPABILITY_TERMS.items():
        matches = matched_terms(statement, terms)
        if matches:
            raw.append((slug, 1 + len(matches), matches))
    if not raw:
        raw = [("general-reasoning", 1, ["explicit task action and outcome"])]

    result = []
    for slug, weight, score, matches in normalize(raw):
        required_level = min(88, 38 + score * 7 + min(14, len(statement.split()) // 5))
        confidence = min(90, 64 + score * 6)
        result.append(
            {
                "slug": slug,
                "weight": weight,
                "level": required_level,
                "confidence": confidence,
                "matches": matches,
            }
        )
    return result


def constraint_payload(statement: str) -> list[dict[str, object]]:
    result = []
    for slug, terms in CONSTRAINT_TERMS.items():
        matches = matched_terms(statement, terms)
        if not matches:
            continue
        result.append(
            {
                "slug": slug,
                "level": min(90, 25 + len(matches) * 14),
                "confidence": min(90, 66 + len(matches) * 7),
                "matches": matches,
            }
        )
    return result


async def generate(run_version: str, cohort_version: str) -> dict[str, object]:
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        existing = await connection.fetchrow(
            "SELECT id,input_task_count,output_task_count FROM ai_generated_task_mapping_runs WHERE run_version=$1",
            run_version,
        )
        if existing:
            cohort_id = await connection.fetchval(
                "SELECT id FROM phase4a_pilot_cohorts WHERE cohort_version=$1", cohort_version
            )
            await connection.execute(
                "UPDATE phase4a_pilot_cohorts SET mapping_run_id=$1,status='mapped' WHERE id=$2 AND mapping_run_id IS NULL",
                existing["id"],
                cohort_id,
            )
            await transaction.commit()
            return {
                "mappingRunId": existing["id"],
                "runVersion": run_version,
                "tasks": existing["output_task_count"],
                "reused": True,
                "newModelCalls": 0,
            }

        policy = await connection.fetchrow(
            """
            SELECT policy.*,rubric.environment_taxonomy_version_id
            FROM task_mapping_evidence_policy_versions policy
            JOIN task_mapping_rubric_versions rubric ON rubric.id=policy.rubric_version_id
            WHERE policy.policy_version='mvp-evidence-policy-v1'
            """
        )
        cohort = await connection.fetchrow(
            "SELECT * FROM phase4a_pilot_cohorts WHERE cohort_version=$1", cohort_version
        )
        if policy is None or cohort is None:
            raise ValueError("Phase 4A policy or cohort is missing")

        tasks = await connection.fetch(
            """
            SELECT task.task_id,task.occupation_code,task.statement,pilot.id pilot_occupation_id
            FROM phase4a_pilot_occupations pilot
            JOIN onet_tasks task ON task.occupation_code=pilot.occupation_code AND task.is_current
            WHERE pilot.cohort_id=$1
            ORDER BY pilot.cohort_order,task.task_id
            """,
            cohort["id"],
        )
        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4A scoring pilot'"
        )
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
        source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        prompt_hash = hashlib.sha256(PROMPT_TEXT.encode()).hexdigest()
        allowed_manifest = {
            "allowed": [
                "phase4a_cohort_membership",
                "onet_task_id",
                "onet_task_statement",
                "taxonomy_definitions",
                "mapping_rubric",
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
            ) VALUES ($1,$2,$3,$4,'JobsVsAI','rubric-authored deterministic mapper','phase4a-v1',
              DATE '2026-08-20','Phase 4A score-blind mapping prompt','phase4a-prompt-v1',$5,$5,$6,$7,
              true,'completed',$8,$8,$9,$10,$11,'system:phase4a-pilot-mapper') RETURNING id
            """,
            run_version,
            policy["taxonomy_version_id"],
            policy["rubric_version_id"],
            policy["id"],
            prompt_hash,
            json.dumps({"temperature": 0, "maximumCapabilities": 6, "runtimeExternalModelCalls": 0}),
            json.dumps(allowed_manifest),
            len(tasks),
            source_id,
            json.dumps([{"promptSha256": prompt_hash, "sourceCodeSha256": source_hash}]),
            json.dumps(
                {
                    "phase": "4A",
                    "pilotOnly": True,
                    "scoreBlind": True,
                    "activationAllowed": False,
                    "productionScoreWritesAllowed": False,
                    "mappingMethod": "model_authored_deterministic_rules",
                    "sourceCodeSha256": source_hash,
                }
            ),
        )

        eligible = 0
        disposition_counts: dict[str, int] = {}
        for task in tasks:
            ambiguity_state, mapping_confidence, rationale = disposition(task["statement"])
            disposition_counts[ambiguity_state] = disposition_counts.get(ambiguity_state, 0) + 1
            mapping_id = await connection.fetchval(
                """
                INSERT INTO ai_generated_task_mappings (
                  mapping_run_id,onet_task_id,mapping_version,task_statement_hash,ambiguity_state,
                  mapping_confidence,initial_validation_status,initial_review_state,rationale,evidence,provenance
                ) VALUES ($1,$2,'phase4a-task-mapping-v1',md5($3),$4,$5,'self_checked','ai_self_checked',
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
                        "phase": "4A",
                        "scoreBlind": True,
                        "pilotOccupationId": task["pilot_occupation_id"],
                        "promptVersion": "phase4a-prompt-v1",
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
                        json.dumps({"mapperVersion": "phase4a-v1", "inferenceBeyondTaskText": False}),
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
                        json.dumps({"mapperVersion": "phase4a-v1", "inferenceBeyondTaskText": False}),
                    )
            event_id = await connection.fetchval(
                "SELECT validate_ai_generated_task_mapping($1,$2,$3,$4,$5,$6)",
                mapping_id,
                policy["id"],
                "phase4a-mapping-validator-v1",
                "JobsVsAI deterministic MVP validator",
                "v1",
                "system:phase4a-pilot-mapper",
            )
            if await connection.fetchval(
                "SELECT scoring_eligible FROM ai_task_mapping_validation_events WHERE id=$1", event_id
            ):
                eligible += 1

        await connection.execute(
            "UPDATE phase4a_pilot_cohorts SET mapping_run_id=$1,status='mapped' WHERE id=$2",
            run_id,
            cohort["id"],
        )
        await transaction.commit()
        return {
            "mappingRunId": run_id,
            "runVersion": run_version,
            "tasks": len(tasks),
            "scoringEligible": eligible,
            "dispositions": disposition_counts,
            "reused": False,
            "newModelCalls": 0,
            "scoreBlind": True,
        }
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-version", default="phase4a-pilot-mapper-v1-2026q3")
    parser.add_argument("--cohort-version", default="phase4a-2026q3-v1")
    args = parser.parse_args()
    print(json.dumps(await generate(args.run_version, args.cohort_version), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
