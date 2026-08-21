"""Run Phase 4B calibration against the frozen Phase 4A mappings and cohort."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import defaultdict
from typing import Any

import asyncpg

from calibration import (
    augmentation_potential_v2,
    automation_feasibility_v2,
    capability_fit_v2,
    consolidated_constraints,
    distribution_summary,
    occupation_proxies,
)
from pilot import canonical_hash, rounded
from run_phase4a_pilot import decoded, dumps, load_dependencies, plain, previous_output


TASK_FORMULAS = (
    "task-capability-fit-v2-calibration",
    "automation-feasibility-v2-calibration",
    "augmentation-potential-v2-calibration",
)
OCCUPATION_FORMULA = "phase4b-occupation-score-v2-calibration"
PROXY_MODEL = "phase4b-occupation-proxy-v1"


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def collect_source_keys(parameters: dict[str, Any]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    groups = list(parameters["domains"].values()) + [
        parameters["adoptionPressure"]["components"],
        parameters["labourMarketResilience"]["components"],
    ]
    for components in groups:
        for component in components:
            if "elementId" in component:
                keys.add((component["elementType"], component["elementId"], component["scaleId"]))
    return keys


async def load_or_create_proxies(
    connection: asyncpg.Connection, dependencies: dict[str, Any]
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    model_row = await connection.fetchrow(
        "SELECT * FROM phase4b_proxy_model_versions WHERE model_version=$1", PROXY_MODEL
    )
    if model_row is None:
        raise ValueError(f"Missing proxy model {PROXY_MODEL}")
    model = dict(model_row)
    model["parameters"] = decoded(model["parameters"])
    source_keys = collect_source_keys(model["parameters"])
    occupation_codes = [item["occupation_code"] for item in dependencies["occupations"]]
    element_ids = sorted({key[1] for key in source_keys})
    rating_rows = await connection.fetch(
        """
        SELECT rating.occupation_code,rating.element_type,rating.element_id,rating.scale_id,
               rating.normalized_value,rating.sample_size,rating.standard_error,
               rating.recommend_suppress,rating.not_relevant,rating.source_version,
               rating.source_record_id,rating.row_hash,element.element_name
        FROM onet_element_ratings rating
        JOIN onet_elements element
          ON element.element_type=rating.element_type AND element.element_id=rating.element_id AND element.is_current
        WHERE rating.is_current AND rating.occupation_code=ANY($1::text[])
          AND rating.element_id=ANY($2::text[])
        ORDER BY rating.occupation_code,rating.element_type,rating.element_id,rating.scale_id
        """,
        occupation_codes,
        element_ids,
    )
    ratings_by_code: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = defaultdict(dict)
    for row in rating_rows:
        key = (row["element_type"], row["element_id"], row["scale_id"])
        if key not in source_keys:
            continue
        ratings_by_code[row["occupation_code"]][key] = {
            "normalizedValue": float(row["normalized_value"]),
            "sampleSize": row["sample_size"],
            "standardError": float(row["standard_error"]) if row["standard_error"] is not None else None,
            "recommendSuppress": row["recommend_suppress"],
            "notRelevant": row["not_relevant"],
            "sourceVersion": row["source_version"],
            "sourceRecordId": row["source_record_id"],
            "rowHash": row["row_hash"],
            "elementName": row["element_name"],
        }
    source_id = await connection.fetchval(
        "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4B calibration'"
    )
    snapshots: dict[int, dict[str, Any]] = {}
    for occupation in dependencies["occupations"]:
        existing = await connection.fetchrow(
            """
            SELECT * FROM phase4b_occupation_proxy_snapshots
            WHERE proxy_model_version_id=$1 AND pilot_occupation_id=$2
            """,
            model["id"],
            occupation["id"],
        )
        if existing:
            snapshot = dict(existing)
            snapshot["domain_values"] = decoded(snapshot["domain_values"])
            snapshot["component_contributions"] = decoded(snapshot["component_contributions"])
            snapshot["exact_inputs"] = decoded(snapshot["exact_inputs"])
            snapshot["warnings"] = decoded(snapshot["warnings"])
            snapshot["reconciliation"] = decoded(snapshot["reconciliation"])
            snapshots[occupation["id"]] = snapshot
            continue
        ratings = ratings_by_code[occupation["occupation_code"]]
        result = occupation_proxies(ratings, model["parameters"])
        exact_inputs = {
            "proxyModelVersion": model["model_version"],
            "occupationCode": occupation["occupation_code"],
            "sourceRatings": [
                {"elementType": key[0], "elementId": key[1], "scaleId": key[2], **value}
                for key, value in sorted(ratings.items())
            ],
            "sourcePolicy": model["parameters"]["sourcePolicy"],
        }
        snapshot_id = await connection.fetchval(
            """
            INSERT INTO phase4b_occupation_proxy_snapshots (
              proxy_model_version_id,pilot_occupation_id,adoption_pressure,labour_market_resilience,
              proxy_confidence,domain_values,component_contributions,exact_inputs,warnings,
              reconciliation,input_hash,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
              'system:phase4b-proxy-calculator') RETURNING id
            """,
            model["id"],
            occupation["id"],
            result["adoptionPressure"]["value"],
            result["labourMarketResilience"]["value"],
            result["confidence"],
            dumps({key: {"value": value["value"], "confidence": value["confidence"]} for key, value in result["domains"].items()}),
            dumps(
                {
                    "domains": result["domains"],
                    "adoptionPressure": result["adoptionPressure"],
                    "labourMarketResilience": result["labourMarketResilience"],
                }
            ),
            dumps(exact_inputs),
            dumps(result["warnings"]),
            dumps(result["reconciliation"]),
            canonical_hash(exact_inputs),
            source_id,
            dumps(
                {
                    "phase": "4B",
                    "provisional": True,
                    "productionAllowed": False,
                    "noImputation": True,
                }
            ),
        )
        snapshots[occupation["id"]] = {
            "id": snapshot_id,
            "proxy_model_version_id": model["id"],
            "pilot_occupation_id": occupation["id"],
            "adoption_pressure": result["adoptionPressure"]["value"],
            "labour_market_resilience": result["labourMarketResilience"]["value"],
            "proxy_confidence": result["confidence"],
            "domain_values": {
                key: {"value": value["value"], "confidence": value["confidence"]}
                for key, value in result["domains"].items()
            },
            "component_contributions": {
                "domains": result["domains"],
                "adoptionPressure": result["adoptionPressure"],
                "labourMarketResilience": result["labourMarketResilience"],
            },
            "exact_inputs": exact_inputs,
            "warnings": result["warnings"],
            "reconciliation": result["reconciliation"],
            "input_hash": canonical_hash(exact_inputs),
        }
    return snapshots, model


def calculate(
    dependencies: dict[str, Any],
    proxies: dict[int, dict[str, Any]],
    model: dict[str, Any],
    methodology_phase: str = "4B",
    mapping_scope_version: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    formulas = dependencies["formulas"]
    occupation_parameters = dependencies["occupationFormula"]["parameters"]
    exposure_weights = occupation_parameters["taskExposureWeights"]
    tasks_by_occupation: dict[int, list[dict[str, Any]]] = defaultdict(list)
    source_tasks_by_occupation: dict[int, list[dict[str, Any]]] = defaultdict(list)
    task_results = []
    for task in dependencies["tasks"]:
        occupation_id = task["pilot_occupation_id"]
        source_tasks_by_occupation[occupation_id].append(task)
        if not task["scoring_eligible"]:
            continue
        proxy_snapshot = proxies[occupation_id]
        proxy_domains = proxy_snapshot["component_contributions"]["domains"]
        requirements = dependencies["requirements"][task["mapping_id"]]
        task_constraints = dependencies["constraints"][task["mapping_id"]]
        fit = capability_fit_v2(
            requirements, dependencies["frontier"], formulas["capability_fit"]["parameters"]
        )
        constraints = consolidated_constraints(
            task_constraints, {"domains": proxy_domains}, formulas["automation_feasibility"]["parameters"]
        )
        automation = automation_feasibility_v2(
            fit["score"], constraints, formulas["automation_feasibility"]["parameters"]
        )
        augmentation = augmentation_potential_v2(
            fit["score"], automation["score"], formulas["augmentation_potential"]["parameters"]
        )
        task_exposure = rounded(
            float(exposure_weights["aiCapabilityFit"]) * fit["score"]
            + float(exposure_weights["automationFeasibility"]) * automation["score"]
            + float(exposure_weights["augmentationPotential"]) * augmentation["score"]
        )
        frontier_confidence = sum(
            float(item["weight"]) * float(dependencies["frontier"][item["slug"]]["confidence"])
            for item in requirements
        )
        dimension_confidence = sum(
            float(item["weight"]) * float(item["mappingConfidence"]) for item in requirements
        )
        base_confidence = (
            0.50 * float(task["mapping_confidence"])
            + 0.25 * dimension_confidence
            + 0.25 * frontier_confidence
        )
        confidence = rounded(base_confidence - automation["proxyConfidencePenalty"])
        warnings = [
            {"code": "frontier_values_provisional", "track": "commercially_deployable"},
            {
                "code": "occupation_proxy_fallback",
                "proxyModelVersion": model["model_version"],
                "domainsUsed": automation["proxyDomainCount"],
                "confidencePenalty": automation["proxyConfidencePenalty"],
            },
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
            "methodologyPhase": methodology_phase,
            "mappingRunId": task.get("mapping_run_id") or dependencies["cohort"]["mapping_run_id"],
            "aiTaskMappingId": task["mapping_id"],
            "taskStatement": task["statement"],
            "taskSourceVersion": task["source_version"],
            "capabilityFitFormula": formulas["capability_fit"]["formula_version"],
            "automationFormula": formulas["automation_feasibility"]["formula_version"],
            "augmentationFormula": formulas["augmentation_potential"]["formula_version"],
            "frontierIndexVersion": dependencies["track"]["index_version"],
            "frontierTrack": dependencies["track"]["track_code"],
            "proxyModelVersion": model["model_version"],
            "proxySnapshotId": proxy_snapshot["id"],
            "requirements": requirements,
            "directConstraints": task_constraints,
            "consolidatedConstraints": constraints,
            "taskExposureWeights": exposure_weights,
        }
        if mapping_scope_version is not None:
            exact_inputs["mappingScopeVersion"] = mapping_scope_version
            exact_inputs["mappingScopeDecision"] = task.get("scope_decision")
        reconciliation = {
            "capabilityFit": fit["reconciliation"],
            "automationFeasibility": automation["reconciliation"],
            "augmentationPotential": augmentation,
            "taskExposureContributionTotal": task_exposure,
            "passed": fit["reconciliation"]["passed"] and automation["reconciliation"]["passed"],
        }
        result = {
            "pilotOccupationId": occupation_id,
            "mappingId": task["mapping_id"],
            "taskId": task["task_id"],
            "statement": task["statement"],
            "weightingEligible": task["weighting_eligible"],
            "importance": float(task["importance_score"]) if task["importance_score"] is not None else None,
            "frequency": float(task["frequency_score"]) if task["frequency_score"] is not None else None,
            "sourceWeight": float(task["importance_score"] * task["frequency_score"])
            if task["weighting_eligible"]
            else 0.0,
            "mappingConfidence": float(task["mapping_confidence"]),
            "frontierConfidence": frontier_confidence,
            "fit": fit,
            "automation": automation,
            "augmentation": augmentation,
            "taskExposure": task_exposure,
            "confidence": confidence,
            "proxyPenalty": automation["proxyConfidencePenalty"],
            "proxySnapshotId": proxy_snapshot["id"],
            "warnings": warnings,
            "exactInputs": exact_inputs,
            "reconciliation": reconciliation,
            "inputHash": canonical_hash(exact_inputs),
        }
        task_results.append(result)
        tasks_by_occupation[occupation_id].append(result)

    occupation_results = []
    replacement_weights = occupation_parameters["replacementWeights"]
    for occupation in dependencies["occupations"]:
        occupation_id = occupation["id"]
        source_tasks = source_tasks_by_occupation[occupation_id]
        mapped_tasks = tasks_by_occupation[occupation_id]
        weighted_tasks = [item for item in mapped_tasks if item["weightingEligible"]]
        source_weight_total = sum(
            float(task["importance_score"] * task["frequency_score"])
            for task in source_tasks
            if task["weighting_eligible"]
        )
        covered_weight = sum(item["sourceWeight"] for item in weighted_tasks)
        if source_weight_total <= 0 or covered_weight <= 0:
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
        capability_proximity = sum(
            item["sourceWeight"] * item["fit"]["score"] for item in weighted_tasks
        ) / covered_weight
        domain_levels = {
            domain: sum(
                item["sourceWeight"]
                * next(
                    contribution["level"]
                    for contribution in item["automation"]["contributions"]
                    if contribution["slug"] == domain
                )
                for item in weighted_tasks
            )
            / covered_weight
            for domain in formulas["automation_feasibility"]["parameters"]["domainWeights"]
        }
        proxy = proxies[occupation_id]
        factor_values = {
            "taskAutomationExposure": task_automation,
            "aiCapabilityProximity": capability_proximity,
            "humanDependencyResistance": 100.0 - domain_levels["human-dependency"],
            "physicalDependencyResistance": 100.0 - domain_levels["physical-presence"],
            "adoptionPressure": float(proxy["adoption_pressure"]),
            "labourMarketResilienceResistance": 100.0 - float(proxy["labour_market_resilience"]),
        }
        factor_contributions = [
            {
                "factor": key,
                "value": rounded(factor_values[key]),
                "weight": float(weight),
                "weightedContribution": rounded(float(weight) * factor_values[key]),
                "placeholder": False,
                "provisionalProxy": key in {"adoptionPressure", "labourMarketResilienceResistance"},
                "proxyModelVersion": model["model_version"]
                if key in {"adoptionPressure", "labourMarketResilienceResistance"}
                else None,
            }
            for key, weight in replacement_weights.items()
        ]
        replacement_risk = rounded(sum(item["weightedContribution"] for item in factor_contributions))
        coverage = rounded(100.0 * covered_weight / source_weight_total)
        coverage_threshold = float(occupation_parameters["minimumWeightedCoverage"])
        coverage_passed = coverage >= coverage_threshold
        coverage_penalty = max(
            0.0,
            (coverage_threshold - coverage)
            * float(occupation_parameters["coverageConfidencePenaltyPerPoint"]),
        )
        mapping_confidence = sum(
            item["sourceWeight"] * item["mappingConfidence"] for item in weighted_tasks
        ) / covered_weight
        frontier_confidence = sum(
            item["sourceWeight"] * item["frontierConfidence"] for item in weighted_tasks
        ) / covered_weight
        source_completeness = 100.0 * sum(
            1 for task in source_tasks if task["weighting_eligible"]
        ) / len(source_tasks)
        confidence_weights = occupation_parameters["confidenceWeights"]
        raw_confidence = (
            float(confidence_weights["weightedCoverage"]) * coverage
            + float(confidence_weights["mappingConfidence"]) * mapping_confidence
            + float(confidence_weights["frontierConfidence"]) * frontier_confidence
            + float(confidence_weights["sourceCompleteness"]) * source_completeness
            + float(confidence_weights["proxyConfidence"]) * float(proxy["proxy_confidence"])
        )
        confidence = rounded(raw_confidence - coverage_penalty)
        scale_eligible = coverage_passed and confidence >= float(
            occupation_parameters["minimumScaleConfidence"]
        )
        warnings = [
            {"code": "frontier_values_provisional", "track": "commercially_deployable"},
            *plain(decoded(proxy["warnings"])),
        ]
        if not coverage_passed:
            warnings.append(
                {
                    "code": "weighted_coverage_below_threshold",
                    "coverage": coverage,
                    "threshold": coverage_threshold,
                    "confidencePenalty": rounded(coverage_penalty),
                    "scaleEligible": False,
                }
            )
        excluded = sum(1 for task in source_tasks if not task["scoring_eligible"])
        if excluded:
            warnings.append({"code": "mapping_policy_exclusions", "taskCount": excluded})
        missing_ratings = sum(1 for task in source_tasks if not task["weighting_eligible"])
        if missing_ratings:
            warnings.append({"code": "source_task_rating_incomplete", "taskCount": missing_ratings})
        warnings.extend(plain(decoded(occupation["warnings"])))
        exact_inputs = {
            "methodologyPhase": methodology_phase,
            "cohortVersion": dependencies["cohort"]["cohort_version"],
            "occupationCode": occupation["occupation_code"],
            "mappingRunId": dependencies["cohort"]["mapping_run_id"],
            "occupationFormula": dependencies["occupationFormula"]["formula_version"],
            "proxyModelVersion": model["model_version"],
            "proxySnapshotId": proxy["id"],
            "sourceWeightTotal": round(source_weight_total, 8),
            "coveredSourceWeight": round(covered_weight, 8),
            "domainLevels": {key: rounded(value) for key, value in domain_levels.items()},
            "replacementWeights": replacement_weights,
            "confidenceWeights": confidence_weights,
            "coverageThreshold": coverage_threshold,
        }
        if mapping_scope_version is not None:
            exact_inputs["mappingScopeVersion"] = mapping_scope_version
        reconciliation = {
            "normalizedTaskWeightTotal": round(
                sum(item["normalizedCoveredWeight"] for item in task_contributions), 7
            ),
            "taskContributionTotal": rounded(
                sum(item["aiExposureContribution"] for item in task_contributions)
            ),
            "replacementFactorWeightTotal": round(
                sum(float(value) for value in replacement_weights.values()), 7
            ),
            "replacementContributionTotal": rounded(
                sum(item["weightedContribution"] for item in factor_contributions)
            ),
            "proxyReconciliationPassed": decoded(proxy["reconciliation"])["passed"],
            "passed": abs(
                ai_exposure
                - rounded(sum(item["aiExposureContribution"] for item in task_contributions))
            )
            <= 0.001
            and abs(
                replacement_risk
                - rounded(sum(item["weightedContribution"] for item in factor_contributions))
            )
            <= 0.001
            and decoded(proxy["reconciliation"])["passed"],
        }
        occupation_results.append(
            {
                "pilotOccupationId": occupation_id,
                "occupationCode": occupation["occupation_code"],
                "title": occupation["source_title"],
                "sourceTaskCount": len(source_tasks),
                "mappedTaskCount": len(mapped_tasks),
                "excludedTaskCount": len(source_tasks) - len(mapped_tasks),
                "weightingEligibleTaskCount": sum(
                    1 for task in source_tasks if task["weighting_eligible"]
                ),
                "coverage": coverage,
                "coverageGateStatus": "passed" if coverage_passed else "below_threshold",
                "coveragePenalty": rounded(coverage_penalty),
                "scaleEligible": scale_eligible,
                "aiExposure": ai_exposure,
                "replacementRisk": replacement_risk,
                "confidence": confidence,
                "factors": factor_contributions,
                "tasks": sorted(
                    task_contributions, key=lambda item: -item["aiExposureContribution"]
                ),
                "warnings": warnings,
                "exactInputs": exact_inputs,
                "reconciliation": reconciliation,
                "inputHash": canonical_hash({"inputs": exact_inputs, "tasks": task_contributions}),
                "proxySnapshotId": proxy["id"],
            }
        )
    return task_results, occupation_results


def output_signature(tasks: list[dict[str, Any]], occupations: list[dict[str, Any]]) -> dict[str, Any]:
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


async def persist_diagnostics(
    connection: asyncpg.Connection,
    baseline_run_id: int,
    calibration_run_id: int,
    tasks: list[dict[str, Any]],
    occupations: list[dict[str, Any]],
    source_id: int,
) -> None:
    metric_specs = [
        ("task", "ai_capability_fit", "ai_capability_fit", [item["fit"]["score"] for item in tasks]),
        ("task", "automation_feasibility", "automation_feasibility", [item["automation"]["score"] for item in tasks]),
        ("task", "augmentation_potential", "augmentation_potential", [item["augmentation"]["score"] for item in tasks]),
        ("task", "task_ai_exposure", "task_ai_exposure", [item["taskExposure"] for item in tasks]),
        ("occupation", "ai_exposure", "ai_exposure", [item["aiExposure"] for item in occupations]),
        ("occupation", "replacement_risk", "replacement_risk", [item["replacementRisk"] for item in occupations]),
        ("occupation", "confidence", "confidence", [item["confidence"] for item in occupations]),
    ]
    for scope, name, column, calibrated_values in metric_specs:
        table = "phase4a_task_assessments" if scope == "task" else "phase4a_occupation_scores"
        baseline_values = [
            float(row["value"])
            for row in await connection.fetch(
                f"SELECT {column} value FROM {table} WHERE calculation_run_id=$1 ORDER BY id",
                baseline_run_id,
            )
        ]
        baseline = distribution_summary(baseline_values)
        calibrated = distribution_summary(calibrated_values)
        delta = {
            # Distribution deltas are signed audit values, not bounded scores.
            "mean": round(calibrated["mean"] - baseline["mean"], 4),
            "median": round(calibrated["median"] - baseline["median"], 4),
            "standardDeviation": round(
                calibrated["standardDeviation"] - baseline["standardDeviation"], 4
            ),
            "atOrAbove90": calibrated["atOrAbove90"] - baseline["atOrAbove90"],
            "atOrAbove95": calibrated["atOrAbove95"] - baseline["atOrAbove95"],
        }
        await connection.execute(
            """
            INSERT INTO phase4b_distribution_diagnostics (
              baseline_run_id,calibration_run_id,metric_scope,metric_name,baseline_summary,
              calibrated_summary,delta_summary,reconciliation,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'system:phase4b-calibration')
            """,
            baseline_run_id,
            calibration_run_id,
            scope,
            name,
            dumps(baseline),
            dumps(calibrated),
            dumps(delta),
            dumps(
                {
                    "baselineCount": len(baseline_values),
                    "calibratedCount": len(calibrated_values),
                    "passed": len(baseline_values) == len(calibrated_values),
                }
            ),
            source_id,
            dumps({"phase": "4B", "sameCohort": True, "sameMappings": True}),
        )


async def run(
    run_version: str,
    run_kind: str,
    previous_run_version: str,
    baseline_run_version: str,
    cohort_version: str,
) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        existing = await connection.fetchrow(
            "SELECT * FROM phase4a_calculation_runs WHERE run_version=$1", run_version
        )
        if existing:
            await transaction.commit()
            return {
                "calculationRunId": existing["id"],
                "runVersion": run_version,
                "reused": True,
                "newMappingCalls": existing["new_ai_mapping_calls"],
            }
        dependencies = await load_dependencies(
            connection,
            cohort_version,
            task_formula_versions=TASK_FORMULAS,
            occupation_formula_version=OCCUPATION_FORMULA,
        )
        proxies, proxy_model = await load_or_create_proxies(connection, dependencies)
        tasks, occupations = calculate(dependencies, proxies, proxy_model)
        if not all(item["reconciliation"]["passed"] for item in tasks + occupations):
            raise ValueError("Phase 4B contribution reconciliation failed")
        baseline = await connection.fetchrow(
            "SELECT * FROM phase4a_calculation_runs WHERE run_version=$1", baseline_run_version
        )
        previous = await connection.fetchrow(
            "SELECT * FROM phase4a_calculation_runs WHERE run_version=$1", previous_run_version
        )
        if baseline is None or previous is None:
            raise ValueError("Baseline or previous calculation run is missing")
        if baseline["mapping_run_id"] != dependencies["cohort"]["mapping_run_id"] or previous[
            "mapping_run_id"
        ] != dependencies["cohort"]["mapping_run_id"]:
            raise ValueError("Phase 4B cannot change the frozen mapping run")
        replay_matches = None
        if run_kind == "deterministic_replay":
            replay_matches = canonical_hash(await previous_output(connection, previous["id"])) == canonical_hash(
                output_signature(tasks, occupations)
            )
            if not replay_matches:
                raise ValueError("Phase 4B deterministic replay mismatch")
        dependency_manifest = {
            "phase": "4B",
            "cohortVersion": cohort_version,
            "mappingRunId": dependencies["cohort"]["mapping_run_id"],
            "frontierTrackId": dependencies["track"]["id"],
            "formulaVersions": {
                key: item["formula_version"] for key, item in dependencies["formulas"].items()
            },
            "occupationFormula": dependencies["occupationFormula"]["formula_version"],
            "proxyModel": proxy_model["model_version"],
            "proxySnapshotHashes": [proxies[key]["input_hash"] for key in sorted(proxies)],
            "taskInputHashes": [item["inputHash"] for item in tasks],
        }
        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4B calibration'"
        )
        run_id = await connection.fetchval(
            """
            INSERT INTO phase4a_calculation_runs (
              cohort_id,run_version,run_kind,capability_fit_formula_id,automation_formula_id,
              augmentation_formula_id,occupation_formula_id,mapping_run_id,frontier_track_id,
              dependency_hash,previous_run_id,new_ai_mapping_calls,reused_mapping_count,
              task_assessment_count,occupation_score_count,reconciliation_status,replay_matches_previous,
              provenance,source_id,created_by,methodology_phase,proxy_model_version_id,baseline_run_id
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,0,$12,$13,$14,'passed',$15,$16,$17,
              'system:phase4b-calibration','4B',$18,$19) RETURNING id
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
            previous["id"],
            len(tasks),
            len(tasks),
            len(occupations),
            replay_matches,
            dumps(
                {
                    "phase": "4B",
                    "calibrationOnly": True,
                    "newMappingCalls": 0,
                    "public": False,
                    "productionScoreWrites": 0,
                    "dependencyManifest": dependency_manifest,
                }
            ),
            source_id,
            proxy_model["id"],
            baseline["id"],
        )
        for item in tasks:
            await connection.execute(
                """
                INSERT INTO phase4a_task_assessments (
                  calculation_run_id,pilot_occupation_id,ai_task_mapping_id,onet_task_id,assessment_version,
                  ai_capability_fit,automation_feasibility,augmentation_potential,task_ai_exposure,confidence,
                  capability_contributions,constraint_contributions,exact_inputs,warnings,reconciliation,
                  input_hash,source_id,provenance,created_by,methodology_phase,proxy_snapshot_id,
                  proxy_confidence_penalty
                ) VALUES ($1,$2,$3,$4,'phase4b-task-assessment-v2',$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,
                  $15,$16,$17,'system:phase4b-calibration','4B',$18,$19)
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
                dumps({"phase": "4B", "calibrationOnly": True, "formulaRun": run_version}),
                item["proxySnapshotId"],
                item["proxyPenalty"],
            )
        for item in occupations:
            await connection.execute(
                """
                INSERT INTO phase4a_occupation_scores (
                  calculation_run_id,pilot_occupation_id,score_version,source_task_count,mapped_task_count,
                  excluded_task_count,weighting_eligible_task_count,weighted_task_coverage,ai_exposure,
                  replacement_risk,confidence,factor_contributions,task_contributions,exact_inputs,warnings,
                  reconciliation,input_hash,source_id,provenance,created_by,methodology_phase,
                  proxy_snapshot_id,coverage_gate_status,confidence_penalty,scale_eligible
                ) VALUES ($1,$2,'phase4b-occupation-score-v2-calibration',$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,
                  $13,$14,$15,$16,$17,$18,'system:phase4b-calibration','4B',$19,$20,$21,$22)
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
                dumps({"phase": "4B", "calibrationOnly": True, "formulaRun": run_version}),
                item["proxySnapshotId"],
                item["coverageGateStatus"],
                item["coveragePenalty"],
                item["scaleEligible"],
            )
        if run_kind == "formula_only_recompute":
            await persist_diagnostics(
                connection, baseline["id"], run_id, tasks, occupations, source_id
            )
        await transaction.commit()
        return {
            "calculationRunId": run_id,
            "runVersion": run_version,
            "runKind": run_kind,
            "mappingRunId": dependencies["cohort"]["mapping_run_id"],
            "newMappingCalls": 0,
            "reusedMappings": len(tasks),
            "proxySnapshots": len(proxies),
            "taskAssessments": len(tasks),
            "occupationScores": len(occupations),
            "coverageBlockedOccupations": sum(
                item["coverageGateStatus"] == "below_threshold" for item in occupations
            ),
            "scaleEligibleOccupations": sum(item["scaleEligible"] for item in occupations),
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
        "--run-kind", choices=["formula_only_recompute", "deterministic_replay"], required=True
    )
    parser.add_argument("--previous-run-version", required=True)
    parser.add_argument("--baseline-run-version", default="phase4a-formula-recompute-v1-2026q3")
    parser.add_argument("--cohort-version", default="phase4a-2026q3-v1")
    args = parser.parse_args()
    print(
        json.dumps(
            await run(
                args.run_version,
                args.run_kind,
                args.previous_run_version,
                args.baseline_run_version,
                args.cohort_version,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
