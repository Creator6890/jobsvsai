"""Score and validate the bounded Phase 4C cross-occupation cohort."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import defaultdict
from typing import Any

import asyncpg

try:
    from .calibration import occupation_proxies
    from .pilot import canonical_hash
    from .run_phase4a_pilot import decoded, dumps, load_dependencies, plain
    from .run_phase4b_calibration import (
        OCCUPATION_FORMULA,
        PROXY_MODEL,
        TASK_FORMULAS,
        calculate,
        collect_source_keys,
        output_signature,
    )
except ImportError:
    from calibration import occupation_proxies
    from pilot import canonical_hash
    from run_phase4a_pilot import decoded, dumps, load_dependencies, plain
    from run_phase4b_calibration import (
        OCCUPATION_FORMULA,
        PROXY_MODEL,
        TASK_FORMULAS,
        calculate,
        collect_source_keys,
        output_signature,
    )


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


async def load_phase4c_dependencies(
    connection: asyncpg.Connection, cohort_version: str
) -> dict[str, Any]:
    # Reuse the exact Phase 4B formulas and Frontier index loader. The returned
    # Phase 4A cohort data is replaced below by the explicit Phase 4C scope.
    dependencies = await load_dependencies(
        connection,
        "phase4a-2026q3-v1",
        task_formula_versions=TASK_FORMULAS,
        occupation_formula_version=OCCUPATION_FORMULA,
    )
    cohort_row = await connection.fetchrow(
        "SELECT * FROM phase4c_validation_cohorts WHERE cohort_version=$1", cohort_version
    )
    if cohort_row is None or cohort_row["new_mapping_run_id"] is None:
        raise ValueError("Phase 4C mapping scope has not been completed")
    cohort = dict(cohort_row)
    cohort["mapping_run_id"] = cohort["new_mapping_run_id"]
    dependencies["cohort"] = cohort
    dependencies["occupations"] = [
        dict(row)
        for row in await connection.fetch(
            """
            SELECT validation.*,source_occupation.title source_title
            FROM phase4c_validation_occupations validation
            JOIN onet_occupations source_occupation
              ON source_occupation.onet_soc_code=validation.occupation_code AND source_occupation.is_current
            WHERE validation.cohort_id=$1 ORDER BY validation.cohort_order
            """,
            cohort["id"],
        )
    ]
    dependencies["tasks"] = await connection.fetch(
        """
        SELECT task.*,validation.id pilot_occupation_id,scope.ai_task_mapping_id mapping_id,
               mapping.mapping_confidence,mapping.ambiguity_state,
               COALESCE(latest.scoring_eligible,false) scoring_eligible,
               scope.mapping_run_id,scope.scope_decision,scope.input_hash mapping_scope_input_hash
        FROM phase4c_validation_occupations validation
        JOIN onet_tasks task ON task.occupation_code=validation.occupation_code AND task.is_current
        LEFT JOIN phase4c_task_mapping_scope scope
          ON scope.cohort_id=validation.cohort_id AND scope.onet_task_id=task.task_id
        LEFT JOIN ai_generated_task_mappings mapping ON mapping.id=scope.ai_task_mapping_id
        LEFT JOIN LATERAL (
          SELECT event.scoring_eligible FROM ai_task_mapping_validation_events event
          WHERE event.ai_task_mapping_id=scope.ai_task_mapping_id
          ORDER BY event.created_at DESC,event.id DESC LIMIT 1
        ) latest ON true
        WHERE validation.cohort_id=$1
        ORDER BY validation.cohort_order,task.task_id
        """,
        cohort["id"],
    )
    requirement_rows = await connection.fetch(
        """
        SELECT requirement.ai_task_mapping_id,definition.slug,definition.name,requirement.weight,
               requirement.required_capability_level,requirement.confidence,requirement.rationale,
               requirement.evidence,requirement.provenance
        FROM phase4c_task_mapping_scope scope
        JOIN ai_generated_task_capability_requirements requirement
          ON requirement.ai_task_mapping_id=scope.ai_task_mapping_id
        JOIN ai_capability_definitions definition ON definition.id=requirement.capability_definition_id
        WHERE scope.cohort_id=$1
        ORDER BY requirement.ai_task_mapping_id,definition.slug
        """,
        cohort["id"],
    )
    constraint_rows = await connection.fetch(
        """
        SELECT mapped.ai_task_mapping_id,definition.slug,definition.name,mapped.constraint_level,
               mapped.confidence,mapped.rationale,mapped.evidence,mapped.provenance
        FROM phase4c_task_mapping_scope scope
        JOIN ai_generated_task_environment_constraints mapped
          ON mapped.ai_task_mapping_id=scope.ai_task_mapping_id
        JOIN task_environment_constraint_definitions definition
          ON definition.id=mapped.constraint_definition_id
        WHERE scope.cohort_id=$1
        ORDER BY mapped.ai_task_mapping_id,definition.slug
        """,
        cohort["id"],
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
    dependencies["requirements"] = requirements
    dependencies["constraints"] = constraints
    return dependencies


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
    rating_rows = await connection.fetch(
        """
        SELECT rating.occupation_code,rating.element_type,rating.element_id,rating.scale_id,
               rating.normalized_value,rating.sample_size,rating.standard_error,
               rating.recommend_suppress,rating.not_relevant,rating.source_version,
               rating.source_record_id,rating.row_hash,element.element_name
        FROM onet_element_ratings rating
        JOIN onet_elements element
          ON element.element_type=rating.element_type AND element.element_id=rating.element_id
         AND element.is_current
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
            "normalizedValue": float(row["normalized_value"]),
            "sampleSize": row["sample_size"],
            "standardError": float(row["standard_error"])
            if row["standard_error"] is not None
            else None,
            "recommendSuppress": row["recommend_suppress"],
            "notRelevant": row["not_relevant"],
            "sourceVersion": row["source_version"],
            "sourceRecordId": row["source_record_id"],
            "rowHash": row["row_hash"],
            "elementName": row["element_name"],
        }
    source_id = await connection.fetchval(
        "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4C targeted validation'"
    )
    snapshots: dict[int, dict[str, Any]] = {}
    for occupation in dependencies["occupations"]:
        existing = await connection.fetchrow(
            """
            SELECT * FROM phase4c_proxy_snapshots
            WHERE proxy_model_version_id=$1 AND validation_occupation_id=$2
            """,
            model["id"],
            occupation["id"],
        )
        if existing:
            snapshot = dict(existing)
            for key in (
                "domain_values",
                "component_contributions",
                "exact_inputs",
                "warnings",
                "reconciliation",
            ):
                snapshot[key] = decoded(snapshot[key])
            snapshots[occupation["id"]] = snapshot
            continue
        ratings = ratings_by_code[occupation["occupation_code"]]
        result = occupation_proxies(ratings, model["parameters"])
        exact_inputs = {
            "methodologyPhase": "4C",
            "cohortVersion": dependencies["cohort"]["cohort_version"],
            "proxyModelVersion": model["model_version"],
            "occupationCode": occupation["occupation_code"],
            "sourceRatings": [
                {"elementType": key[0], "elementId": key[1], "scaleId": key[2], **value}
                for key, value in sorted(ratings.items())
            ],
            "sourcePolicy": model["parameters"]["sourcePolicy"],
        }
        domain_values = {
            key: {"value": value["value"], "confidence": value["confidence"]}
            for key, value in result["domains"].items()
        }
        contributions = {
            "domains": result["domains"],
            "adoptionPressure": result["adoptionPressure"],
            "labourMarketResilience": result["labourMarketResilience"],
        }
        snapshot_id = await connection.fetchval(
            """
            INSERT INTO phase4c_proxy_snapshots (
              proxy_model_version_id,validation_occupation_id,adoption_pressure,
              labour_market_resilience,proxy_confidence,domain_values,component_contributions,
              exact_inputs,warnings,reconciliation,input_hash,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
              'system:phase4c-proxy-calculator') RETURNING id
            """,
            model["id"],
            occupation["id"],
            result["adoptionPressure"]["value"],
            result["labourMarketResilience"]["value"],
            result["confidence"],
            dumps(domain_values),
            dumps(contributions),
            dumps(exact_inputs),
            dumps(result["warnings"]),
            dumps(result["reconciliation"]),
            canonical_hash(exact_inputs),
            source_id,
            dumps(
                {
                    "phase": "4C",
                    "provisional": True,
                    "productionAllowed": False,
                    "noImputation": True,
                }
            ),
        )
        snapshots[occupation["id"]] = {
            "id": snapshot_id,
            "adoption_pressure": result["adoptionPressure"]["value"],
            "labour_market_resilience": result["labourMarketResilience"]["value"],
            "proxy_confidence": result["confidence"],
            "domain_values": domain_values,
            "component_contributions": contributions,
            "exact_inputs": exact_inputs,
            "warnings": result["warnings"],
            "reconciliation": result["reconciliation"],
            "input_hash": canonical_hash(exact_inputs),
        }
    return snapshots, model


async def persisted_output(connection: asyncpg.Connection, run_id: int) -> dict[str, Any]:
    tasks = await connection.fetch(
        """
        SELECT onet_task_id,ai_capability_fit,automation_feasibility,augmentation_potential,
               task_ai_exposure,confidence,input_hash
        FROM phase4c_task_assessments WHERE calculation_run_id=$1 ORDER BY onet_task_id
        """,
        run_id,
    )
    occupations = await connection.fetch(
        """
        SELECT validation_occupation_id pilot_occupation_id,ai_exposure,replacement_risk,
               confidence,weighted_task_coverage,input_hash
        FROM phase4c_occupation_scores WHERE calculation_run_id=$1 ORDER BY validation_occupation_id
        """,
        run_id,
    )
    return plain({"tasks": [dict(row) for row in tasks], "occupations": [dict(row) for row in occupations]})


def proxy_metric(snapshot: dict[str, Any], metric: str) -> float:
    if metric == "adoption-pressure":
        return float(snapshot["adoption_pressure"])
    if metric == "labour-market-resilience":
        return float(snapshot["labour_market_resilience"])
    return float(snapshot["domain_values"][metric]["value"])


async def persist_expectation_results(
    connection: asyncpg.Connection,
    run_id: int,
    cohort_id: int,
    proxies: dict[int, dict[str, Any]],
    source_id: int,
) -> dict[str, int]:
    expectations = await connection.fetch(
        "SELECT * FROM phase4c_proxy_pairwise_expectations WHERE cohort_id=$1 ORDER BY id",
        cohort_id,
    )
    counts = {"passed": 0, "warnings": 0, "failures": 0}
    for expectation in expectations:
        higher = proxy_metric(proxies[expectation["higher_occupation_id"]], expectation["proxy_metric"])
        lower = proxy_metric(proxies[expectation["lower_occupation_id"]], expectation["proxy_metric"])
        delta = round(higher - lower, 4)
        minimum = float(expectation["minimum_delta"])
        passed = delta >= minimum
        if passed:
            severity = "pass"
            counts["passed"] += 1
        elif delta >= 0:
            severity = "warning"
            counts["warnings"] += 1
        else:
            severity = "failure"
            counts["failures"] += 1
        finding = (
            f"Observed {expectation['proxy_metric']} delta {delta:.4f}; "
            f"predeclared minimum {minimum:.4f}."
        )
        await connection.execute(
            """
            INSERT INTO phase4c_proxy_validation_results (
              calculation_run_id,expectation_id,higher_value,lower_value,observed_delta,
              passed,severity,finding,reconciliation,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,
              'system:phase4c-proxy-validator')
            """,
            run_id,
            expectation["id"],
            higher,
            lower,
            delta,
            passed,
            severity,
            finding,
            dumps(
                {
                    "recomputedDelta": delta,
                    "passed": abs(delta - round(higher - lower, 4)) <= 0.0001,
                }
            ),
            source_id,
            dumps(
                {
                    "phase": "4C",
                    "expectationVersion": expectation["expectation_version"],
                    "definedBeforeProxyEvaluation": True,
                }
            ),
        )
    return counts


async def retained_continuity(
    connection: asyncpg.Connection,
    dependencies: dict[str, Any],
    occupations: list[dict[str, Any]],
) -> dict[str, Any]:
    phase4b_rows = await connection.fetch(
        """
        SELECT pilot.occupation_code,score.ai_exposure,score.replacement_risk,
               score.confidence,score.weighted_task_coverage
        FROM phase4a_occupation_scores score
        JOIN phase4a_calculation_runs run ON run.id=score.calculation_run_id
        JOIN phase4a_pilot_occupations pilot ON pilot.id=score.pilot_occupation_id
        WHERE run.run_version='phase4b-replay-v1.1-2026q3'
        """
    )
    baseline = {row["occupation_code"]: row for row in phase4b_rows}
    code_by_id = {row["id"]: row["occupation_code"] for row in dependencies["occupations"]}
    mismatches = []
    checked = 0
    for result in occupations:
        code = code_by_id[result["pilotOccupationId"]]
        if code not in baseline:
            continue
        checked += 1
        comparisons = {
            "aiExposure": (result["aiExposure"], float(baseline[code]["ai_exposure"])),
            "replacementRisk": (result["replacementRisk"], float(baseline[code]["replacement_risk"])),
            "confidence": (result["confidence"], float(baseline[code]["confidence"])),
            "weightedCoverage": (result["coverage"], float(baseline[code]["weighted_task_coverage"])),
        }
        for metric, (current, previous) in comparisons.items():
            if abs(current - previous) > 0.001:
                mismatches.append(
                    {"occupationCode": code, "metric": metric, "phase4b": previous, "phase4c": current}
                )
    return {"checkedOccupations": checked, "mismatches": mismatches, "passed": checked == 12 and not mismatches}


async def run(
    run_version: str,
    run_kind: str,
    previous_run_version: str | None,
    cohort_version: str,
) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        existing = await connection.fetchrow(
            "SELECT * FROM phase4c_calculation_runs WHERE run_version=$1", run_version
        )
        if existing:
            await transaction.commit()
            return {
                "calculationRunId": existing["id"],
                "runVersion": run_version,
                "reused": True,
                "externalAiCalls": existing["external_ai_calls"],
            }
        dependencies = await load_phase4c_dependencies(connection, cohort_version)
        proxies, proxy_model = await load_or_create_proxies(connection, dependencies)
        tasks, occupations = calculate(
            dependencies,
            proxies,
            proxy_model,
            methodology_phase="4C",
            mapping_scope_version="phase4c-minimum-scope-v1",
        )
        if not all(item["reconciliation"]["passed"] for item in tasks + occupations):
            raise ValueError("Phase 4C contribution reconciliation failed")
        continuity = await retained_continuity(connection, dependencies, occupations)
        if not continuity["passed"]:
            raise ValueError(f"Retained Phase 4A continuity mismatch: {continuity['mismatches']}")
        scope_rows = await connection.fetch(
            """
            SELECT scope_decision,input_hash FROM phase4c_task_mapping_scope
            WHERE cohort_id=$1 ORDER BY onet_task_id
            """,
            dependencies["cohort"]["id"],
        )
        mapping_scope_hash = canonical_hash([dict(row) for row in scope_rows])
        decision_counts: dict[str, int] = defaultdict(int)
        for row in scope_rows:
            decision_counts[row["scope_decision"]] += 1
        previous = None
        replay_matches = None
        if previous_run_version:
            previous = await connection.fetchrow(
                "SELECT * FROM phase4c_calculation_runs WHERE run_version=$1", previous_run_version
            )
            if previous is None:
                raise ValueError(f"Unknown previous Phase 4C run {previous_run_version}")
        if run_kind == "deterministic_replay":
            replay_matches = canonical_hash(await persisted_output(connection, previous["id"])) == canonical_hash(
                output_signature(tasks, occupations)
            )
            if not replay_matches:
                raise ValueError("Phase 4C deterministic replay mismatch")
        dependency_manifest = {
            "phase": "4C",
            "cohortVersion": cohort_version,
            "mappingScopeVersion": "phase4c-minimum-scope-v1",
            "mappingScopeHash": mapping_scope_hash,
            "formulaVersions": {
                key: item["formula_version"] for key, item in dependencies["formulas"].items()
            },
            "occupationFormula": dependencies["occupationFormula"]["formula_version"],
            "frontierTrackId": dependencies["track"]["id"],
            "proxyModel": proxy_model["model_version"],
            "proxySnapshotHashes": [proxies[key]["input_hash"] for key in sorted(proxies)],
            "taskInputHashes": [item["inputHash"] for item in tasks],
        }
        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4C targeted validation'"
        )
        run_id = await connection.fetchval(
            """
            INSERT INTO phase4c_calculation_runs (
              cohort_id,run_version,run_kind,capability_fit_formula_id,automation_formula_id,
              augmentation_formula_id,occupation_formula_id,frontier_track_id,proxy_model_version_id,
              mapping_scope_hash,dependency_hash,previous_run_id,new_mapping_count,
              reused_mapping_count,external_ai_calls,task_assessment_count,occupation_score_count,
              reconciliation_status,replay_matches_previous,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,0,$15,$16,'passed',$17,$18,$19,
              'system:phase4c-validation-scorer') RETURNING id
            """,
            dependencies["cohort"]["id"],
            run_version,
            run_kind,
            dependencies["formulas"]["capability_fit"]["id"],
            dependencies["formulas"]["automation_feasibility"]["id"],
            dependencies["formulas"]["augmentation_potential"]["id"],
            dependencies["occupationFormula"]["id"],
            dependencies["track"]["id"],
            proxy_model["id"],
            mapping_scope_hash,
            canonical_hash(dependency_manifest),
            previous["id"] if previous else None,
            decision_counts["generated"] + decision_counts["unmapped_insufficient_evidence"],
            decision_counts["reused"],
            len(tasks),
            len(occupations),
            replay_matches,
            source_id,
            dumps(
                {
                    "phase": "4C",
                    "targetedValidationOnly": True,
                    "public": False,
                    "productionScoreWrites": 0,
                    "externalAiCalls": 0,
                    "continuity": continuity,
                    "dependencyManifest": dependency_manifest,
                }
            ),
        )
        for item in tasks:
            await connection.execute(
                """
                INSERT INTO phase4c_task_assessments (
                  calculation_run_id,validation_occupation_id,ai_task_mapping_id,onet_task_id,
                  assessment_version,ai_capability_fit,automation_feasibility,augmentation_potential,
                  task_ai_exposure,confidence,proxy_confidence_penalty,capability_contributions,
                  constraint_contributions,exact_inputs,warnings,reconciliation,input_hash,
                  source_id,provenance,created_by
                ) VALUES ($1,$2,$3,$4,'phase4c-task-assessment-v1',$5,$6,$7,$8,$9,$10,$11,$12,
                  $13,$14,$15,$16,$17,$18,'system:phase4c-validation-scorer')
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
                item["proxyPenalty"],
                dumps(item["fit"]["contributions"]),
                dumps(item["automation"]["contributions"]),
                dumps(item["exactInputs"]),
                dumps(item["warnings"]),
                dumps(item["reconciliation"]),
                item["inputHash"],
                source_id,
                dumps({"phase": "4C", "targetedValidationOnly": True, "formulaRun": run_version}),
            )
        for item in occupations:
            await connection.execute(
                """
                INSERT INTO phase4c_occupation_scores (
                  calculation_run_id,validation_occupation_id,score_version,source_task_count,
                  mapped_task_count,excluded_task_count,weighting_eligible_task_count,
                  weighted_task_coverage,ai_exposure,replacement_risk,confidence,coverage_gate_status,
                  confidence_penalty,scale_eligible,factor_contributions,task_contributions,
                  exact_inputs,warnings,reconciliation,input_hash,source_id,provenance,created_by
                ) VALUES ($1,$2,'phase4c-occupation-score-v1',$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
                  $14,$15,$16,$17,$18,$19,$20,$21,'system:phase4c-validation-scorer')
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
                item["coverageGateStatus"],
                item["coveragePenalty"],
                item["scaleEligible"],
                dumps(item["factors"]),
                dumps(item["tasks"]),
                dumps(item["exactInputs"]),
                dumps(item["warnings"]),
                dumps(item["reconciliation"]),
                item["inputHash"],
                source_id,
                dumps({"phase": "4C", "targetedValidationOnly": True, "formulaRun": run_version}),
            )
        expectation_counts = await persist_expectation_results(
            connection, run_id, dependencies["cohort"]["id"], proxies, source_id
        )
        await connection.execute(
            "UPDATE phase4c_validation_cohorts SET status='validated' WHERE id=$1",
            dependencies["cohort"]["id"],
        )
        await transaction.commit()
        return {
            "calculationRunId": run_id,
            "runVersion": run_version,
            "runKind": run_kind,
            "occupations": len(occupations),
            "taskAssessments": len(tasks),
            "newMappingRows": decision_counts["generated"]
            + decision_counts["unmapped_insufficient_evidence"],
            "reusedMappingRows": decision_counts["reused"],
            "externalAiCalls": 0,
            "coverageBlockedOccupations": sum(
                item["coverageGateStatus"] == "below_threshold" for item in occupations
            ),
            "scaleEligibleOccupations": sum(item["scaleEligible"] for item in occupations),
            "retainedContinuity": continuity,
            "proxyExpectations": expectation_counts,
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
        "--run-kind", choices=["targeted_validation", "deterministic_replay"], required=True
    )
    parser.add_argument("--previous-run-version")
    parser.add_argument("--cohort-version", default="phase4c-2026q3-v1")
    args = parser.parse_args()
    print(
        json.dumps(
            await run(
                args.run_version, args.run_kind, args.previous_run_version, args.cohort_version
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
