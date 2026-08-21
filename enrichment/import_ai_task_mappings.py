"""Import structured AI task mappings into the provisional, non-activated layer."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import asyncpg


def database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai").replace(
        "postgresql+asyncpg://", "postgresql://", 1,
    )


async def main() -> None:
    arguments = argparse.ArgumentParser(description="Import and deterministically validate structured AI mappings.")
    arguments.add_argument("input", type=Path)
    arguments.add_argument("--policy-version", default="mvp-evidence-policy-v1")
    arguments.add_argument("--validation-version", default="mvp-structural-validator-v1")
    args = arguments.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        policy = await connection.fetchrow("""
          SELECT policy.*,rubric.environment_taxonomy_version_id
          FROM task_mapping_evidence_policy_versions policy
          JOIN task_mapping_rubric_versions rubric ON rubric.id=policy.rubric_version_id
          WHERE policy.policy_version=$1
        """, args.policy_version)
        if policy is None:
            raise ValueError(f"Unknown evidence policy {args.policy_version}")
        prompt = payload["prompt"]
        model = payload["model"]
        source_id = policy["source_id"]
        mappings = payload["mappings"]
        run_id = await connection.fetchval("""
          INSERT INTO ai_generated_task_mapping_runs (
            run_version,taxonomy_version_id,rubric_version_id,evidence_policy_version_id,
            provider_name,model_name,model_version,model_snapshot_date,prompt_name,prompt_version,
            prompt_sha256,system_prompt_sha256,inference_configuration,allowed_input_manifest,
            prohibited_input_attestation,status,input_task_count,output_task_count,source_id,
            evidence,provenance,created_by
          ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,true,'completed',$15,$15,$16,$17,$18,$19)
          RETURNING id
        """, payload["runVersion"], policy["taxonomy_version_id"], policy["rubric_version_id"], policy["id"],
            model["provider"], model["name"], model["version"], model.get("snapshotDate"),
            prompt["name"], prompt["version"], prompt["sha256"], prompt.get("systemPromptSha256"),
            json.dumps(payload.get("inferenceConfiguration", {})),
            json.dumps(payload.get("allowedInputManifest", {
                "allowed": ["onet_task_statement", "taxonomy_definitions", "mapping_rubric"],
                "prohibited": ["frontier_capability_values", "automation_outcomes", "occupation_scores"],
            })), len(mappings), source_id, json.dumps(payload.get("evidence", [])),
            json.dumps({"mvp_provisional": True, "activation_allowed": False, **payload.get("provenance", {})}),
            payload.get("createdBy", "system:ai-mapping-importer"))
        capability_ids = {
            row["slug"]: row["id"] for row in await connection.fetch(
                "SELECT id,slug FROM ai_capability_definitions WHERE taxonomy_version_id=$1", policy["taxonomy_version_id"],
            )
        }
        constraint_ids = {
            row["slug"]: row["id"] for row in await connection.fetch(
                "SELECT id,slug FROM task_environment_constraint_definitions WHERE environment_taxonomy_version_id=$1",
                policy["environment_taxonomy_version_id"],
            )
        }
        eligibility = []
        for mapping in mappings:
            statement_hash = await connection.fetchval(
                "SELECT md5(statement) FROM onet_tasks WHERE task_id=$1", mapping["onetTaskId"],
            )
            if statement_hash is None:
                raise ValueError(f"Unknown O*NET task {mapping['onetTaskId']}")
            mapping_id = await connection.fetchval("""
              INSERT INTO ai_generated_task_mappings (
                mapping_run_id,onet_task_id,mapping_version,task_statement_hash,ambiguity_state,
                mapping_confidence,initial_validation_status,initial_review_state,rationale,evidence,provenance
              ) VALUES ($1,$2,$3,$4,$5,$6,'self_checked',$7,$8,$9,$10) RETURNING id
            """, run_id, mapping["onetTaskId"], mapping["mappingVersion"], statement_hash,
                mapping["ambiguityState"], mapping["confidence"], mapping.get("reviewState", "ai_self_checked"),
                mapping["rationale"], json.dumps(mapping.get("evidence", [])),
                json.dumps({"structured_ai_mapping": True, **mapping.get("provenance", {})}))
            for requirement in mapping.get("capabilities", []):
                await connection.execute("""
                  INSERT INTO ai_generated_task_capability_requirements (
                    ai_task_mapping_id,capability_definition_id,weight,required_capability_level,
                    confidence,rationale,evidence,provenance
                  ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                """, mapping_id, capability_ids[requirement["slug"]], requirement["weight"],
                    requirement["requiredLevel"], requirement["confidence"], requirement["rationale"],
                    json.dumps(requirement.get("evidence", [])), json.dumps(requirement.get("provenance", {})))
            for constraint in mapping.get("constraints", []):
                await connection.execute("""
                  INSERT INTO ai_generated_task_environment_constraints (
                    ai_task_mapping_id,constraint_definition_id,constraint_level,confidence,
                    rationale,evidence,provenance
                  ) VALUES ($1,$2,$3,$4,$5,$6,$7)
                """, mapping_id, constraint_ids[constraint["slug"]], constraint["level"],
                    constraint["confidence"], constraint["rationale"],
                    json.dumps(constraint.get("evidence", [])), json.dumps(constraint.get("provenance", {})))
            event_id = await connection.fetchval(
                "SELECT validate_ai_generated_task_mapping($1,$2,$3,$4,$5,$6)",
                mapping_id, policy["id"], args.validation_version,
                "JobsVsAI deterministic MVP validator", "v1", payload.get("createdBy", "system:ai-mapping-importer"),
            )
            event = await connection.fetchrow(
                "SELECT validation_status,review_state,scoring_eligible,failure_reasons FROM ai_task_mapping_validation_events WHERE id=$1",
                event_id,
            )
            eligibility.append({"onetTaskId": mapping["onetTaskId"], **dict(event)})
        await transaction.commit()
        print(json.dumps({"mappingRunId": run_id, "runVersion": payload["runVersion"], "mappings": eligibility}, default=str, indent=2))
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
