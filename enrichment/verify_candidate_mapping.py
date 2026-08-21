"""Independent structural verification for draft task mapper output."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

import asyncpg


def database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai").replace(
        "postgresql+asyncpg://", "postgresql://", 1,
    )


async def main() -> None:
    arguments = argparse.ArgumentParser()
    arguments.add_argument("candidate_run_id", type=int)
    arguments.add_argument("--verification-version", default="independent-structure-v1")
    args = arguments.parse_args()
    source_text = Path(__file__).read_text(encoding="utf-8")
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        run = await connection.fetchrow("SELECT * FROM task_mapping_candidate_runs WHERE id=$1", args.candidate_run_id)
        if run is None:
            raise ValueError(f"Unknown candidate run {args.candidate_run_id}")
        items = await connection.fetch("""
          SELECT candidate.*,input.task_statement_hash current_statement_hash,
            (SELECT count(*) FROM candidate_task_capability_requirements requirement WHERE requirement.candidate_task_mapping_id=candidate.id) requirement_count,
            (SELECT count(*) FROM candidate_task_environment_constraints constraint_mapping WHERE constraint_mapping.candidate_task_mapping_id=candidate.id) constraint_count
          FROM candidate_task_mappings candidate
          JOIN task_mapping_blind_inputs input ON input.onet_task_id=candidate.onet_task_id
          WHERE candidate.candidate_run_id=$1 ORDER BY candidate.onet_task_id
        """, args.candidate_run_id)
        findings: list[dict[str, object]] = []
        for item in items:
            savepoint = connection.transaction()
            await savepoint.start()
            try:
                await connection.fetchval("SELECT validate_candidate_mapping($1)", item["id"])
                await savepoint.commit()
            except asyncpg.PostgresError as error:
                await savepoint.rollback()
                findings.append({"item": item["id"], "severity": "error", "code": "rubric_structure", "message": str(error)})
            if item["task_statement_hash"] != item["current_statement_hash"]:
                findings.append({"item": item["id"], "severity": "error", "code": "task_hash_mismatch", "message": "Task text changed after mapping."})
            if item["disposition"] != "mappable" and (item["requirement_count"] or item["constraint_count"]):
                findings.append({"item": item["id"], "severity": "error", "code": "false_inference", "message": "Non-mappable task has inferred mapping rows."})
        manifest = run["allowed_input_manifest"]
        if isinstance(manifest, str):
            manifest = json.loads(manifest)
        prohibited = set(manifest.get("prohibited", []))
        if not run["prohibited_input_attestation"] or not prohibited:
            findings.append({"item": None, "severity": "error", "code": "blindness_attestation", "message": "Score-blind input attestation is incomplete."})
        if len(items) != run["output_task_count"] or run["input_task_count"] != run["output_task_count"]:
            findings.append({"item": None, "severity": "error", "code": "run_reconciliation", "message": "Candidate run task counts do not reconcile."})
        errors = sum(finding["severity"] == "error" for finding in findings)
        summary = {
            "tasksChecked": len(items), "errors": errors,
            "warnings": sum(finding["severity"] == "warning" for finding in findings),
            "falseInferenceFindings": sum(finding["code"] == "false_inference" for finding in findings),
            "taskHashesReconciled": not any(finding["code"] == "task_hash_mismatch" for finding in findings),
            "scoreBlindAttestationPresent": bool(run["prohibited_input_attestation"]),
        }
        source_id = await connection.fetchval("SELECT id FROM data_sources WHERE name='JobsVsAI Draft Task Mapper'")
        verification_id = await connection.fetchval("""
          INSERT INTO task_mapping_verification_runs (
            candidate_run_id,verification_version,verifier_name,verifier_version,status,
            independent_implementation_attestation,allowed_input_manifest,checks_performed,summary,
            source_code_sha256,source_id,provenance,created_by
          ) VALUES ($1,$2,'JobsVsAI independent structural verifier','independent-structure-v1',$3,true,$4,$5,$6,$7,$8,$9,'system:independent-verifier') RETURNING id
        """, args.candidate_run_id, args.verification_version, "passed" if errors == 0 else "failed",
            json.dumps({"candidate_outputs": True, "rubric": True, "task_statement_hash": True, "score_tables": False}),
            json.dumps(["rubric_structure", "normalization", "taxonomy_version", "task_hash", "false_inference", "run_reconciliation", "blindness_attestation"]),
            json.dumps(summary), hashlib.sha256(source_text.encode()).hexdigest(), source_id,
            json.dumps({"independent_from_mapper_rules": True, "activation_allowed": False}))
        for finding in findings:
            await connection.execute("""
              INSERT INTO task_mapping_verification_findings (
                verification_run_id,candidate_task_mapping_id,severity,finding_code,message,evidence
              ) VALUES ($1,$2,$3,$4,$5,'[]')
            """, verification_id, finding["item"], finding["severity"], finding["code"], finding["message"])
        await transaction.commit()
        print(json.dumps({"verificationRunId": verification_id, "status": "passed" if errors == 0 else "failed", **summary}))
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
