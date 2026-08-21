"""Run the production-isolated Phase 5 bounded corpus candidate calculation."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import asyncpg

try:
    from .calibration import (
        augmentation_potential_v2,
        automation_feasibility_v2,
        consolidated_constraints,
        occupation_proxies,
    )
    from .phase4d_proxies import (
        ACCOUNTABILITY_COMPONENTS,
        CLINICAL_COMPONENTS,
        CONSEQUENCE_BASE_COMPONENTS,
        ENVIRONMENT_COMPONENTS,
        FAMILY_VERSIONS,
        MODEL_VERSION as PHASE4D_MODEL,
        PHYSICAL_COMPONENTS,
        direct_structural_proxies,
    )
    from .phase5_analysis import CHECKS, POLICY_VERSION, THRESHOLDS, analyze
    from .pilot import canonical_hash, rounded
    from .run_phase4a_pilot import decoded, dumps, load_dependencies, plain
    from .run_phase4b_calibration import (
        OCCUPATION_FORMULA,
        PROXY_MODEL,
        TASK_FORMULAS,
        calculate,
        collect_source_keys,
    )
    from .run_phase4c_validation import database_url
except ImportError:
    from calibration import (
        augmentation_potential_v2,
        automation_feasibility_v2,
        consolidated_constraints,
        occupation_proxies,
    )
    from phase4d_proxies import (
        ACCOUNTABILITY_COMPONENTS, CLINICAL_COMPONENTS, CONSEQUENCE_BASE_COMPONENTS,
        ENVIRONMENT_COMPONENTS, FAMILY_VERSIONS, MODEL_VERSION as PHASE4D_MODEL,
        PHYSICAL_COMPONENTS, direct_structural_proxies,
    )
    from phase5_analysis import CHECKS, POLICY_VERSION, THRESHOLDS, analyze
    from pilot import canonical_hash, rounded
    from run_phase4a_pilot import decoded, dumps, load_dependencies, plain
    from run_phase4b_calibration import (
        OCCUPATION_FORMULA, PROXY_MODEL, TASK_FORMULAS, calculate, collect_source_keys,
    )
    from run_phase4c_validation import database_url


NAMESPACE_VERSION = "phase5-candidate-2026q3-v1"
MAPPING_RUN_VERSION = "phase5-bounded-mapper-v1-2026q3"
RUN_VERSION = "phase5-bounded-corpus-v1-2026q3"
REPLAY_VERSION = "phase5-bounded-corpus-replay-v1-2026q3"
MAPPING_SCOPE_VERSION = "phase5-dependency-aware-minimum-scope-v1"
ALL_DIRECT_COMPONENTS = (
    PHYSICAL_COMPONENTS + ENVIRONMENT_COMPONENTS + ACCOUNTABILITY_COMPONENTS
    + CONSEQUENCE_BASE_COMPONENTS + CLINICAL_COMPONENTS
)


async def load_phase5_dependencies(
    connection: asyncpg.Connection,
    namespace_version: str,
    mapping_run_version: str = MAPPING_RUN_VERSION,
) -> dict[str, Any]:
    dependencies = await load_dependencies(
        connection,
        "phase4a-2026q3-v1",
        task_formula_versions=TASK_FORMULAS,
        occupation_formula_version=OCCUPATION_FORMULA,
    )
    namespace = await connection.fetchrow(
        "SELECT * FROM phase5_candidate_namespaces WHERE namespace_version=$1", namespace_version
    )
    if namespace is None:
        raise ValueError(f"Missing Phase 5 namespace {namespace_version}")
    mapping_run_id = await connection.fetchval(
        "SELECT id FROM ai_generated_task_mapping_runs WHERE run_version=$1", mapping_run_version
    )
    if mapping_run_id is None:
        raise ValueError("Phase 5 mapping scope has no completed mapping run")
    occupations = [
        dict(row)
        for row in await connection.fetch(
            """
            SELECT candidate.*,candidate.title_snapshot source_title,'[]'::jsonb warnings
            FROM phase5_candidate_occupations candidate
            WHERE candidate.namespace_id=$1 ORDER BY candidate.cohort_order
            """,
            namespace["id"],
        )
    ]
    tasks = [
        dict(row)
        for row in await connection.fetch(
            """
            SELECT task.*,candidate.id pilot_occupation_id,scope.ai_task_mapping_id mapping_id,
                   mapping.mapping_confidence,mapping.ambiguity_state,
                   (scope.ai_task_mapping_id IS NOT NULL) scoring_eligible,
                   scope.mapping_run_id,scope.scope_decision,scope.dependency_reuse_key
            FROM phase5_candidate_occupations candidate
            JOIN onet_tasks task ON task.occupation_code=candidate.occupation_code AND task.is_current
            JOIN phase5_task_mapping_scope scope
              ON scope.namespace_id=candidate.namespace_id AND scope.onet_task_id=task.task_id
            LEFT JOIN ai_generated_task_mappings mapping ON mapping.id=scope.ai_task_mapping_id
            WHERE candidate.namespace_id=$1
            ORDER BY candidate.cohort_order,task.task_id
            """,
            namespace["id"],
        )
    ]
    mapping_ids = sorted({row["mapping_id"] for row in tasks if row["mapping_id"] is not None})
    requirement_rows = await connection.fetch(
        """
        SELECT requirement.ai_task_mapping_id,definition.slug,definition.name,requirement.weight,
               requirement.required_capability_level,requirement.confidence,requirement.rationale,
               requirement.evidence,requirement.provenance
        FROM ai_generated_task_capability_requirements requirement
        JOIN ai_capability_definitions definition ON definition.id=requirement.capability_definition_id
        WHERE requirement.ai_task_mapping_id=ANY($1::bigint[])
        ORDER BY requirement.ai_task_mapping_id,definition.slug
        """,
        mapping_ids,
    )
    constraint_rows = await connection.fetch(
        """
        SELECT mapped.ai_task_mapping_id,definition.slug,definition.name,mapped.constraint_level,
               mapped.confidence,mapped.rationale,mapped.evidence,mapped.provenance
        FROM ai_generated_task_environment_constraints mapped
        JOIN task_environment_constraint_definitions definition
          ON definition.id=mapped.constraint_definition_id
        WHERE mapped.ai_task_mapping_id=ANY($1::bigint[])
        ORDER BY mapped.ai_task_mapping_id,definition.slug
        """,
        mapping_ids,
    )
    requirements: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in requirement_rows:
        requirements[row["ai_task_mapping_id"]].append({
            "slug": row["slug"], "name": row["name"], "weight": float(row["weight"]),
            "requiredLevel": float(row["required_capability_level"]),
            "mappingConfidence": float(row["confidence"]), "rationale": row["rationale"],
            "evidence": decoded(row["evidence"]),
        })
    constraints: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in constraint_rows:
        constraints[row["ai_task_mapping_id"]].append({
            "slug": row["slug"], "name": row["name"], "level": float(row["constraint_level"]),
            "confidence": float(row["confidence"]), "rationale": row["rationale"],
            "evidence": decoded(row["evidence"]),
        })
    if any(not requirements[mapping_id] for mapping_id in mapping_ids):
        raise ValueError("Phase 5 contains a scoring-eligible mapping without capability requirements")
    dependencies["cohort"] = {
        "id": namespace["id"], "cohort_version": namespace_version,
        "mapping_run_id": mapping_run_id,
    }
    dependencies["namespace"] = dict(namespace)
    dependencies["occupations"] = occupations
    dependencies["tasks"] = tasks
    dependencies["requirements"] = requirements
    dependencies["constraints"] = constraints
    return dependencies


async def load_or_create_anomaly_policy(
    connection: asyncpg.Connection, source_id: int
) -> dict[str, Any]:
    existing = await connection.fetchrow(
        "SELECT * FROM phase5_anomaly_policy_versions WHERE policy_version=$1", POLICY_VERSION
    )
    if existing:
        return dict(existing)
    implementation_hash = hashlib.sha256(Path(__file__).with_name("phase5_analysis.py").read_bytes()).hexdigest()
    policy_id = await connection.fetchval(
        """
        INSERT INTO phase5_anomaly_policy_versions (
          policy_version,name,status,thresholds,checks,implementation_hash,source_id,provenance,created_by
        ) VALUES ($1,'JobsVsAI Phase 5 corpus anomaly policy','candidate',$2,$3,$4,$5,$6,
          'system:phase5-anomaly-policy') RETURNING id
        """,
        POLICY_VERSION,
        dumps(THRESHOLDS),
        dumps(CHECKS),
        implementation_hash,
        source_id,
        dumps({"phase": "5", "individualOccupationTuning": False, "public": False}),
    )
    return {"id": policy_id, "policy_version": POLICY_VERSION,
            "implementation_hash": implementation_hash}


async def load_or_create_proxies(
    connection: asyncpg.Connection,
    dependencies: dict[str, Any],
    source_id: int,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    namespace_id = dependencies["namespace"]["id"]
    base_model_row = await connection.fetchrow(
        "SELECT * FROM phase4b_proxy_model_versions WHERE model_version=$1", PROXY_MODEL
    )
    direct_model_row = await connection.fetchrow(
        "SELECT * FROM phase4d_proxy_model_versions WHERE model_version=$1", PHASE4D_MODEL
    )
    if base_model_row is None or direct_model_row is None:
        raise ValueError("Approved Phase 4B/4D proxy versions are missing")
    base_model = dict(base_model_row)
    base_model["parameters"] = decoded(base_model["parameters"])
    direct_model = dict(direct_model_row)
    source_keys = collect_source_keys(base_model["parameters"])
    source_keys.update(
        (item["elementType"], item["elementId"], item["scaleId"])
        for item in ALL_DIRECT_COMPONENTS if item["kind"] == "element"
    )
    occupation_codes = [row["occupation_code"] for row in dependencies["occupations"]]
    rating_rows = await connection.fetch(
        """
        SELECT rating.occupation_code,rating.element_type,rating.element_id,rating.scale_id,
               rating.normalized_value,rating.sample_size,rating.standard_error,
               rating.recommend_suppress,rating.not_relevant,rating.source_version,
               rating.source_record_id,rating.row_hash,element.element_name
        FROM onet_element_ratings rating
        JOIN onet_elements element ON element.element_type=rating.element_type
          AND element.element_id=rating.element_id AND element.is_current
        WHERE rating.is_current AND rating.occupation_code=ANY($1::text[])
          AND rating.element_id=ANY($2::text[])
        ORDER BY rating.occupation_code,rating.element_type,rating.element_id,rating.scale_id
        """,
        occupation_codes,
        sorted({key[1] for key in source_keys}),
    )
    ratings_by_code: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = defaultdict(dict)
    for row in rating_rows:
        key = (row["element_type"], row["element_id"], row["scale_id"])
        if key not in source_keys:
            continue
        ratings_by_code[row["occupation_code"]][key] = {
            "normalizedValue": float(row["normalized_value"]), "sampleSize": row["sample_size"],
            "standardError": float(row["standard_error"]) if row["standard_error"] is not None else None,
            "recommendSuppress": row["recommend_suppress"], "notRelevant": row["not_relevant"],
            "sourceVersion": row["source_version"], "sourceRecordId": row["source_record_id"],
            "rowHash": row["row_hash"], "elementName": row["element_name"],
        }
    tasks_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in dependencies["tasks"]:
        source_weight = (
            float(task["importance_score"] * task["frequency_score"])
            if task["weighting_eligible"] else None
        )
        tasks_by_code[task["occupation_code"]].append({
            "taskId": task["task_id"], "statement": task["statement"],
            "sourceWeight": source_weight, "rowHash": task["row_hash"],
            "sourceVersion": task["source_version"],
        })

    snapshots: dict[int, dict[str, Any]] = {}
    for index, occupation in enumerate(dependencies["occupations"], 1):
        existing = await connection.fetchrow(
            """
            SELECT * FROM phase5_proxy_snapshots
            WHERE namespace_id=$1 AND candidate_occupation_id=$2
            """,
            namespace_id,
            occupation["id"],
        )
        if existing:
            snapshot = dict(existing)
            for key in ("family_values", "component_contributions", "exact_inputs", "warnings",
                        "reconciliation", "provisional_flags"):
                snapshot[key] = decoded(snapshot[key])
            snapshots[occupation["id"]] = snapshot
            continue
        code = occupation["occupation_code"]
        ratings = ratings_by_code[code]
        base = occupation_proxies(ratings, base_model["parameters"])
        direct = direct_structural_proxies(ratings, tasks_by_code[code])
        domains = copy.deepcopy(base["domains"])
        for family, value in direct["families"].items():
            domains[family] = {
                "name": family, "value": float(value["value"]),
                "confidence": float(value["confidence"]), "components": value["components"],
                "reconciliation": value["reconciliation"],
            }
        proxy_confidence = min(float(base["confidence"]), float(direct["confidence"]))
        warnings = [
            *base["warnings"], *direct["warnings"],
            {"code": "provisional_regulation_model", "version": PROXY_MODEL},
            {"code": "provisional_adoption_pressure_model", "version": PROXY_MODEL},
            {"code": "provisional_labour_market_resilience_model", "version": PROXY_MODEL},
        ]
        reconciliation = {
            "baseProxyPassed": base["reconciliation"]["passed"],
            "phase4dDirectProxyPassed": direct["reconciliation"]["passed"],
            "familiesPassed": direct["reconciliation"]["familiesPassed"],
            "passed": base["reconciliation"]["passed"] and direct["reconciliation"]["passed"],
        }
        exact_inputs = {
            "phase": "5", "namespaceVersion": dependencies["namespace"]["namespace_version"],
            "occupationCode": code, "sourceVersion": "O*NET 30.3",
            "phase4dProxyModel": PHASE4D_MODEL, "phase4dFormulaVersions": FAMILY_VERSIONS,
            "baseProxyModel": PROXY_MODEL,
            "sourceRecordHashes": sorted(value["rowHash"] for value in ratings.values() if value.get("rowHash")),
            "taskRecordHashes": sorted(task["rowHash"] for task in tasks_by_code[code]),
            "missingDataPolicy": "exclude and renormalize observed values; never invent or impute",
            "prohibitedInputs": ["occupation_scores", "task_scores", "target_distributions",
                                 "occupation_title", "archetype_membership"],
        }
        provisional_flags = {
            "regulation": {"provisional": True, "version": PROXY_MODEL, "uncertaintyExposed": True},
            "adoption-pressure": {"provisional": True, "version": PROXY_MODEL, "uncertaintyExposed": True},
            "labour-market-resilience": {"provisional": True, "version": PROXY_MODEL, "uncertaintyExposed": True},
        }
        contributions = {
            "domains": domains,
            "adoptionPressure": base["adoptionPressure"],
            "labourMarketResilience": base["labourMarketResilience"],
        }
        snapshot_id = await connection.fetchval(
            """
            INSERT INTO phase5_proxy_snapshots (
              namespace_id,candidate_occupation_id,phase4d_proxy_model_version_id,
              base_proxy_model_version_id,physical_presence,environment_variability,
              accountability,consequence_severity,human_dependency,regulation,adoption_pressure,
              labour_market_resilience,proxy_confidence,family_values,component_contributions,
              exact_inputs,warnings,reconciliation,provisional_flags,input_hash,source_id,
              provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,
              'system:phase5-proxy-calculator') RETURNING id
            """,
            namespace_id, occupation["id"], direct_model["id"], base_model["id"],
            direct["families"]["physical-presence"]["value"],
            direct["families"]["environment-variability"]["value"],
            direct["families"]["accountability"]["value"],
            direct["families"]["consequence-severity"]["value"],
            domains["human-dependency"]["value"], domains["regulation"]["value"],
            base["adoptionPressure"]["value"], base["labourMarketResilience"]["value"],
            proxy_confidence, dumps(direct["families"]), dumps(contributions), dumps(exact_inputs),
            dumps(warnings), dumps(reconciliation), dumps(provisional_flags), canonical_hash(exact_inputs),
            source_id, dumps({"phase": "5", "bounded": True, "production": False,
                              "archetypeScoring": False, "noImputation": True}),
        )
        snapshots[occupation["id"]] = {
            "id": snapshot_id, "namespace_id": namespace_id,
            "candidate_occupation_id": occupation["id"],
            "adoption_pressure": base["adoptionPressure"]["value"],
            "labour_market_resilience": base["labourMarketResilience"]["value"],
            "proxy_confidence": proxy_confidence,
            "family_values": direct["families"], "component_contributions": contributions,
            "exact_inputs": exact_inputs, "warnings": warnings, "reconciliation": reconciliation,
            "provisional_flags": provisional_flags, "input_hash": canonical_hash(exact_inputs),
        }
        if index % 100 == 0:
            print(f"Persisted {index}/{len(dependencies['occupations'])} Phase 5 proxy snapshots", flush=True)
    return snapshots, base_model


def provisional_sensitivity(
    occupation: dict[str, Any],
    tasks: list[dict[str, Any]],
    proxy: dict[str, Any],
    dependencies: dict[str, Any],
) -> dict[str, Any]:
    weighted = [task for task in tasks if task["weightingEligible"]]
    covered_weight = sum(float(task["sourceWeight"]) for task in weighted)
    task_parameters = dependencies["formulas"]["automation_feasibility"]["parameters"]
    augmentation_parameters = dependencies["formulas"]["augmentation_potential"]["parameters"]
    occupation_parameters = dependencies["occupationFormula"]["parameters"]
    exposure_weights = occupation_parameters["taskExposureWeights"]
    replacement_weights = occupation_parameters["replacementWeights"]
    regulation_task_automation = 0.0
    regulation_ai_exposure = 0.0
    for task in weighted:
        domains = copy.deepcopy(proxy["component_contributions"]["domains"])
        domains["regulation"] = {**domains["regulation"], "value": 50.0}
        consolidated = consolidated_constraints(
            dependencies["constraints"][task["mappingId"]], {"domains": domains}, task_parameters
        )
        automation = automation_feasibility_v2(task["fit"]["score"], consolidated, task_parameters)
        augmentation = augmentation_potential_v2(
            task["fit"]["score"], automation["score"], augmentation_parameters
        )
        exposure = rounded(
            float(exposure_weights["aiCapabilityFit"]) * task["fit"]["score"]
            + float(exposure_weights["automationFeasibility"]) * automation["score"]
            + float(exposure_weights["augmentationPotential"]) * augmentation["score"]
        )
        normalized = float(task["sourceWeight"]) / covered_weight
        regulation_task_automation += normalized * float(automation["score"])
        regulation_ai_exposure += normalized * float(exposure)
    actual_task_automation = next(
        float(item["value"]) for item in occupation["factors"]
        if item["factor"] == "taskAutomationExposure"
    )
    regulation_replacement = rounded(
        float(occupation["replacementRisk"])
        - float(replacement_weights["taskAutomationExposure"])
          * (actual_task_automation - regulation_task_automation)
    )
    adoption = float(proxy["adoption_pressure"])
    resilience = float(proxy["labour_market_resilience"])
    adoption_replacement = rounded(
        float(occupation["replacementRisk"])
        - float(replacement_weights["adoptionPressure"]) * (adoption - 50.0)
    )
    labour_replacement = rounded(
        float(occupation["replacementRisk"])
        - float(replacement_weights["labourMarketResilienceResistance"]) * (50.0 - resilience)
    )
    impacts = {
        "regulationNeutralAiExposureDelta": rounded(regulation_ai_exposure - float(occupation["aiExposure"])),
        "regulationNeutralReplacementRiskDelta": rounded(regulation_replacement - float(occupation["replacementRisk"])),
        "adoptionNeutralReplacementRiskDelta": rounded(adoption_replacement - float(occupation["replacementRisk"])),
        "labourNeutralReplacementRiskDelta": rounded(labour_replacement - float(occupation["replacementRisk"])),
    }
    return {
        "method": "one-at-a-time deterministic neutral-50 counterfactual",
        "provisionalVersions": {"regulation": PROXY_MODEL, "adoptionPressure": PROXY_MODEL,
                                "labourMarketResilience": PROXY_MODEL},
        **impacts,
        "maximumAbsoluteScoreImpact": rounded(max(abs(value) for value in impacts.values())),
    }


def enrich_outputs(
    tasks: list[dict[str, Any]],
    occupations: list[dict[str, Any]],
    proxies: dict[int, dict[str, Any]],
    dependencies: dict[str, Any],
) -> list[dict[str, Any]]:
    tasks_by_occupation: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        tasks_by_occupation[task["pilotOccupationId"]].append(task)
    enriched: list[dict[str, Any]] = []
    for occupation in occupations:
        occupation_id = occupation["pilotOccupationId"]
        proxy = proxies[occupation_id]
        occupation_tasks = tasks_by_occupation[occupation_id]
        covered_weight = sum(task["sourceWeight"] for task in occupation_tasks if task["weightingEligible"])
        constraint_totals: dict[str, dict[str, Any]] = {}
        augmentation_rows = []
        for task in occupation_tasks:
            if not task["weightingEligible"]:
                continue
            normalized = task["sourceWeight"] / covered_weight
            augmentation_rows.append({
                "onetTaskId": task["taskId"], "statement": task["statement"],
                "augmentationPotential": task["augmentation"]["score"],
                "normalizedCoveredWeight": rounded(normalized),
                "weightedAugmentationContribution": rounded(normalized * task["augmentation"]["score"]),
            })
            for contribution in task["automation"]["contributions"]:
                row = constraint_totals.setdefault(contribution["slug"], {
                    "constraint": contribution["slug"], "weightedBurdenContribution": 0.0,
                    "weightedLevel": 0.0, "sourceCounts": defaultdict(int),
                })
                row["weightedBurdenContribution"] += normalized * float(contribution["burdenContribution"])
                row["weightedLevel"] += normalized * float(contribution["level"])
                row["sourceCounts"][contribution["source"]] += 1
        top_constraints = [
            {"constraint": row["constraint"],
             "weightedBurdenContribution": rounded(row["weightedBurdenContribution"]),
             "weightedLevel": rounded(row["weightedLevel"]),
             "sourceCounts": dict(row["sourceCounts"])}
            for row in sorted(constraint_totals.values(),
                              key=lambda value: value["weightedBurdenContribution"], reverse=True)[:8]
        ]
        sensitivity = provisional_sensitivity(occupation, occupation_tasks, proxy, dependencies)
        confidence_passed = occupation["confidence"] >= float(
            dependencies["occupationFormula"]["parameters"]["minimumScaleConfidence"]
        )
        blocking_reasons = []
        if occupation["coverageGateStatus"] != "passed":
            blocking_reasons.append({"code": "weighted_coverage_below_70",
                                     "coverage": occupation["coverage"], "threshold": 70})
        if not confidence_passed:
            blocking_reasons.append({"code": "confidence_below_scale_threshold",
                                     "confidence": occupation["confidence"], "threshold": 70})
        proxy_values = {
            "physical-presence": float(proxy["family_values"]["physical-presence"]["value"]),
            "environment-variability": float(proxy["family_values"]["environment-variability"]["value"]),
            "accountability": float(proxy["family_values"]["accountability"]["value"]),
            "consequence-severity": float(proxy["family_values"]["consequence-severity"]["value"]),
            "human-dependency": float(proxy["component_contributions"]["domains"]["human-dependency"]["value"]),
            "regulation": float(proxy["component_contributions"]["domains"]["regulation"]["value"]),
            "adoption-pressure": float(proxy["adoption_pressure"]),
            "labour-market-resilience": float(proxy["labour_market_resilience"]),
        }
        structural = {
            "proxySnapshotId": proxy["id"], "proxyInputHash": proxy["input_hash"],
            "phase4dProxyModel": PHASE4D_MODEL, "phase4dFormulaVersions": FAMILY_VERSIONS,
            "baseProxyModel": PROXY_MODEL, "values": proxy_values,
            "provisionalFlags": proxy["provisional_flags"],
            "missingDataPolicy": proxy["exact_inputs"]["missingDataPolicy"],
        }
        enriched.append({
            **occupation,
            "candidateOccupationId": occupation_id,
            "calculationStatus": "scored",
            "confidenceGateStatus": "passed" if confidence_passed else "below_threshold",
            "candidateStatus": "review_ready" if occupation["scaleEligible"] else "blocked",
            "topExposureTasks": occupation["tasks"][:5],
            "topAutomationConstraints": top_constraints,
            "augmentationHeavyTasks": sorted(
                augmentation_rows, key=lambda row: row["weightedAugmentationContribution"], reverse=True
            )[:5],
            "structuralProxyInputs": structural,
            "proxyValues": proxy_values,
            "provisionalSensitivity": sensitivity,
            "blockingReasons": blocking_reasons,
            "warnings": [
                *occupation["warnings"],
                {"code": "provisional_regulation_model", "version": PROXY_MODEL},
                {"code": "provisional_adoption_pressure_model", "version": PROXY_MODEL},
                {"code": "provisional_labour_market_resilience_model", "version": PROXY_MODEL},
                {"code": "candidate_only_not_public_or_production"},
            ],
        })
    return enriched


def current_signature(
    tasks: list[dict[str, Any]], occupations: list[dict[str, Any]],
    anomalies: list[dict[str, Any]], report_hash: str,
) -> dict[str, Any]:
    return {
        "tasks": [
            {"taskId": row["taskId"], "fit": row["fit"]["score"],
             "automation": row["automation"]["score"], "augmentation": row["augmentation"]["score"],
             "exposure": row["taskExposure"], "confidence": row["confidence"], "inputHash": row["inputHash"]}
            for row in sorted(tasks, key=lambda item: item["taskId"])
        ],
        "occupations": [
            {"candidateOccupationId": row["candidateOccupationId"], "aiExposure": row["aiExposure"],
             "replacementRisk": row["replacementRisk"], "confidence": row["confidence"],
             "coverage": row["coverage"], "candidateStatus": row["candidateStatus"],
             "inputHash": row["inputHash"], "provisionalSensitivity": row["provisionalSensitivity"]}
            for row in sorted(occupations, key=lambda item: item["candidateOccupationId"])
        ],
        "anomalyHashes": sorted(row["inputHash"] for row in anomalies),
        "reportHash": report_hash,
    }


async def persisted_signature(connection: asyncpg.Connection, run_id: int) -> dict[str, Any]:
    tasks = await connection.fetch(
        """
        SELECT onet_task_id,ai_capability_fit,automation_feasibility,augmentation_potential,
               task_ai_exposure,confidence,input_hash
        FROM phase5_task_assessments WHERE calculation_run_id=$1 ORDER BY onet_task_id
        """, run_id,
    )
    occupations = await connection.fetch(
        """
        SELECT candidate_occupation_id,ai_exposure,replacement_risk,confidence,
               weighted_task_coverage,candidate_status,input_hash,provisional_sensitivity
        FROM phase5_occupation_scores WHERE calculation_run_id=$1 ORDER BY candidate_occupation_id
        """, run_id,
    )
    anomaly_hashes = await connection.fetch(
        "SELECT input_hash FROM phase5_anomaly_findings WHERE calculation_run_id=$1 ORDER BY input_hash", run_id
    )
    report_hash = await connection.fetchval(
        "SELECT input_hash FROM phase5_corpus_reports WHERE calculation_run_id=$1", run_id
    )
    return {
        "tasks": [
            {"taskId": row["onet_task_id"], "fit": float(row["ai_capability_fit"]),
             "automation": float(row["automation_feasibility"]),
             "augmentation": float(row["augmentation_potential"]),
             "exposure": float(row["task_ai_exposure"]), "confidence": float(row["confidence"]),
             "inputHash": row["input_hash"]}
            for row in tasks
        ],
        "occupations": [
            {"candidateOccupationId": row["candidate_occupation_id"],
             "aiExposure": float(row["ai_exposure"]), "replacementRisk": float(row["replacement_risk"]),
             "confidence": float(row["confidence"]), "coverage": float(row["weighted_task_coverage"]),
             "candidateStatus": row["candidate_status"], "inputHash": row["input_hash"],
             "provisionalSensitivity": decoded(row["provisional_sensitivity"])}
            for row in occupations
        ],
        "anomalyHashes": [row["input_hash"] for row in anomaly_hashes],
        "reportHash": report_hash,
    }


async def run(
    run_version: str,
    run_kind: str,
    previous_run_version: str | None,
    namespace_version: str = NAMESPACE_VERSION,
    mapping_run_version: str = MAPPING_RUN_VERSION,
    mapping_scope_version: str = MAPPING_SCOPE_VERSION,
) -> dict[str, Any]:
    started = time.perf_counter()
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        existing = await connection.fetchrow(
            "SELECT * FROM phase5_calculation_runs WHERE run_version=$1", run_version
        )
        if existing:
            await transaction.commit()
            return {"calculationRunId": existing["id"], "runVersion": run_version,
                    "replayMatchesPrevious": existing["replay_matches_previous"], "reused": True}
        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 5 bounded corpus scoring'"
        )
        production_before = await connection.fetchrow(
            """SELECT (SELECT count(*) FROM occupation_scores) occupation_rows,
                      (SELECT count(*) FROM task_ai_scores) task_rows,
                      (SELECT count(*) FROM occupation_publications WHERE activation_status='public') public_rows,
                      (SELECT enabled FROM scoring_enrichment_feature_flags
                       WHERE flag_key='occupational_archetype_layer') archetype_enabled"""
        )
        dependencies = await load_phase5_dependencies(connection, namespace_version, mapping_run_version)
        anomaly_policy = await load_or_create_anomaly_policy(connection, source_id)
        proxies, proxy_model = await load_or_create_proxies(connection, dependencies, source_id)
        task_results, occupation_results = calculate(
            dependencies, proxies, proxy_model, methodology_phase="5",
            mapping_scope_version=mapping_scope_version,
        )
        if len(occupation_results) != dependencies["namespace"]["occupation_population_count"]:
            raise ValueError("Phase 5 did not calculate the frozen scoring-ready population")
        if not all(row["reconciliation"]["passed"] for row in task_results + occupation_results):
            raise ValueError("Phase 5 contribution reconciliation failed")
        enriched = enrich_outputs(task_results, occupation_results, proxies, dependencies)
        mapping_counts_row = await connection.fetchrow(
            """
            SELECT count(*) FILTER (WHERE scope_decision='generated') new_mappings,
                   count(*) FILTER (WHERE scope_decision='reused_exact_task') reused_exact_mappings,
                   count(*) FILTER (WHERE scope_decision='reused_task_hash') reused_hash_mappings,
                   count(*) FILTER (WHERE scope_decision='unmapped_insufficient_evidence') insufficient_descriptions,
                   count(*) FILTER (WHERE scope_decision='unmapped_after_gate') unmapped_after_gate,
                   count(*) FILTER (WHERE scope_decision='source_weight_ineligible') source_weight_ineligible,
                   count(*) total_scope_rows
            FROM phase5_task_mapping_scope WHERE namespace_id=$1
            """, dependencies["namespace"]["id"],
        )
        mapping_counts = {key: int(value) for key, value in dict(mapping_counts_row).items()}
        total_source_occupations = await connection.fetchval(
            "SELECT count(*) FROM onet_occupations WHERE is_current"
        )
        anomalies, report = analyze(enriched, total_source_occupations, mapping_counts, 0, 0)
        mapping_compute_ms = await connection.fetchval(
            """
            SELECT round(extract(epoch FROM (min(scope.created_at)-run.created_at))*1000)::bigint
            FROM ai_generated_task_mapping_runs run
            JOIN phase5_task_mapping_scope scope ON scope.namespace_id=$1
            WHERE run.run_version=$2 GROUP BY run.created_at
            """, dependencies["namespace"]["id"], mapping_run_version,
        )
        report["mappingReuseSummary"]["mappingComputeMillisecondsEstimate"] = int(
            mapping_compute_ms or round(mapping_counts["new_mappings"] * 2.14)
        )
        report_payload_hash = canonical_hash(report)
        previous = None
        replay_matches = None
        if previous_run_version:
            previous = await connection.fetchrow(
                "SELECT * FROM phase5_calculation_runs WHERE run_version=$1", previous_run_version
            )
            if previous is None:
                raise ValueError(f"Unknown prior Phase 5 run {previous_run_version}")
        current = current_signature(task_results, enriched, anomalies, report_payload_hash)
        if run_kind == "deterministic_replay":
            replay_matches = canonical_hash(await persisted_signature(connection, previous["id"])) == canonical_hash(current)
            if not replay_matches:
                raise ValueError("Phase 5 deterministic replay mismatch")
        scope_hashes = await connection.fetch(
            "SELECT input_hash FROM phase5_task_mapping_scope WHERE namespace_id=$1 ORDER BY onet_task_id",
            dependencies["namespace"]["id"],
        )
        dependency_manifest = {
            "phase": "5", "namespaceVersion": namespace_version,
            "populationHash": dependencies["namespace"]["occupation_population_hash"],
            "mappingScopeVersion": mapping_scope_version,
            "mappingScopeHash": canonical_hash([row["input_hash"] for row in scope_hashes]),
            "formulaVersions": {key: value["formula_version"] for key, value in dependencies["formulas"].items()},
            "occupationFormula": dependencies["occupationFormula"]["formula_version"],
            "frontierIndexVersion": dependencies["track"]["index_version"],
            "frontierTrack": dependencies["track"]["track_code"],
            "phase4dProxyModel": PHASE4D_MODEL,
            "baseProxyModel": PROXY_MODEL,
            "anomalyPolicy": POLICY_VERSION,
            "proxyHashes": [proxies[key]["input_hash"] for key in sorted(proxies)],
            "taskInputHashes": [row["inputHash"] for row in sorted(task_results, key=lambda item: item["taskId"])],
        }
        local_compute_ms = round((time.perf_counter() - started) * 1000)
        review_ready = sum(row["candidateStatus"] == "review_ready" for row in enriched)
        blocked = len(enriched) - review_ready
        run_id = await connection.fetchval(
            """
            INSERT INTO phase5_calculation_runs (
              namespace_id,run_version,run_kind,previous_run_id,anomaly_policy_version_id,mapping_run_id,
              capability_fit_formula_id,automation_formula_id,augmentation_formula_id,occupation_formula_id,
              frontier_track_id,attempted_occupation_count,scored_occupation_count,blocked_occupation_count,
              task_assessment_count,new_mapping_count,reused_exact_mapping_count,reused_hash_mapping_count,
              external_ai_calls,estimated_ai_tokens,local_compute_milliseconds,dependency_hash,
              reconciliation_status,replay_matches_previous,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,0,0,$19,$20,
              'passed',$21,$22,$23,'system:phase5-candidate-scorer') RETURNING id
            """,
            dependencies["namespace"]["id"], run_version, run_kind,
            previous["id"] if previous else None, anomaly_policy["id"],
            dependencies["cohort"]["mapping_run_id"],
            dependencies["formulas"]["capability_fit"]["id"],
            dependencies["formulas"]["automation_feasibility"]["id"],
            dependencies["formulas"]["augmentation_potential"]["id"],
            dependencies["occupationFormula"]["id"], dependencies["track"]["id"],
            len(enriched), review_ready, blocked, len(task_results), mapping_counts["new_mappings"],
            mapping_counts["reused_exact_mappings"], mapping_counts["reused_hash_mappings"],
            local_compute_ms, canonical_hash(dependency_manifest), replay_matches, source_id,
            dumps({"phase": "5", "bounded": True, "candidateOnly": True,
                   "publicActivations": 0, "productionScoreWrites": 0, "externalAiCalls": 0,
                   "estimatedAiTokens": 0, "archetypeScoring": False,
                   "productionBefore": dict(production_before), "dependencyManifest": dependency_manifest}),
        )
        await connection.executemany(
            """
            INSERT INTO phase5_task_assessments (
              calculation_run_id,candidate_occupation_id,onet_task_id,ai_task_mapping_id,
              ai_capability_fit,automation_feasibility,augmentation_potential,task_ai_exposure,
              confidence,source_weight,capability_contributions,constraint_contributions,
              exact_inputs,warnings,reconciliation,input_hash,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
            """,
            [(
                run_id, row["pilotOccupationId"], row["taskId"], row["mappingId"],
                row["fit"]["score"], row["automation"]["score"], row["augmentation"]["score"],
                row["taskExposure"], row["confidence"], row["sourceWeight"],
                dumps(row["fit"]["contributions"]), dumps(row["automation"]["contributions"]),
                dumps(row["exactInputs"]), dumps(row["warnings"]), dumps(row["reconciliation"]),
                row["inputHash"], source_id,
                dumps({"phase": "5", "bounded": True, "candidateOnly": True,
                       "formulaRun": run_version}), "system:phase5-candidate-scorer",
            ) for row in task_results],
        )
        await connection.executemany(
            """
            INSERT INTO phase5_occupation_scores (
              calculation_run_id,candidate_occupation_id,proxy_snapshot_id,calculation_status,
              ai_exposure,replacement_risk,confidence,weighted_task_coverage,source_task_count,
              eligible_task_count,excluded_task_count,weighting_eligible_task_count,
              coverage_gate_status,confidence_gate_status,candidate_status,top_exposure_tasks,
              top_automation_constraints,augmentation_heavy_tasks,structural_proxy_inputs,
              provisional_sensitivity,factor_contributions,task_contributions,exact_inputs,
              warnings,blocking_reasons,reconciliation,input_hash,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,'scored',$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,
              $20,$21,$22,$23,$24,$25,$26,$27,$28,$29)
            """,
            [(
                run_id, row["candidateOccupationId"], row["proxySnapshotId"], row["aiExposure"],
                row["replacementRisk"], row["confidence"], row["coverage"], row["sourceTaskCount"],
                row["mappedTaskCount"], row["excludedTaskCount"], row["weightingEligibleTaskCount"],
                row["coverageGateStatus"], row["confidenceGateStatus"], row["candidateStatus"],
                dumps(row["topExposureTasks"]), dumps(row["topAutomationConstraints"]),
                dumps(row["augmentationHeavyTasks"]), dumps(row["structuralProxyInputs"]),
                dumps(row["provisionalSensitivity"]), dumps(row["factors"]), dumps(row["tasks"]),
                dumps(row["exactInputs"]), dumps(row["warnings"]), dumps(row["blockingReasons"]),
                dumps(row["reconciliation"]), row["inputHash"], source_id,
                dumps({"phase": "5", "candidateOnly": True, "public": False,
                       "production": False, "formulaRun": run_version}),
                "system:phase5-candidate-scorer",
            ) for row in enriched],
        )
        if anomalies:
            await connection.executemany(
                """
                INSERT INTO phase5_anomaly_findings (
                  calculation_run_id,candidate_occupation_id,anomaly_type,severity,metric_values,
                  threshold_values,explanation,input_hash,source_id,provenance,created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'system:phase5-anomaly-checker')
                """,
                [(
                    run_id, row["candidateOccupationId"], row["anomalyType"], row["severity"],
                    dumps(row["metricValues"]), dumps(row["thresholdValues"]), row["explanation"],
                    row["inputHash"], source_id,
                    dumps({"phase": "5", "policyVersion": POLICY_VERSION,
                           "individualOccupationTuning": False}),
                ) for row in anomalies],
            )
        exact_reconciliation = {
            "taskAssessments": len(task_results), "occupationCalculations": len(enriched),
            "taskReconciliationFailures": sum(not row["reconciliation"]["passed"] for row in task_results),
            "occupationReconciliationFailures": sum(not row["reconciliation"]["passed"] for row in enriched),
            "coverageGateViolations": sum(row["coverage"] < 70 and row["candidateStatus"] != "blocked" for row in enriched),
            "publicActivations": 0, "productionScoreWrites": 0,
            "archetypeScoringEnabled": False, "deterministicReplay": replay_matches,
            "passed": True,
        }
        await connection.execute(
            """
            INSERT INTO phase5_corpus_reports (
              calculation_run_id,report_version,corpus_summary,distributions,percentiles,correlation,
              extremes,soc_outliers,provisional_impact,anomaly_summary,mapping_reuse_summary,
              recommended_launch_cohort,exact_reconciliation,input_hash,source_id,provenance,created_by
            ) VALUES ($1,'phase5-corpus-report-v1',$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
              'system:phase5-corpus-reporter')
            """,
            run_id, dumps(report["corpusSummary"]), dumps(report["distributions"]),
            dumps(report["percentiles"]), dumps(report["correlation"]), dumps(report["extremes"]),
            dumps(report["socOutliers"]), dumps(report["provisionalImpact"]),
            dumps(report["anomalySummary"]), dumps(report["mappingReuseSummary"]),
            dumps(report["recommendedLaunchCohort"]), dumps(exact_reconciliation),
            report_payload_hash, source_id,
            dumps({"phase": "5", "candidateOnly": True, "publicActivated": False,
                   "productionScoreWrites": 0, "runVersion": run_version}),
        )
        production_after = await connection.fetchrow(
            """SELECT (SELECT count(*) FROM occupation_scores) occupation_rows,
                      (SELECT count(*) FROM task_ai_scores) task_rows,
                      (SELECT count(*) FROM occupation_publications WHERE activation_status='public') public_rows,
                      (SELECT enabled FROM scoring_enrichment_feature_flags
                       WHERE flag_key='occupational_archetype_layer') archetype_enabled"""
        )
        if dict(production_before) != dict(production_after):
            raise ValueError("Phase 5 isolation violation: production/public state changed")
        await transaction.commit()
        return {
            "calculationRunId": run_id, "runVersion": run_version, "runKind": run_kind,
            "attemptedOccupations": len(enriched), "candidateCalculations": len(enriched),
            "reviewReadyOccupations": review_ready, "blockedOccupations": blocked,
            "coverageBlockedOccupations": report["corpusSummary"]["coverageBlockedOccupations"],
            "confidenceBlockedOccupations": report["corpusSummary"]["confidenceBlockedOccupations"],
            "taskAssessments": len(task_results), "mappingReuse": report["mappingReuseSummary"],
            "anomalies": report["anomalySummary"],
            "recommendedLaunchCohort": report["recommendedLaunchCohort"]["recommendedCount"],
            "externalAiCalls": 0, "estimatedAiTokens": 0,
            "localComputeMilliseconds": local_compute_ms,
            "replayMatchesPrevious": replay_matches, "reconciliation": exact_reconciliation,
            "productionIsolation": dict(production_after), "reused": False,
        }
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-version", required=True)
    parser.add_argument("--run-kind", choices=["bounded_corpus", "deterministic_replay"], required=True)
    parser.add_argument("--previous-run-version")
    parser.add_argument("--namespace-version", default=NAMESPACE_VERSION)
    args = parser.parse_args()
    print(json.dumps(await run(args.run_version, args.run_kind, args.previous_run_version,
                               args.namespace_version), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
