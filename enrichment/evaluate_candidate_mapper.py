"""Aggregate candidate-mapper evaluation against a versioned gold dataset."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from statistics import mean

import asyncpg


def database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai").replace(
        "postgresql+asyncpg://", "postgresql://", 1,
    )


def average(values: list[float]) -> float:
    return round(mean(values), 7) if values else 0.0


async def main() -> None:
    arguments = argparse.ArgumentParser()
    arguments.add_argument("candidate_run_id", type=int)
    arguments.add_argument("--gold-version", default="gold-v1-representative-test")
    arguments.add_argument("--gate-version", default="mapper-acceptance-gates-v1")
    arguments.add_argument("--evaluation-version", default="evaluation-v1-run1-controls")
    args = arguments.parse_args()

    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        gold = await connection.fetchrow(
            "SELECT * FROM task_capability_gold_datasets WHERE dataset_version=$1", args.gold_version,
        )
        gate = await connection.fetchrow(
            "SELECT * FROM mapper_acceptance_gate_configs WHERE gate_version=$1", args.gate_version,
        )
        candidate_run = await connection.fetchrow("SELECT * FROM task_mapping_candidate_runs WHERE id=$1", args.candidate_run_id)
        if gold is None or gate is None or candidate_run is None:
            raise ValueError("Unknown candidate run, gold dataset, or gate configuration")
        gold_items = await connection.fetch("""
          SELECT item.*,task.occupation_code
          FROM task_capability_gold_items item JOIN onet_tasks task ON task.task_id=item.onet_task_id
          WHERE item.gold_dataset_id=$1 ORDER BY item.onet_task_id
        """, gold["id"])
        candidates = {
            row["onet_task_id"]: row for row in await connection.fetch(
                "SELECT * FROM candidate_task_mappings WHERE candidate_run_id=$1", args.candidate_run_id,
            )
        }
        set_agreements: list[float] = []
        weight_deviations: list[float] = []
        requirement_deviations: list[float] = []
        constraint_deviations: list[float] = []
        confidence_agreements: list[float] = []
        disposition_matches = 0
        false_inferences = 0
        extra_dimensions = 0
        missing_dimensions = 0
        total_gold_dimensions = 0
        total_candidate_dimensions = 0
        evaluated = 0
        occupation_codes: set[str] = set()

        for item in gold_items:
            candidate = candidates.get(item["onet_task_id"])
            if candidate is None:
                continue
            evaluated += 1
            occupation_codes.add(item["occupation_code"])
            if candidate["disposition"] == item["disposition"]:
                disposition_matches += 1
            candidate_requirements = {
                row["capability_definition_id"]: row for row in await connection.fetch(
                    "SELECT * FROM candidate_task_capability_requirements WHERE candidate_task_mapping_id=$1", candidate["id"],
                )
            }
            candidate_constraints = {
                row["constraint_definition_id"]: row for row in await connection.fetch(
                    "SELECT * FROM candidate_task_environment_constraints WHERE candidate_task_mapping_id=$1", candidate["id"],
                )
            }
            gold_requirements = {
                row["capability_definition_id"]: row for row in await connection.fetch(
                    "SELECT * FROM gold_task_capability_requirements WHERE gold_item_id=$1", item["id"],
                )
            }
            gold_constraints = {
                row["constraint_definition_id"]: row for row in await connection.fetch(
                    "SELECT * FROM gold_task_environment_constraints WHERE gold_item_id=$1", item["id"],
                )
            }
            if item["disposition"] != "mappable":
                if candidate["disposition"] == "mappable" or candidate_requirements or candidate_constraints:
                    false_inferences += 1
                continue

            candidate_set = set(candidate_requirements)
            gold_set = set(gold_requirements)
            union = candidate_set | gold_set
            set_agreements.append(len(candidate_set & gold_set) / len(union) if union else 1.0)
            extra_dimensions += len(candidate_set - gold_set)
            missing_dimensions += len(gold_set - candidate_set)
            total_candidate_dimensions += len(candidate_set)
            total_gold_dimensions += len(gold_set)
            for dimension in union:
                candidate_row = candidate_requirements.get(dimension)
                gold_row = gold_requirements.get(dimension)
                weight_deviations.append(abs(float(candidate_row["weight"] if candidate_row else 0) - float(gold_row["weight"] if gold_row else 0)))
                requirement_deviations.append(abs(float(candidate_row["required_capability_level"] if candidate_row else 0) - float(gold_row["required_capability_level"] if gold_row else 0)))
                confidence_agreements.append(
                    max(0, 1 - abs(float(candidate_row["confidence"]) - float(gold_row["confidence"])) / 100)
                    if candidate_row and gold_row else 0
                )
            for dimension in set(candidate_constraints) | set(gold_constraints):
                candidate_row = candidate_constraints.get(dimension)
                gold_row = gold_constraints.get(dimension)
                constraint_deviations.append(abs(float(candidate_row["constraint_level"] if candidate_row else 0) - float(gold_row["constraint_level"] if gold_row else 0)))
                confidence_agreements.append(
                    max(0, 1 - abs(float(candidate_row["confidence"]) - float(gold_row["confidence"])) / 100)
                    if candidate_row and gold_row else 0
                )

        non_mappable = sum(item["disposition"] != "mappable" for item in gold_items if item["onet_task_id"] in candidates)
        human_reviewed = await connection.fetchval("""
          SELECT count(DISTINCT item.id)
          FROM task_capability_gold_items item
          WHERE item.gold_dataset_id=$1 AND (
            SELECT count(DISTINCT review.reviewer_identifier)
            FROM task_mapping_gold_review_events review
            WHERE review.gold_item_id=item.id AND review.reviewer_kind='human'
              AND review.decision IN ('submitted','approved')
          )>=2
        """, gold["id"])
        verification = await connection.fetchrow("""
          SELECT * FROM task_mapping_verification_runs
          WHERE candidate_run_id=$1 ORDER BY created_at DESC,id DESC LIMIT 1
        """, args.candidate_run_id)
        metrics = {
            "capabilitySetAgreement": average(set_agreements),
            "meanWeightDeviation": average(weight_deviations),
            "meanRequirementLevelDeviation": average(requirement_deviations),
            "meanConstraintDeviation": average(constraint_deviations),
            "confidenceAgreement": average(confidence_agreements),
            "extraDimensions": extra_dimensions,
            "missingDimensions": missing_dimensions,
            "extraDimensionRate": round(extra_dimensions / max(1, total_candidate_dimensions), 7),
            "missingDimensionRate": round(missing_dimensions / max(1, total_gold_dimensions), 7),
            "falseInferenceCount": false_inferences,
            "falseInferenceRate": round(false_inferences / max(1, non_mappable), 7),
            "dispositionAgreement": round(disposition_matches / max(1, evaluated), 7),
        }
        gate_results = {
            "minimumHumanReviewedTasks": human_reviewed >= gate["minimum_human_reviewed_tasks"],
            "minimumOccupations": len(occupation_codes) >= gate["minimum_occupations"],
            "capabilitySetAgreement": metrics["capabilitySetAgreement"] >= float(gate["minimum_capability_set_agreement"]),
            "weightDeviation": metrics["meanWeightDeviation"] <= float(gate["maximum_mean_weight_deviation"]),
            "requirementLevelDeviation": metrics["meanRequirementLevelDeviation"] <= float(gate["maximum_mean_requirement_level_deviation"]),
            "constraintDeviation": metrics["meanConstraintDeviation"] <= float(gate["maximum_mean_constraint_deviation"]),
            "confidenceAgreement": metrics["confidenceAgreement"] >= float(gate["minimum_confidence_agreement"]),
            "extraDimensions": metrics["extraDimensionRate"] <= float(gate["maximum_extra_dimension_rate"]),
            "missingDimensions": metrics["missingDimensionRate"] <= float(gate["maximum_missing_dimension_rate"]),
            "falseInference": metrics["falseInferenceRate"] <= float(gate["maximum_false_inference_rate"]),
            "independentVerification": bool(verification and verification["status"] == "passed" and verification["independent_implementation_attestation"]),
        }
        eligible = gate_results["minimumHumanReviewedTasks"] and gate_results["minimumOccupations"]
        status = "passed" if eligible and all(gate_results.values()) else "failed" if eligible else "ineligible"
        source_id = await connection.fetchval("SELECT id FROM data_sources WHERE name='JobsVsAI Draft Task Mapper'")
        evaluation_id = await connection.fetchval("""
          INSERT INTO task_mapper_evaluation_runs (
            evaluation_version,candidate_run_id,gold_dataset_id,gate_config_id,verification_run_id,
            status,evaluated_task_count,human_reviewed_task_count,occupation_count,metrics,gate_results,
            source_id,provenance,created_by
          ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'system:mapper-evaluator') RETURNING id
        """, args.evaluation_version, args.candidate_run_id, gold["id"], gate["id"], verification["id"] if verification else None,
            status, evaluated, human_reviewed, len(occupation_codes), json.dumps(metrics), json.dumps(gate_results), source_id,
            json.dumps({"evaluation_method": "aggregate-gold-comparison-v1", "activation_allowed": False}))
        await transaction.commit()
        print(json.dumps({"evaluationRunId": evaluation_id, "status": status, "metrics": metrics, "gateResults": gate_results}, indent=2))
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
