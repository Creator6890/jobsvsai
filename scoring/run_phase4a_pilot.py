"""Persist an isolated Phase 4A initial, replay, or formula-only scoring run."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import defaultdict
from decimal import Decimal
from typing import Any

import asyncpg

from pilot import augmentation_potential, automation_feasibility, canonical_hash, capability_fit, rounded


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def dumps(value: Any) -> str:
    return json.dumps(plain(value), sort_keys=True, default=str)


def decoded(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


async def load_dependencies(
    connection: asyncpg.Connection,
    cohort_version: str,
    task_formula_versions: tuple[str, str, str] = (
        "task-capability-fit-v1",
        "automation-feasibility-v1",
        "augmentation-potential-v1",
    ),
    occupation_formula_version: str = "phase4a-occupation-score-v1",
) -> dict[str, Any]:
    cohort = await connection.fetchrow(
        "SELECT * FROM phase4a_pilot_cohorts WHERE cohort_version=$1", cohort_version
    )
    if cohort is None or cohort["mapping_run_id"] is None:
        raise ValueError("Pilot cohort has no completed mapping run")
    formulas = {}
    for row in await connection.fetch(
        "SELECT * FROM phase4a_task_formula_versions WHERE formula_version=ANY($1::text[])",
        list(task_formula_versions),
    ):
        formula = dict(row)
        formula["parameters"] = decoded(formula["parameters"])
        formulas[row["formula_type"]] = formula
    occupation_formula_row = await connection.fetchrow(
        "SELECT * FROM phase4a_occupation_formula_versions WHERE formula_version=$1",
        occupation_formula_version,
    )
    occupation_formula = dict(occupation_formula_row)
    occupation_formula["parameters"] = decoded(occupation_formula["parameters"])
    track = await connection.fetchrow(
        """
        SELECT track.*,version.index_version
        FROM frontier_ai_capability_index_tracks track
        JOIN frontier_ai_capability_index_versions version ON version.id=track.index_version_id
        WHERE track.track_code='commercially_deployable' AND version.index_version='frontier-ai-index-v1'
        """
    )
    frontier_rows = await connection.fetch(
        """
        SELECT definition.slug,entry.id entry_id,entry.capability_score,entry.confidence,
               entry.assessment_status,entry.assessment_date
        FROM frontier_ai_capability_index_entries entry
        JOIN ai_capability_definitions definition ON definition.id=entry.capability_definition_id
        WHERE entry.track_id=$1
        ORDER BY definition.slug
        """,
        track["id"],
    )
    evidence_rows = await connection.fetch(
        """
        SELECT evidence.id,definition.slug
        FROM frontier_ai_capability_evidence_records evidence
        JOIN ai_capability_definitions definition ON definition.id=evidence.capability_definition_id
        WHERE evidence.track_id=$1 ORDER BY evidence.id
        """,
        track["id"],
    )
    evidence_ids: dict[str, list[int]] = defaultdict(list)
    for row in evidence_rows:
        evidence_ids[row["slug"]].append(row["id"])
    frontier = {
        row["slug"]: {
            "entryId": row["entry_id"],
            "score": float(row["capability_score"]),
            "confidence": float(row["confidence"]),
            "assessmentStatus": row["assessment_status"],
            "assessmentDate": str(row["assessment_date"]),
            "evidenceIds": evidence_ids[row["slug"]],
        }
        for row in frontier_rows
    }
    if len(frontier) != 15 or any(not item["evidenceIds"] for item in frontier.values()):
        raise ValueError("Commercial Frontier track must reconcile to 15 evidenced capability values")

    occupations = [
        dict(row)
        for row in await connection.fetch(
            """
            SELECT pilot.*,occupation.title source_title
            FROM phase4a_pilot_occupations pilot
            JOIN onet_occupations occupation ON occupation.onet_soc_code=pilot.occupation_code
            WHERE pilot.cohort_id=$1 ORDER BY pilot.cohort_order
            """,
            cohort["id"],
        )
    ]
    task_rows = await connection.fetch(
        """
        WITH latest_validation AS (
          SELECT DISTINCT ON (event.ai_task_mapping_id) event.*
          FROM ai_task_mapping_validation_events event
          JOIN ai_generated_task_mappings mapping ON mapping.id=event.ai_task_mapping_id
          WHERE mapping.mapping_run_id=$1
          ORDER BY event.ai_task_mapping_id,event.created_at DESC,event.id DESC
        )
        SELECT task.*,pilot.id pilot_occupation_id,mapping.id mapping_id,mapping.mapping_confidence,
               mapping.ambiguity_state,validation.scoring_eligible
        FROM phase4a_pilot_occupations pilot
        JOIN onet_tasks task ON task.occupation_code=pilot.occupation_code AND task.is_current
        JOIN ai_generated_task_mappings mapping ON mapping.onet_task_id=task.task_id AND mapping.mapping_run_id=$1
        JOIN latest_validation validation ON validation.ai_task_mapping_id=mapping.id
        WHERE pilot.cohort_id=$2
        ORDER BY pilot.cohort_order,task.task_id
        """,
        cohort["mapping_run_id"],
        cohort["id"],
    )
    requirement_rows = await connection.fetch(
        """
        SELECT requirement.ai_task_mapping_id,definition.slug,definition.name,requirement.weight,
               requirement.required_capability_level,requirement.confidence,requirement.rationale,
               requirement.evidence,requirement.provenance
        FROM ai_generated_task_capability_requirements requirement
        JOIN ai_capability_definitions definition ON definition.id=requirement.capability_definition_id
        JOIN ai_generated_task_mappings mapping ON mapping.id=requirement.ai_task_mapping_id
        WHERE mapping.mapping_run_id=$1 ORDER BY requirement.ai_task_mapping_id,definition.slug
        """,
        cohort["mapping_run_id"],
    )
    constraint_rows = await connection.fetch(
        """
        SELECT mapped_constraint.ai_task_mapping_id,definition.slug,definition.name,mapped_constraint.constraint_level,
               mapped_constraint.confidence,mapped_constraint.rationale,mapped_constraint.evidence,mapped_constraint.provenance
        FROM ai_generated_task_environment_constraints mapped_constraint
        JOIN task_environment_constraint_definitions definition ON definition.id=mapped_constraint.constraint_definition_id
        JOIN ai_generated_task_mappings mapping ON mapping.id=mapped_constraint.ai_task_mapping_id
        WHERE mapping.mapping_run_id=$1 ORDER BY mapped_constraint.ai_task_mapping_id,definition.slug
        """,
        cohort["mapping_run_id"],
    )
    requirements: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in requirement_rows:
        requirements[row["ai_task_mapping_id"]].append(
            {
                "slug": row["slug"],
                "name": row["name"],
                "weight": float(row["weight"]),
                "requiredLevel": float(row["required_capability_level"]),
                "mappingConfidence": float(row["confidence"]),
                "rationale": row["rationale"],
                "evidence": decoded(row["evidence"]),
            }
        )
    constraints: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in constraint_rows:
        constraints[row["ai_task_mapping_id"]].append(
            {
                "slug": row["slug"],
                "name": row["name"],
                "level": float(row["constraint_level"]),
                "confidence": float(row["confidence"]),
                "rationale": row["rationale"],
                "evidence": decoded(row["evidence"]),
            }
        )
    return {
        "cohort": dict(cohort),
        "formulas": formulas,
        "occupationFormula": occupation_formula,
        "track": dict(track),
        "frontier": frontier,
        "occupations": occupations,
        "tasks": [dict(row) for row in task_rows],
        "requirements": requirements,
        "constraints": constraints,
    }


def calculate(dependencies: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    formulas = dependencies["formulas"]
    occupation_parameters = dependencies["occupationFormula"]["parameters"]
    task_exposure_weights = occupation_parameters["taskExposureWeights"]
    task_results = []
    tasks_by_occupation: dict[int, list[dict[str, Any]]] = defaultdict(list)
    source_tasks_by_occupation: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for task in dependencies["tasks"]:
        source_tasks_by_occupation[task["pilot_occupation_id"]].append(task)
        if not task["scoring_eligible"]:
            continue
        requirements = dependencies["requirements"][task["mapping_id"]]
        constraints = dependencies["constraints"][task["mapping_id"]]
        fit = capability_fit(requirements, dependencies["frontier"], formulas["capability_fit"]["parameters"])
        automation = automation_feasibility(
            fit["score"], constraints, formulas["automation_feasibility"]["parameters"]
        )
        augmentation = augmentation_potential(
            fit["score"], automation["score"], formulas["augmentation_potential"]["parameters"]
        )
        task_exposure = rounded(
            float(task_exposure_weights["aiCapabilityFit"]) * fit["score"]
            + float(task_exposure_weights["automationFeasibility"]) * automation["score"]
            + float(task_exposure_weights["augmentationPotential"]) * augmentation["score"]
        )
        frontier_confidence = sum(
            float(item["weight"]) * float(dependencies["frontier"][item["slug"]]["confidence"])
            for item in requirements
        )
        mapping_dimension_confidence = sum(
            float(item["weight"]) * float(item["mappingConfidence"]) for item in requirements
        )
        confidence = rounded(
            0.50 * float(task["mapping_confidence"])
            + 0.25 * mapping_dimension_confidence
            + 0.25 * frontier_confidence
        )
        warnings = [
            {"code": "frontier_values_provisional", "track": "commercially_deployable"},
            *[
                {"code": "constraint_proxy_limit", "domain": key, "detail": value}
                for key, value in formulas["automation_feasibility"]["parameters"]["proxyWarnings"].items()
            ],
        ]
        if not task["weighting_eligible"]:
            warnings.append(
                {
                    "code": "source_task_rating_incomplete",
                    "missingFields": task["missing_rating_fields"] or [],
                    "occupationAggregationExcluded": True,
                }
            )
        exact_inputs = {
            "mappingRunId": dependencies["cohort"]["mapping_run_id"],
            "aiTaskMappingId": task["mapping_id"],
            "taskStatement": task["statement"],
            "taskSourceVersion": task["source_version"],
            "capabilityFitFormula": formulas["capability_fit"]["formula_version"],
            "automationFormula": formulas["automation_feasibility"]["formula_version"],
            "augmentationFormula": formulas["augmentation_potential"]["formula_version"],
            "frontierIndexVersion": dependencies["track"]["index_version"],
            "frontierTrack": dependencies["track"]["track_code"],
            "frontierTrackId": dependencies["track"]["id"],
            "requirements": requirements,
            "constraints": constraints,
            "taskExposureWeights": task_exposure_weights,
        }
        reconciliation = {
            "capabilityFit": fit["reconciliation"],
            "automationFeasibility": automation["reconciliation"],
            "augmentationPotential": augmentation,
            "taskExposureContributionTotal": task_exposure,
            "passed": fit["reconciliation"]["passed"] and automation["reconciliation"]["passed"],
        }
        result = {
            "pilotOccupationId": task["pilot_occupation_id"],
            "mappingId": task["mapping_id"],
            "taskId": task["task_id"],
            "statement": task["statement"],
            "weightingEligible": task["weighting_eligible"],
            "importance": float(task["importance_score"]) if task["importance_score"] is not None else None,
            "frequency": float(task["frequency_score"]) if task["frequency_score"] is not None else None,
            "sourceWeight": (
                float(task["importance_score"] * task["frequency_score"])
                if task["weighting_eligible"]
                else 0.0
            ),
            "mappingConfidence": float(task["mapping_confidence"]),
            "frontierConfidence": frontier_confidence,
            "fit": fit,
            "automation": automation,
            "augmentation": augmentation,
            "taskExposure": task_exposure,
            "confidence": confidence,
            "warnings": warnings,
            "exactInputs": exact_inputs,
            "reconciliation": reconciliation,
            "inputHash": canonical_hash(exact_inputs),
        }
        task_results.append(result)
        tasks_by_occupation[task["pilot_occupation_id"]].append(result)

    occupation_results = []
    replacement_weights = occupation_parameters["replacementWeights"]
    for occupation in dependencies["occupations"]:
        source_tasks = source_tasks_by_occupation[occupation["id"]]
        mapped_tasks = tasks_by_occupation[occupation["id"]]
        source_weight_total = sum(
            float(task["importance_score"] * task["frequency_score"])
            for task in source_tasks
            if task["weighting_eligible"]
        )
        weighted_tasks = [item for item in mapped_tasks if item["weightingEligible"]]
        covered_weight = sum(item["sourceWeight"] for item in weighted_tasks)
        if covered_weight <= 0 or source_weight_total <= 0:
            raise ValueError(f"No usable weighted coverage for {occupation['occupation_code']}")
        task_contributions = []
        for item in weighted_tasks:
            normalized_weight = item["sourceWeight"] / covered_weight
            task_contributions.append(
                {
                    "taskAssessmentKey": item["mappingId"],
                    "onetTaskId": item["taskId"],
                    "statement": item["statement"],
                    "importance": item["importance"],
                    "frequency": item["frequency"],
                    "sourceWeight": round(item["sourceWeight"], 8),
                    "normalizedCoveredWeight": round(normalized_weight, 8),
                    "taskAIExposure": item["taskExposure"],
                    "automationFeasibility": item["automation"]["score"],
                    "aiExposureContribution": rounded(normalized_weight * item["taskExposure"]),
                }
            )
        ai_exposure = rounded(sum(item["aiExposureContribution"] for item in task_contributions))
        task_automation = sum(
            item["sourceWeight"] * item["automation"]["score"] for item in weighted_tasks
        ) / covered_weight
        capability_proximity = sum(item["sourceWeight"] * item["fit"]["score"] for item in weighted_tasks) / covered_weight
        constraint_levels = {
            slug: sum(
                item["sourceWeight"]
                * next(
                    contribution["level"]
                    for contribution in item["automation"]["contributions"]
                    if contribution["slug"] == slug
                )
                for item in weighted_tasks
            )
            / covered_weight
            for slug in formulas["automation_feasibility"]["parameters"]["constraintWeights"]
        }
        human_dependency = sum(
            float(weight) * constraint_levels[slug]
            for slug, weight in occupation_parameters["humanDependencyWeights"].items()
        )
        physical_dependency = sum(
            float(weight) * constraint_levels[slug]
            for slug, weight in occupation_parameters["physicalDependencyWeights"].items()
        )
        factor_values = {
            "taskAutomationExposure": task_automation,
            "aiCapabilityProximity": capability_proximity,
            "humanDependencyResistance": 100.0 - human_dependency,
            "physicalDependencyResistance": 100.0 - physical_dependency,
            "adoptionPressure": float(occupation_parameters["adoptionPressureDefault"]),
            "labourMarketResilienceResistance": 100.0
            - float(occupation_parameters["labourMarketResilienceDefault"]),
        }
        factor_contributions = [
            {
                "factor": key,
                "value": rounded(factor_values[key]),
                "weight": float(weight),
                "weightedContribution": rounded(float(weight) * factor_values[key]),
                "placeholder": key in {"adoptionPressure", "labourMarketResilienceResistance"},
            }
            for key, weight in replacement_weights.items()
        ]
        replacement_risk = rounded(sum(item["weightedContribution"] for item in factor_contributions))
        coverage = rounded(100.0 * covered_weight / source_weight_total)
        mapping_confidence = sum(
            item["sourceWeight"] * item["mappingConfidence"] for item in weighted_tasks
        ) / covered_weight
        frontier_confidence = sum(
            item["sourceWeight"] * item["frontierConfidence"] for item in weighted_tasks
        ) / covered_weight
        source_completeness = 100.0 * sum(1 for task in source_tasks if task["weighting_eligible"]) / len(source_tasks)
        confidence_weights = occupation_parameters["confidenceWeights"]
        confidence = rounded(
            float(confidence_weights["weightedCoverage"]) * coverage
            + float(confidence_weights["mappingConfidence"]) * mapping_confidence
            + float(confidence_weights["frontierConfidence"]) * frontier_confidence
            + float(confidence_weights["sourceCompleteness"]) * source_completeness
        )
        warnings = [
            {
                "code": "neutral_placeholder",
                "factor": "adoptionPressure",
                "value": occupation_parameters["adoptionPressureDefault"],
            },
            {
                "code": "neutral_placeholder",
                "factor": "labourMarketResilience",
                "value": occupation_parameters["labourMarketResilienceDefault"],
            },
            {"code": "frontier_values_provisional", "track": "commercially_deployable"},
        ]
        excluded_ambiguous = sum(1 for task in source_tasks if task["ambiguity_state"] != "none")
        if excluded_ambiguous:
            warnings.append({"code": "mapping_policy_exclusions", "taskCount": excluded_ambiguous})
        missing_ratings = sum(1 for task in source_tasks if not task["weighting_eligible"])
        if missing_ratings:
            warnings.append({"code": "source_task_rating_incomplete", "taskCount": missing_ratings})
        warnings.extend(plain(decoded(occupation["warnings"])))
        exact_inputs = {
            "cohortVersion": dependencies["cohort"]["cohort_version"],
            "occupationCode": occupation["occupation_code"],
            "mappingRunId": dependencies["cohort"]["mapping_run_id"],
            "occupationFormula": dependencies["occupationFormula"]["formula_version"],
            "frontierIndexVersion": dependencies["track"]["index_version"],
            "frontierTrack": dependencies["track"]["track_code"],
            "sourceTaskWeighting": occupation_parameters["taskWeight"],
            "sourceWeightTotal": round(source_weight_total, 8),
            "coveredSourceWeight": round(covered_weight, 8),
            "constraintLevels": {key: rounded(value) for key, value in constraint_levels.items()},
            "replacementWeights": replacement_weights,
            "confidenceWeights": confidence_weights,
        }
        reconciliation = {
            "normalizedTaskWeightTotal": round(sum(item["normalizedCoveredWeight"] for item in task_contributions), 7),
            "taskContributionTotal": rounded(sum(item["aiExposureContribution"] for item in task_contributions)),
            "replacementFactorWeightTotal": round(sum(float(value) for value in replacement_weights.values()), 7),
            "replacementContributionTotal": rounded(sum(item["weightedContribution"] for item in factor_contributions)),
            "passed": abs(ai_exposure - rounded(sum(item["aiExposureContribution"] for item in task_contributions))) <= 0.001
            and abs(replacement_risk - rounded(sum(item["weightedContribution"] for item in factor_contributions))) <= 0.001,
        }
        occupation_results.append(
            {
                "pilotOccupationId": occupation["id"],
                "occupationCode": occupation["occupation_code"],
                "title": occupation["source_title"],
                "sourceTaskCount": len(source_tasks),
                "mappedTaskCount": len(mapped_tasks),
                "excludedTaskCount": len(source_tasks) - len(mapped_tasks),
                "weightingEligibleTaskCount": sum(1 for task in source_tasks if task["weighting_eligible"]),
                "coverage": coverage,
                "aiExposure": ai_exposure,
                "replacementRisk": replacement_risk,
                "confidence": confidence,
                "factors": factor_contributions,
                "tasks": sorted(task_contributions, key=lambda item: -item["aiExposureContribution"]),
                "warnings": warnings,
                "exactInputs": exact_inputs,
                "reconciliation": reconciliation,
                "inputHash": canonical_hash({"inputs": exact_inputs, "tasks": task_contributions}),
            }
        )
    return task_results, occupation_results


async def previous_output(connection: asyncpg.Connection, run_id: int) -> dict[str, Any]:
    tasks = await connection.fetch(
        "SELECT onet_task_id,ai_capability_fit,automation_feasibility,augmentation_potential,task_ai_exposure,confidence,input_hash FROM phase4a_task_assessments WHERE calculation_run_id=$1 ORDER BY onet_task_id",
        run_id,
    )
    occupations = await connection.fetch(
        "SELECT pilot_occupation_id,ai_exposure,replacement_risk,confidence,weighted_task_coverage,input_hash FROM phase4a_occupation_scores WHERE calculation_run_id=$1 ORDER BY pilot_occupation_id",
        run_id,
    )
    return plain({"tasks": [dict(row) for row in tasks], "occupations": [dict(row) for row in occupations]})


def calculated_output(tasks: list[dict[str, Any]], occupations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "tasks": [
            {
                "onet_task_id": item["taskId"],
                "ai_capability_fit": item["fit"]["score"],
                "automation_feasibility": item["automation"]["score"],
                "augmentation_potential": item["augmentation"]["score"],
                "task_ai_exposure": item["taskExposure"],
                "confidence": item["confidence"],
                "input_hash": item["inputHash"],
            }
            for item in sorted(tasks, key=lambda row: row["taskId"])
        ],
        "occupations": [
            {
                "pilot_occupation_id": item["pilotOccupationId"],
                "ai_exposure": item["aiExposure"],
                "replacement_risk": item["replacementRisk"],
                "confidence": item["confidence"],
                "weighted_task_coverage": item["coverage"],
                "input_hash": item["inputHash"],
            }
            for item in sorted(occupations, key=lambda row: row["pilotOccupationId"])
        ],
    }


async def run(run_version: str, run_kind: str, previous_run_version: str | None, cohort_version: str) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        existing = await connection.fetchrow(
            "SELECT id,run_version,run_kind,reconciliation_status,replay_matches_previous FROM phase4a_calculation_runs WHERE run_version=$1",
            run_version,
        )
        if existing:
            await transaction.commit()
            return {**dict(existing), "reused": True, "newMappingCalls": 0}
        dependencies = await load_dependencies(connection, cohort_version)
        task_results, occupation_results = calculate(dependencies)
        if not all(item["reconciliation"]["passed"] for item in task_results + occupation_results):
            raise ValueError("Contribution reconciliation failed")
        previous = None
        replay_matches = None
        if previous_run_version:
            previous = await connection.fetchrow(
                "SELECT id,mapping_run_id FROM phase4a_calculation_runs WHERE run_version=$1", previous_run_version
            )
            if previous is None:
                raise ValueError(f"Unknown previous run {previous_run_version}")
            if previous["mapping_run_id"] != dependencies["cohort"]["mapping_run_id"]:
                raise ValueError("Formula-only/replay run cannot change the mapping run")
            replay_matches = canonical_hash(await previous_output(connection, previous["id"])) == canonical_hash(
                calculated_output(task_results, occupation_results)
            )
            if run_kind == "deterministic_replay" and not replay_matches:
                raise ValueError("Deterministic replay did not match the previous run")
        dependency_manifest = {
            "cohortVersion": cohort_version,
            "mappingRunId": dependencies["cohort"]["mapping_run_id"],
            "frontierTrackId": dependencies["track"]["id"],
            "frontierValues": dependencies["frontier"],
            "taskFormulaVersions": {
                key: value["formula_version"] for key, value in dependencies["formulas"].items()
            },
            "occupationFormulaVersion": dependencies["occupationFormula"]["formula_version"],
            "taskInputHashes": [item["inputHash"] for item in task_results],
        }
        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4A scoring pilot'"
        )
        run_id = await connection.fetchval(
            """
            INSERT INTO phase4a_calculation_runs (
              cohort_id,run_version,run_kind,capability_fit_formula_id,automation_formula_id,
              augmentation_formula_id,occupation_formula_id,mapping_run_id,frontier_track_id,
              dependency_hash,previous_run_id,new_ai_mapping_calls,reused_mapping_count,
              task_assessment_count,occupation_score_count,reconciliation_status,replay_matches_previous,
              provenance,source_id,created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,0,$12,$13,$14,'passed',$15,$16,$17,
              'system:phase4a-pilot-scorer') RETURNING id
            """,
            dependencies["cohort"]["id"],
            run_version,
            run_kind,
            dependencies["formulas"]["capability_fit"]["id"],
            dependencies["formulas"]["automation_feasibility"]["id"],
            dependencies["formulas"]["augmentation_potential"]["id"],
            dependencies["occupationFormula"]["id"],
            dependencies["cohort"]["mapping_run_id"],
            dependencies["track"]["id"],
            canonical_hash(dependency_manifest),
            previous["id"] if previous else None,
            len(task_results) if run_kind != "initial" else 0,
            len(task_results),
            len(occupation_results),
            replay_matches,
            dumps(
                {
                    "phase": "4A",
                    "pilotOnly": True,
                    "public": False,
                    "productionScoreWrites": 0,
                    "newMappingCalls": 0,
                    "dependencyManifest": dependency_manifest,
                }
            ),
            source_id,
        )
        for item in task_results:
            await connection.execute(
                """
                INSERT INTO phase4a_task_assessments (
                  calculation_run_id,pilot_occupation_id,ai_task_mapping_id,onet_task_id,assessment_version,
                  ai_capability_fit,automation_feasibility,augmentation_potential,task_ai_exposure,confidence,
                  capability_contributions,constraint_contributions,exact_inputs,warnings,reconciliation,
                  input_hash,source_id,provenance,created_by
                ) VALUES ($1,$2,$3,$4,'phase4a-task-assessment-v1',$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,
                  $15,$16,$17,'system:phase4a-pilot-scorer')
                """,
                run_id,
                item["pilotOccupationId"],
                item["mappingId"],
                item["taskId"],
                item["fit"]["score"],
                item["automation"]["score"],
                item["augmentation"]["score"],
                item["taskExposure"],
                item["confidence"],
                dumps(item["fit"]["contributions"]),
                dumps(item["automation"]["contributions"]),
                dumps(item["exactInputs"]),
                dumps(item["warnings"]),
                dumps(item["reconciliation"]),
                item["inputHash"],
                source_id,
                dumps({"phase": "4A", "pilotOnly": True, "formulaRun": run_version}),
            )
        for item in occupation_results:
            await connection.execute(
                """
                INSERT INTO phase4a_occupation_scores (
                  calculation_run_id,pilot_occupation_id,score_version,source_task_count,mapped_task_count,
                  excluded_task_count,weighting_eligible_task_count,weighted_task_coverage,ai_exposure,
                  replacement_risk,confidence,factor_contributions,task_contributions,exact_inputs,warnings,
                  reconciliation,input_hash,source_id,provenance,created_by
                ) VALUES ($1,$2,'phase4a-occupation-score-v1',$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,
                  $15,$16,$17,$18,'system:phase4a-pilot-scorer')
                """,
                run_id,
                item["pilotOccupationId"],
                item["sourceTaskCount"],
                item["mappedTaskCount"],
                item["excludedTaskCount"],
                item["weightingEligibleTaskCount"],
                item["coverage"],
                item["aiExposure"],
                item["replacementRisk"],
                item["confidence"],
                dumps(item["factors"]),
                dumps(item["tasks"]),
                dumps(item["exactInputs"]),
                dumps(item["warnings"]),
                dumps(item["reconciliation"]),
                item["inputHash"],
                source_id,
                dumps({"phase": "4A", "pilotOnly": True, "formulaRun": run_version}),
            )
        await transaction.commit()
        return {
            "calculationRunId": run_id,
            "runVersion": run_version,
            "runKind": run_kind,
            "taskAssessments": len(task_results),
            "occupationScores": len(occupation_results),
            "newMappingCalls": 0,
            "replayMatchesPrevious": replay_matches,
            "reconciliation": "passed",
            "reused": False,
        }
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-version", required=True)
    parser.add_argument(
        "--run-kind", choices=["initial", "deterministic_replay", "formula_only_recompute"], required=True
    )
    parser.add_argument("--previous-run-version")
    parser.add_argument("--cohort-version", default="phase4a-2026q3-v1")
    args = parser.parse_args()
    if args.run_kind != "initial" and not args.previous_run_version:
        parser.error("--previous-run-version is required for replay/recompute runs")
    print(
        json.dumps(
            await run(args.run_version, args.run_kind, args.previous_run_version, args.cohort_version), indent=2
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
