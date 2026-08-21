"""Run the bounded Phase 4D direct structural proxy reconstruction."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import asyncpg

try:
    from .phase4d_proxies import (
        ACCOUNTABILITY_COMPONENTS,
        CLINICAL_COMPONENTS,
        CONSEQUENCE_BASE_COMPONENTS,
        ENVIRONMENT_COMPONENTS,
        FAMILY_VERSIONS,
        FORMULA_PARAMETERS,
        MODEL_VERSION,
        PHYSICAL_COMPONENTS,
        direct_structural_proxies,
    )
    from .pilot import canonical_hash
    from .run_phase4a_pilot import decoded, dumps, plain
    from .run_phase4b_calibration import calculate, output_signature
    from .run_phase4c_validation import database_url, load_or_create_proxies, load_phase4c_dependencies
except ImportError:
    from phase4d_proxies import (
        ACCOUNTABILITY_COMPONENTS, CLINICAL_COMPONENTS, CONSEQUENCE_BASE_COMPONENTS,
        ENVIRONMENT_COMPONENTS, FAMILY_VERSIONS, FORMULA_PARAMETERS, MODEL_VERSION,
        PHYSICAL_COMPONENTS, direct_structural_proxies,
    )
    from pilot import canonical_hash
    from run_phase4a_pilot import decoded, dumps, plain
    from run_phase4b_calibration import calculate, output_signature
    from run_phase4c_validation import database_url, load_or_create_proxies, load_phase4c_dependencies


RUN_VERSION = "phase4d-direct-proxy-recompute-v2-2026q3"
REPLAY_VERSION = "phase4d-direct-proxy-replay-v2-2026q3"
COHORT_VERSION = "phase4c-2026q3-v1"
BASELINE_RUN_VERSION = "phase4c-targeted-validation-v1-2026q3"
FAMILIES = ("physical-presence", "environment-variability", "accountability", "consequence-severity")
ALL_COMPONENTS = (
    PHYSICAL_COMPONENTS + ENVIRONMENT_COMPONENTS + ACCOUNTABILITY_COMPONENTS
    + CONSEQUENCE_BASE_COMPONENTS + CLINICAL_COMPONENTS
)


def absolute_pass(value: float, expectation: str) -> bool:
    if expectation == "high":
        return value >= 60
    if expectation == "low":
        return value <= 40
    if expectation == "medium":
        return 35 <= value <= 65
    if expectation == "medium-high":
        return value >= 50
    raise ValueError(f"Unknown absolute band {expectation}")


def outcome_rank(outcome: str) -> int:
    return {"failure": 0, "warning": 1, "pass": 2}[outcome]


def metric(snapshot: dict[str, Any], name: str) -> float:
    if name == "adoption-pressure":
        return float(snapshot["adoption_pressure"])
    if name == "labour-market-resilience":
        return float(snapshot["labour_market_resilience"])
    return float(snapshot["domain_values"][name]["value"])


async def load_or_create_model(connection: asyncpg.Connection) -> dict[str, Any]:
    existing = await connection.fetchrow(
        "SELECT * FROM phase4d_proxy_model_versions WHERE model_version=$1", MODEL_VERSION
    )
    if existing:
        row = dict(existing)
        row["formula_parameters"] = decoded(row["formula_parameters"])
        return row
    source_id = await connection.fetchval(
        "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4D direct structural proxy reconstruction'"
    )
    implementation_hash = hashlib.sha256(
        (Path(__file__).read_bytes() + Path(__file__).with_name("phase4d_proxies.py").read_bytes())
    ).hexdigest()
    model_id = await connection.fetchval(
        """
        INSERT INTO phase4d_proxy_model_versions (
          model_version,name,description,status,source_version,reconstructed_families,
          formula_parameters,missing_data_policy,implementation_hash,source_id,provenance,created_by
        ) VALUES ($1,'JobsVsAI Phase 4D Direct Structural Proxies',
          'Title-blind O*NET source formulas for the four weak Phase 4C structural families.',
          'pilot','O*NET 30.3',$2,$3,$4,$5,$6,$7,'system:phase4d-proxy-model') RETURNING id
        """, MODEL_VERSION, dumps(list(FAMILIES)), dumps(FORMULA_PARAMETERS),
        dumps({"missing": "exclude_and_renormalize", "suppressed": "exclude_and_penalize_confidence",
               "taskRatings": "exclude_tasks_without_importance_or_frequency_from_weighted_signals",
               "imputation": "prohibited", "inventedValues": False}),
        implementation_hash, source_id,
        dumps({"phase": "4D", "cohortOnly": COHORT_VERSION, "public": False,
               "production": False, "externalAiCalls": 0, "occupationTitleUsed": False,
               "socUsedAsFormulaInput": False, "archetypeScoring": False}),
    )
    return {"id": model_id, "model_version": MODEL_VERSION,
            "formula_parameters": FORMULA_PARAMETERS, "implementation_hash": implementation_hash}


async def load_source_inputs(
    connection: asyncpg.Connection, dependencies: dict[str, Any]
) -> tuple[dict[str, dict[tuple[str, str, str], dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    codes = [row["occupation_code"] for row in dependencies["occupations"]]
    element_ids = sorted({item["elementId"] for item in ALL_COMPONENTS if item["kind"] == "element"})
    rows = await connection.fetch(
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
        """, codes, element_ids,
    )
    ratings: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        ratings[row["occupation_code"]][
            (row["element_type"], row["element_id"], row["scale_id"])
        ] = {
            "normalizedValue": float(row["normalized_value"]), "sampleSize": row["sample_size"],
            "standardError": float(row["standard_error"]) if row["standard_error"] is not None else None,
            "recommendSuppress": row["recommend_suppress"], "notRelevant": row["not_relevant"],
            "sourceVersion": row["source_version"], "sourceRecordId": row["source_record_id"],
            "rowHash": row["row_hash"], "elementName": row["element_name"],
        }
    task_rows = await connection.fetch(
        """
        SELECT task.task_id,task.occupation_code,task.statement,task.importance_score,
               task.frequency_score,task.weighting_eligible,task.row_hash,task.source_version
        FROM onet_tasks task WHERE task.is_current AND task.occupation_code=ANY($1::text[])
        ORDER BY task.occupation_code,task.task_id
        """, codes,
    )
    tasks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        source_weight = (
            float(row["importance_score"] * row["frequency_score"])
            if row["weighting_eligible"] and row["importance_score"] is not None
            and row["frequency_score"] is not None else None
        )
        tasks[row["occupation_code"]].append(
            {"taskId": row["task_id"], "statement": row["statement"],
             "sourceWeight": source_weight, "rowHash": row["row_hash"],
             "sourceVersion": row["source_version"]}
        )
    return dict(ratings), dict(tasks)


async def load_or_create_snapshots(
    connection: asyncpg.Connection,
    dependencies: dict[str, Any],
    base_proxies: dict[int, dict[str, Any]],
    model: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    ratings_by_code, tasks_by_code = await load_source_inputs(connection, dependencies)
    source_id = await connection.fetchval(
        "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4D direct structural proxy reconstruction'"
    )
    snapshots: dict[int, dict[str, Any]] = {}
    for occupation in dependencies["occupations"]:
        occupation_id = occupation["id"]
        code = occupation["occupation_code"]
        existing = await connection.fetchrow(
            "SELECT * FROM phase4d_proxy_snapshots WHERE proxy_model_version_id=$1 AND validation_occupation_id=$2",
            model["id"], occupation_id,
        )
        if existing:
            families = decoded(existing["family_values"])
            exact_inputs = decoded(existing["exact_inputs"])
            warnings = decoded(existing["warnings"])
            reconciliation = decoded(existing["reconciliation"])
            snapshot_id = existing["id"]
        else:
            result = direct_structural_proxies(ratings_by_code[code], tasks_by_code[code])
            families = result["families"]
            exact_inputs = {
                "phase": "4D", "cohortVersion": COHORT_VERSION, "occupationCode": code,
                "proxyModelVersion": MODEL_VERSION, "sourceVersion": "O*NET 30.3",
                "formulaVersions": FAMILY_VERSIONS,
                "families": families,
                "sourceRecordHashes": sorted({
                    component["evidence"].get("rowHash")
                    for family in families.values()
                    for component in family["components"] + family.get("clinicalComponents", [])
                    if component["kind"] == "element" and component["evidence"].get("rowHash")
                }),
                "taskRecordHashes": [task["rowHash"] for task in tasks_by_code[code]],
                "prohibitedInputs": ["occupation_title", "industry", "SOC_category_assumption",
                                     "occupation_scores", "automation_outcomes", "archetype_membership"],
            }
            warnings = result["warnings"]
            reconciliation = result["reconciliation"]
            snapshot_id = await connection.fetchval(
                """
                INSERT INTO phase4d_proxy_snapshots (
                  proxy_model_version_id,validation_occupation_id,physical_presence,
                  environment_variability,accountability,consequence_severity,proxy_confidence,
                  family_values,exact_inputs,warnings,reconciliation,input_hash,source_id,
                  provenance,created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,
                  'system:phase4d-proxy-calculator') RETURNING id
                """, model["id"], occupation_id,
                families["physical-presence"]["value"],
                families["environment-variability"]["value"],
                families["accountability"]["value"], families["consequence-severity"]["value"],
                result["confidence"], dumps(families), dumps(exact_inputs), dumps(warnings),
                dumps(reconciliation), canonical_hash(exact_inputs), source_id,
                dumps({"phase": "4D", "directSource": True, "noImputation": True,
                       "titleBlind": True, "public": False, "production": False}),
            )
        base = base_proxies[occupation_id]
        base_domains = plain(decoded(base["component_contributions"])["domains"])
        domain_values = plain(decoded(base["domain_values"]))
        for family in FAMILIES:
            value = families[family]
            base_domains[family] = {
                "name": family, "value": float(value["value"]),
                "confidence": float(value["confidence"]), "components": value["components"],
                "reconciliation": value["reconciliation"],
            }
            domain_values[family] = {"value": float(value["value"]),
                                     "confidence": float(value["confidence"])}
        proxy_confidence = min(
            float(base["proxy_confidence"]),
            *(float(families[family]["confidence"]) for family in FAMILIES),
        )
        proxy_exact_inputs = {
            "phase": "4D", "phase4dProxySnapshotId": snapshot_id,
            "phase4cBaseProxySnapshotId": base["id"], "reconstructedFamilies": list(FAMILIES),
            "unchangedFamilies": ["human-dependency", "regulation", "adoption-pressure",
                                  "labour-market-resilience"],
            "archetypeScoringEnabled": False,
        }
        snapshots[occupation_id] = {
            "id": snapshot_id,
            "adoption_pressure": float(base["adoption_pressure"]),
            "labour_market_resilience": float(base["labour_market_resilience"]),
            "proxy_confidence": proxy_confidence, "domain_values": domain_values,
            "component_contributions": {
                "domains": base_domains,
                "adoptionPressure": decoded(base["component_contributions"])["adoptionPressure"],
                "labourMarketResilience": decoded(base["component_contributions"])["labourMarketResilience"],
            },
            "exact_inputs": proxy_exact_inputs,
            "warnings": [*warnings, {"code": "unchanged_phase4c_proxy_families",
                                      "families": proxy_exact_inputs["unchangedFamilies"]}],
            "reconciliation": {"directFamiliesPassed": reconciliation["passed"],
                               "unchangedFamiliesCopied": True, "passed": reconciliation["passed"]},
            "input_hash": canonical_hash({"direct": exact_inputs, "overlay": proxy_exact_inputs}),
        }
    return snapshots


async def persisted_signature(connection: asyncpg.Connection, run_id: int) -> dict[str, Any]:
    tasks = await connection.fetch(
        """SELECT onet_task_id,ai_capability_fit,automation_feasibility,augmentation_potential,
                  task_ai_exposure,confidence,input_hash FROM phase4d_task_assessments
           WHERE calculation_run_id=$1 ORDER BY onet_task_id""", run_id,
    )
    occupations = await connection.fetch(
        """SELECT validation_occupation_id pilot_occupation_id,ai_exposure,replacement_risk,
                  confidence,weighted_task_coverage,input_hash FROM phase4d_occupation_scores
           WHERE calculation_run_id=$1 ORDER BY validation_occupation_id""", run_id,
    )
    return plain({"tasks": [dict(row) for row in tasks], "occupations": [dict(row) for row in occupations]})


async def persist_validations(
    connection: asyncpg.Connection, run_id: int, cohort_id: int,
    baseline_proxies: dict[int, dict[str, Any]], phase4d_proxies: dict[int, dict[str, Any]], source_id: int,
) -> dict[str, int]:
    counts = {"improved": 0, "regressed": 0, "unchanged": 0,
              "pairwisePass": 0, "pairwiseWarning": 0, "pairwiseFailure": 0,
              "absolutePass": 0, "absoluteFailure": 0}
    expectations = await connection.fetch(
        "SELECT * FROM phase4c_proxy_pairwise_expectations WHERE cohort_id=$1 ORDER BY id", cohort_id
    )
    for row in expectations:
        family = row["proxy_metric"]
        minimum = float(row["minimum_delta"])
        before_delta = round(
            metric(baseline_proxies[row["higher_occupation_id"]], family)
            - metric(baseline_proxies[row["lower_occupation_id"]], family), 4
        )
        after_delta = round(
            metric(phase4d_proxies[row["higher_occupation_id"]], family)
            - metric(phase4d_proxies[row["lower_occupation_id"]], family), 4
        )
        before = "pass" if before_delta >= minimum else "warning" if before_delta >= 0 else "failure"
        after = "pass" if after_delta >= minimum else "warning" if after_delta >= 0 else "failure"
        improved = outcome_rank(after) > outcome_rank(before)
        regressed = outcome_rank(after) < outcome_rank(before)
        counts["improved" if improved else "regressed" if regressed else "unchanged"] += 1
        counts[f"pairwise{after.title()}"] += 1
        await connection.execute(
            """
            INSERT INTO phase4d_proxy_validation_results (
              calculation_run_id,validation_type,validation_key,proxy_family,baseline_outcome,
              phase4d_outcome,baseline_value,phase4d_value,improved,regressed,finding,
              reconciliation,source_id,provenance,created_by
            ) VALUES ($1,'pairwise',$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
              'system:phase4d-proxy-validator')
            """, run_id, f"phase4c-pair-{row['id']}", family, before, after,
            dumps({"delta": before_delta, "minimum": minimum}),
            dumps({"delta": after_delta, "minimum": minimum}), improved, regressed,
            f"{family}: Phase 4C delta {before_delta:.4f}; Phase 4D delta {after_delta:.4f}; minimum {minimum:.4f}.",
            dumps({"before": before_delta, "after": after_delta, "passed": True}), source_id,
            dumps({"phase": "4D", "expectationVersion": row["expectation_version"],
                   "predeclared": True}),
        )
    occupations = await connection.fetch(
        "SELECT id,occupation_code,expected_proxy_behavior FROM phase4c_validation_occupations WHERE cohort_id=$1",
        cohort_id,
    )
    for row in occupations:
        for family, expectation in decoded(row["expected_proxy_behavior"]).items():
            if family == "expectation":
                continue
            before_value = metric(baseline_proxies[row["id"]], family)
            after_value = metric(phase4d_proxies[row["id"]], family)
            before = "pass" if absolute_pass(before_value, expectation) else "failure"
            after = "pass" if absolute_pass(after_value, expectation) else "failure"
            improved = outcome_rank(after) > outcome_rank(before)
            regressed = outcome_rank(after) < outcome_rank(before)
            counts["improved" if improved else "regressed" if regressed else "unchanged"] += 1
            counts[f"absolute{after.title()}"] += 1
            await connection.execute(
                """
                INSERT INTO phase4d_proxy_validation_results (
                  calculation_run_id,validation_type,validation_key,proxy_family,baseline_outcome,
                  phase4d_outcome,baseline_value,phase4d_value,improved,regressed,finding,
                  reconciliation,source_id,provenance,created_by
                ) VALUES ($1,'absolute_band',$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
                  'system:phase4d-proxy-validator')
                """, run_id, f"{row['occupation_code']}:{family}", family, before, after,
                dumps({"value": before_value, "expectedBand": expectation}),
                dumps({"value": after_value, "expectedBand": expectation}), improved, regressed,
                f"{row['occupation_code']} {family}: Phase 4C {before_value:.4f}; Phase 4D {after_value:.4f}; expected {expectation}.",
                dumps({"beforePass": before == "pass", "afterPass": after == "pass", "passed": True}),
                source_id, dumps({"phase": "4D", "predeclared": True}),
            )
    return counts


async def run(
    run_version: str, run_kind: str, previous_run_version: str | None, cohort_version: str,
) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        existing = await connection.fetchrow(
            "SELECT * FROM phase4d_calculation_runs WHERE run_version=$1", run_version
        )
        if existing:
            await transaction.commit()
            return {"calculationRunId": existing["id"], "runVersion": run_version,
                    "reused": True, "externalAiCalls": existing["external_ai_calls"]}
        dependencies = await load_phase4c_dependencies(connection, cohort_version)
        baseline_proxies, base_proxy_model = await load_or_create_proxies(connection, dependencies)
        model = await load_or_create_model(connection)
        phase4d_proxies = await load_or_create_snapshots(
            connection, dependencies, baseline_proxies, model
        )
        calculation_model = {**base_proxy_model, "id": model["id"], "model_version": MODEL_VERSION}
        tasks, occupations = calculate(
            dependencies, phase4d_proxies, calculation_model, methodology_phase="4D",
            mapping_scope_version="phase4c-minimum-scope-v1",
        )
        if len(occupations) != 25 or not all(item["reconciliation"]["passed"] for item in tasks + occupations):
            raise ValueError("Phase 4D scope or reconciliation failed")
        baseline_run = await connection.fetchrow(
            "SELECT * FROM phase4c_calculation_runs WHERE run_version=$1", BASELINE_RUN_VERSION
        )
        baseline_scores = {
            row["validation_occupation_id"]: dict(row) for row in await connection.fetch(
                "SELECT * FROM phase4c_occupation_scores WHERE calculation_run_id=$1", baseline_run["id"]
            )
        }
        baseline_task_fit = {
            row["ai_task_mapping_id"]: float(row["ai_capability_fit"])
            for row in await connection.fetch(
                "SELECT ai_task_mapping_id,ai_capability_fit FROM phase4c_task_assessments WHERE calculation_run_id=$1",
                baseline_run["id"],
            )
        }
        fit_changes = [item["mappingId"] for item in tasks
                       if abs(item["fit"]["score"] - baseline_task_fit[item["mappingId"]]) > .001]
        if fit_changes:
            raise ValueError("Phase 4D changed Task Capability Fit")
        coverage_changes = [item["occupationCode"] for item in occupations
                            if abs(item["coverage"] - float(baseline_scores[item["pilotOccupationId"]]["weighted_task_coverage"])) > .001
                            or item["coverageGateStatus"] != baseline_scores[item["pilotOccupationId"]]["coverage_gate_status"]]
        if coverage_changes:
            raise ValueError(f"Phase 4D changed coverage gate for {coverage_changes}")
        blocked = sorted(item["occupationCode"] for item in occupations if not item["scaleEligible"])
        required_blocked = sorted(["27-1024.00", "11-2022.00", "39-5012.00", "41-2031.00"])
        if blocked != required_blocked:
            raise ValueError(f"Phase 4D changed blocked set: {blocked}")
        previous = None
        replay_matches = None
        if previous_run_version:
            previous = await connection.fetchrow(
                "SELECT * FROM phase4d_calculation_runs WHERE run_version=$1", previous_run_version
            )
            if previous is None:
                raise ValueError(f"Missing previous Phase 4D run {previous_run_version}")
        if run_kind == "deterministic_replay":
            replay_matches = canonical_hash(await persisted_signature(connection, previous["id"])) == canonical_hash(
                output_signature(tasks, occupations)
            )
            if not replay_matches:
                raise ValueError("Phase 4D deterministic replay mismatch")
        dependency_manifest = {
            "phase": "4D", "cohortVersion": cohort_version,
            "baselineRunVersion": BASELINE_RUN_VERSION, "proxyModelVersion": MODEL_VERSION,
            "proxyImplementationHash": model["implementation_hash"],
            "mappingScopeHash": baseline_run["mapping_scope_hash"],
            "frontierTrackId": dependencies["track"]["id"],
            "taskFormulas": {key: row["formula_version"] for key, row in dependencies["formulas"].items()},
            "occupationFormula": dependencies["occupationFormula"]["formula_version"],
            "coverageGate": 70, "archetypeScoring": False,
            "snapshotHashes": [phase4d_proxies[key]["input_hash"] for key in sorted(phase4d_proxies)],
        }
        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4D direct structural proxy reconstruction'"
        )
        run_id = await connection.fetchval(
            """
            INSERT INTO phase4d_calculation_runs (
              run_version,run_kind,proxy_model_version_id,baseline_phase4c_run_id,previous_run_id,
              occupation_count,task_assessment_count,external_ai_calls,regenerated_mapping_count,
              archetype_scoring_enabled,production_score_writes,dependency_hash,
              reconciliation_status,replay_matches_previous,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,25,$6,0,0,false,0,$7,'passed',$8,$9,$10,
              'system:phase4d-scorer') RETURNING id
            """, run_version, run_kind, model["id"], baseline_run["id"],
            previous["id"] if previous else None, len(tasks), canonical_hash(dependency_manifest),
            replay_matches, source_id,
            dumps({"phase": "4D", "cohortOnly": True, "public": False, "production": False,
                   "externalAiCalls": 0, "regeneratedMappings": 0, "taskCapabilityFitChanges": 0,
                   "dependencyManifest": dependency_manifest}),
        )
        for item in tasks:
            await connection.execute(
                """
                INSERT INTO phase4d_task_assessments (
                  calculation_run_id,validation_occupation_id,ai_task_mapping_id,onet_task_id,
                  ai_capability_fit,automation_feasibility,augmentation_potential,task_ai_exposure,
                  confidence,exact_inputs,constraint_contributions,warnings,reconciliation,input_hash,
                  source_id,provenance,created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,
                  'system:phase4d-scorer')
                """, run_id, item["pilotOccupationId"], item["mappingId"], item["taskId"],
                item["fit"]["score"], item["automation"]["score"], item["augmentation"]["score"],
                item["taskExposure"], item["confidence"], dumps(item["exactInputs"]),
                dumps(item["automation"]["contributions"]), dumps(item["warnings"]),
                dumps(item["reconciliation"]), item["inputHash"], source_id,
                dumps({"phase": "4D", "existingMappingPreserved": True,
                       "taskCapabilityFitPreserved": True, "formulaRun": run_version}),
            )
        for item in occupations:
            baseline = baseline_scores[item["pilotOccupationId"]]
            await connection.execute(
                """
                INSERT INTO phase4d_occupation_scores (
                  calculation_run_id,validation_occupation_id,baseline_phase4c_score_id,
                  ai_exposure,replacement_risk,confidence,weighted_task_coverage,coverage_gate_status,
                  scale_eligible,ai_exposure_delta,replacement_risk_delta,confidence_delta,
                  factor_contributions,task_contributions,exact_inputs,warnings,reconciliation,
                  input_hash,source_id,provenance,created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
                  'system:phase4d-scorer')
                """, run_id, item["pilotOccupationId"], baseline["id"], item["aiExposure"],
                item["replacementRisk"], item["confidence"], item["coverage"],
                item["coverageGateStatus"], item["scaleEligible"],
                round(item["aiExposure"] - float(baseline["ai_exposure"]), 4),
                round(item["replacementRisk"] - float(baseline["replacement_risk"]), 4),
                round(item["confidence"] - float(baseline["confidence"]), 4),
                dumps(item["factors"]), dumps(item["tasks"]), dumps(item["exactInputs"]),
                dumps(item["warnings"]), dumps(item["reconciliation"]), item["inputHash"], source_id,
                dumps({"phase": "4D", "coverageGateUnchanged": True,
                       "archetypeScoring": False, "formulaRun": run_version}),
            )
        validations = await persist_validations(
            connection, run_id, dependencies["cohort"]["id"], baseline_proxies, phase4d_proxies, source_id
        )
        await transaction.commit()
        return {
            "calculationRunId": run_id, "runVersion": run_version, "runKind": run_kind,
            "occupations": len(occupations), "taskAssessments": len(tasks),
            "proxySnapshots": len(phase4d_proxies), "taskCapabilityFitChanges": 0,
            "coverageBlockedCodes": blocked,
            "scaleEligibleOccupations": sum(item["scaleEligible"] for item in occupations),
            "validations": validations, "replayMatchesPrevious": replay_matches,
            "externalAiCalls": 0, "regeneratedMappings": 0, "productionScoreWrites": 0,
            "archetypeScoringEnabled": False, "reconciliation": "passed", "reused": False,
        }
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-version", default=RUN_VERSION)
    parser.add_argument("--run-kind", choices=["direct_proxy_recompute", "deterministic_replay"],
                        default="direct_proxy_recompute")
    parser.add_argument("--previous-run-version")
    parser.add_argument("--cohort-version", default=COHORT_VERSION)
    args = parser.parse_args()
    print(json.dumps(await run(args.run_version, args.run_kind, args.previous_run_version,
                               args.cohort_version), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
