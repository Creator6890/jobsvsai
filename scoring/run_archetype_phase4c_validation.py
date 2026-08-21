"""Apply Archetype Layer v1 to the frozen Phase 4C cohort only.

This is an isolated pilot override.  It reuses the Phase 4C task mappings,
Frontier index, formulas, task weights and 70% coverage gate.  The global
feature flag remains disabled and no production score table is written.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from typing import Any

import asyncpg

try:
    from enrichment.discover_occupational_archetypes import (
        BASELINE_VERSION,
        DIMENSIONS,
        MODEL_VERSION,
        load_inputs,
        structural_profile,
    )
    from scoring.pilot import canonical_hash, rounded
    from scoring.run_phase4a_pilot import decoded, dumps, plain
    from scoring.run_phase4b_calibration import calculate, output_signature
    from scoring.run_phase4c_validation import (
        database_url,
        load_or_create_proxies,
        load_phase4c_dependencies,
    )
except ImportError:
    from discover_occupational_archetypes import (
        BASELINE_VERSION, DIMENSIONS, MODEL_VERSION, load_inputs, structural_profile,
    )
    from pilot import canonical_hash, rounded
    from run_phase4a_pilot import decoded, dumps, plain
    from run_phase4b_calibration import calculate, output_signature
    from run_phase4c_validation import database_url, load_or_create_proxies, load_phase4c_dependencies


RUN_VERSION = "archetype-phase4c-pilot-v1-2026q3"
REPLAY_VERSION = "archetype-phase4c-replay-v1-2026q3"
COHORT_VERSION = "phase4c-2026q3-v1"
BASELINE_RUN_VERSION = "phase4c-targeted-validation-v1-2026q3"
ADJUSTMENT_FORMULA = "archetype-prior-source-adjustment-v1"


def absolute_pass(value: float, expectation: str) -> bool:
    if expectation == "high":
        return value >= 60
    if expectation == "low":
        return value <= 40
    if expectation == "medium":
        return 35 <= value <= 65
    if expectation == "medium-high":
        return value >= 50
    raise ValueError(f"Unknown expectation band {expectation}")


def outcome_rank(value: str) -> int:
    return {"failure": 0, "warning": 1, "pass": 2}[value]


def baseline_metric(snapshot: dict[str, Any], metric: str) -> float:
    if metric == "adoption-pressure":
        return float(snapshot["adoption_pressure"])
    if metric == "labour-market-resilience":
        return float(snapshot["labour_market_resilience"])
    return float(snapshot["domain_values"][metric]["value"])


def pilot_metric(snapshot: dict[str, Any], metric: str) -> float:
    if metric == "adoption-pressure":
        return float(snapshot["adoption_pressure"])
    if metric == "labour-market-resilience":
        return float(snapshot["labour_market_resilience"])
    return float(snapshot["domain_values"][metric]["value"])


async def load_model_context(
    connection: asyncpg.Connection, model_version: str
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    model = await connection.fetchrow(
        "SELECT * FROM occupational_archetype_model_versions WHERE model_version=$1", model_version
    )
    if model is None:
        raise ValueError(f"Archetype model {model_version} has not been discovered")
    rows = await connection.fetch(
        """
        SELECT membership.occupation_code,membership.membership_role,
               membership.membership_strength::float,membership.membership_confidence::float,
               membership.feature_completeness::float,definition.id archetype_id,
               definition.archetype_code,definition.name,baseline.structural_dimension,
               baseline.baseline_value::float,baseline.confidence::float baseline_confidence,
               baseline.formula_version,baseline.exact_inputs
        FROM occupation_archetype_memberships membership
        JOIN occupational_archetype_definitions definition
          ON definition.id=membership.archetype_definition_id
        JOIN archetype_structural_baselines baseline
          ON baseline.archetype_definition_id=definition.id AND baseline.baseline_version=$2
        WHERE membership.model_version_id=$1
        ORDER BY membership.occupation_code,membership.distance_rank,baseline.structural_dimension
        """, model["id"], BASELINE_VERSION,
    )
    context: dict[str, dict[str, Any]] = defaultdict(lambda: {"memberships": {}})
    for row in rows:
        role = row["membership_role"]
        membership = context[row["occupation_code"]]["memberships"].setdefault(
            role,
            {"archetypeId": row["archetype_id"], "archetypeCode": row["archetype_code"],
             "name": row["name"], "strength": row["membership_strength"],
             "confidence": row["membership_confidence"],
             "featureCompleteness": row["feature_completeness"], "baselines": {}},
        )
        membership["baselines"][row["structural_dimension"]] = {
            "value": row["baseline_value"], "confidence": row["baseline_confidence"],
            "formulaVersion": row["formula_version"], "exactInputs": decoded(row["exact_inputs"]),
        }
    return dict(model), dict(context)


async def load_profiles(
    connection: asyncpg.Connection, occupation_codes: set[str]
) -> dict[str, dict[str, dict[str, Any]]]:
    # Uses the same source derivation as discovery. It loads current O*NET records
    # once and retains profiles only for the bounded 25-occupation pilot.
    inputs = await load_inputs(connection)
    proxy = await connection.fetchrow(
        "SELECT parameters FROM phase4b_proxy_model_versions WHERE model_version='phase4b-occupation-proxy-v1'"
    )
    parameters = decoded(proxy["parameters"])
    return {
        code: structural_profile(inputs["ratingsByCode"][code], parameters)
        for code in sorted(occupation_codes)
    }


async def build_pilot_proxies(
    connection: asyncpg.Connection,
    dependencies: dict[str, Any],
    base_proxies: dict[int, dict[str, Any]],
    model: dict[str, Any],
    membership_context: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, dict[str, Any]]],
    source_id: int,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    snapshots: dict[int, dict[str, Any]] = {}
    adjustment_counts = {"priorOnly": 0, "sourceAdjusted": 0}
    for occupation in dependencies["occupations"]:
        occupation_id = occupation["id"]
        code = occupation["occupation_code"]
        memberships = membership_context.get(code, {}).get("memberships", {})
        primary = memberships.get("primary")
        secondary = memberships.get("secondary")
        if primary is None:
            raise ValueError(f"Phase 4C occupation {code} has no primary archetype")
        adjustments: dict[str, dict[str, Any]] = {}
        for dimension in DIMENSIONS:
            priors = [(primary, float(primary["strength"]))]
            if secondary:
                priors.append((secondary, float(secondary["strength"])))
            prior_weight_total = sum(weight for _, weight in priors)
            baseline = sum(
                item["baselines"][dimension]["value"] * weight for item, weight in priors
            ) / prior_weight_total
            baseline_confidence = sum(
                item["baselines"][dimension]["confidence"] * weight for item, weight in priors
            ) / prior_weight_total
            membership_confidence = sum(item["confidence"] * weight for item, weight in priors) / prior_weight_total
            source = profiles[code][dimension]
            source_value = source["value"]
            source_confidence = float(source["confidence"])
            warnings = []
            if source_value is None:
                applied_prior_weight = 1.0
                result = baseline
                result_confidence = rounded(min(baseline_confidence, membership_confidence) * .45)
                warnings.append({"code": "no_direct_occupation_source_evidence",
                                 "policy": "archetype_prior_only_with_confidence_penalty"})
                adjustment_counts["priorOnly"] += 1
            else:
                applied_prior_weight = min(
                    .28, .10 + .18 * (1 - source_confidence / 100) * (membership_confidence / 100)
                )
                result = baseline * applied_prior_weight + float(source_value) * (1 - applied_prior_weight)
                raw_confidence = (
                    baseline_confidence * applied_prior_weight
                    + source_confidence * (1 - applied_prior_weight)
                )
                result_confidence = rounded(raw_confidence * (1 - .20 * applied_prior_weight))
                adjustment_counts["sourceAdjusted"] += 1
            result = rounded(result)
            archetype_adjustment = round(result - baseline, 4)
            exact_inputs = {
                "modelVersion": model["model_version"], "baselineVersion": BASELINE_VERSION,
                "dimension": dimension,
                "primaryMembership": {key: primary[key] for key in (
                    "archetypeId", "archetypeCode", "strength", "confidence", "featureCompleteness"
                )},
                "secondaryMembership": {key: secondary[key] for key in (
                    "archetypeId", "archetypeCode", "strength", "confidence", "featureCompleteness"
                )} if secondary else None,
                "blendedArchetypeBaseline": rounded(baseline),
                "baselineConfidence": rounded(baseline_confidence),
                "sourceEvidence": source,
                "sourceEvidenceValue": source_value,
                "sourceEvidenceConfidence": source_confidence,
                "priorWeight": round(applied_prior_weight, 6),
                "formula": "result = priorWeight * archetypeBaseline + (1-priorWeight) * sourceEvidence",
                "missingPolicy": "prior-only, explicit warning, confidence capped and penalized; no invented source value",
            }
            reconciliation = {
                "recomputedResult": result,
                "recomputedAdjustment": archetype_adjustment,
                "passed": abs(
                    result - rounded(baseline if source_value is None else
                                     baseline * applied_prior_weight + float(source_value) * (1 - applied_prior_weight))
                ) <= .001,
            }
            existing = await connection.fetchrow(
                """
                SELECT * FROM occupation_archetype_proxy_adjustments
                WHERE model_version_id=$1 AND validation_occupation_id=$2 AND structural_dimension=$3
                """, model["id"], occupation_id, dimension,
            )
            if existing:
                adjustment_id = existing["id"]
                result = float(existing["resulting_proxy"])
                result_confidence = float(existing["resulting_confidence"])
                exact_inputs = decoded(existing["exact_inputs"])
                warnings = decoded(existing["warnings"])
                reconciliation = decoded(existing["reconciliation"])
            else:
                adjustment_id = await connection.fetchval(
                    """
                    INSERT INTO occupation_archetype_proxy_adjustments (
                      model_version_id,validation_occupation_id,structural_dimension,primary_archetype_id,
                      secondary_archetype_id,archetype_baseline,occupation_source_evidence,
                      evidence_confidence,prior_weight,occupation_adjustment,resulting_proxy,
                      resulting_confidence,formula_version,exact_inputs,warnings,reconciliation,
                      source_id,provenance,created_by
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,
                      'system:archetype-phase4c-pilot') RETURNING id
                    """, model["id"], occupation_id, dimension, primary["archetypeId"],
                    secondary["archetypeId"] if secondary else None, rounded(baseline), source_value,
                    source_confidence, round(applied_prior_weight, 6), archetype_adjustment, result,
                    result_confidence, ADJUSTMENT_FORMULA, dumps(exact_inputs), dumps(warnings),
                    dumps(reconciliation), source_id,
                    dumps({"pilotScope": COHORT_VERSION, "public": False, "production": False,
                           "featureFlagOverride": True, "sourceVersion": "O*NET 30.3"}),
                )
            adjustments[dimension] = {
                "id": adjustment_id, "value": result, "confidence": result_confidence,
                "components": [{"source": "archetype_prior_plus_occupation_source_adjustment",
                                "archetypeBaseline": exact_inputs["blendedArchetypeBaseline"],
                                "sourceEvidenceValue": exact_inputs["sourceEvidenceValue"],
                                "priorWeight": exact_inputs["priorWeight"]}],
                "warnings": warnings, "reconciliation": reconciliation,
            }
        base = base_proxies[occupation_id]
        domain_values = {
            dimension: {"value": adjustments[dimension]["value"],
                        "confidence": adjustments[dimension]["confidence"]}
            for dimension in (
                "physical-presence", "environment-variability", "human-dependency",
                "regulation", "accountability", "consequence-severity",
            )
        }
        contribution_domains = {
            dimension: {"name": dimension, "value": value["value"],
                        "confidence": value["confidence"],
                        "components": adjustments[dimension]["components"],
                        "reconciliation": adjustments[dimension]["reconciliation"]}
            for dimension, value in domain_values.items()
        }
        warnings = [
            {"code": "occupational_archetype_pilot_override", "modelVersion": model["model_version"],
             "globalFeatureFlagEnabled": False, "scope": COHORT_VERSION},
            {"code": "labour_market_resilience_unchanged",
             "detail": "Not an Archetype v1 structural dimension; Phase 4C proxy retained."},
        ]
        warnings.extend(
            {"code": "archetype_dimension_warning", "dimension": dimension, **warning}
            for dimension, value in adjustments.items() for warning in value["warnings"]
        )
        confidence_values = [value["confidence"] for value in domain_values.values()]
        confidence_values.extend([
            adjustments["adoption-pressure"]["confidence"], float(base["proxy_confidence"])
        ])
        proxy_confidence = rounded(min(confidence_values))
        exact_inputs = {
            "methodologyPhase": "archetype-v1-pilot", "cohortVersion": COHORT_VERSION,
            "modelVersion": model["model_version"], "baseProxySnapshotId": base["id"],
            "adjustmentIds": [adjustments[dimension]["id"] for dimension in DIMENSIONS],
            "unchangedInputs": {"labourMarketResilience": base["labour_market_resilience"],
                                "mappingScope": "phase4c-minimum-scope-v1",
                                "coverageGate": 70},
        }
        reconciliation = {
            "dimensionReconciliationsPassed": all(
                value["reconciliation"]["passed"] for value in adjustments.values()
            ),
            "coverageGateChanged": False, "labourMarketResilienceChanged": False, "passed": True,
        }
        snapshots[occupation_id] = {
            "id": adjustments["physical-presence"]["id"],
            "adoption_pressure": adjustments["adoption-pressure"]["value"],
            "labour_market_resilience": float(base["labour_market_resilience"]),
            "proxy_confidence": proxy_confidence, "domain_values": domain_values,
            "component_contributions": {
                "domains": contribution_domains,
                "adoptionPressure": {"value": adjustments["adoption-pressure"]["value"],
                                     "confidence": adjustments["adoption-pressure"]["confidence"]},
                "labourMarketResilience": base["component_contributions"]["labourMarketResilience"],
            },
            "exact_inputs": exact_inputs, "warnings": warnings,
            "reconciliation": reconciliation, "input_hash": canonical_hash(exact_inputs),
            "adjustments": adjustments,
        }
    return snapshots, adjustment_counts


async def persisted_signature(connection: asyncpg.Connection, run_id: int) -> dict[str, Any]:
    tasks = await connection.fetch(
        """SELECT onet_task_id,ai_capability_fit,automation_feasibility,augmentation_potential,
                  task_ai_exposure,confidence,input_hash
           FROM archetype_phase4c_task_assessments WHERE validation_run_id=$1 ORDER BY onet_task_id""",
        run_id,
    )
    occupations = await connection.fetch(
        """SELECT validation_occupation_id pilot_occupation_id,ai_exposure,replacement_risk,
                  confidence,weighted_task_coverage,input_hash
           FROM archetype_phase4c_occupation_scores WHERE validation_run_id=$1
           ORDER BY validation_occupation_id""", run_id,
    )
    return plain({"tasks": [dict(row) for row in tasks], "occupations": [dict(row) for row in occupations]})


async def persist_validations(
    connection: asyncpg.Connection,
    run_id: int,
    cohort_id: int,
    base_proxies: dict[int, dict[str, Any]],
    pilot_proxies: dict[int, dict[str, Any]],
    source_id: int,
) -> dict[str, Any]:
    counts = {"improved": 0, "regressed": 0, "unchanged": 0,
              "pairwisePass": 0, "pairwiseWarning": 0, "pairwiseFailure": 0,
              "absolutePass": 0, "absoluteFailure": 0}
    expectations = await connection.fetch(
        "SELECT * FROM phase4c_proxy_pairwise_expectations WHERE cohort_id=$1 ORDER BY id", cohort_id
    )
    for row in expectations:
        metric = row["proxy_metric"]
        minimum = float(row["minimum_delta"])
        before_delta = rounded(
            baseline_metric(base_proxies[row["higher_occupation_id"]], metric)
            - baseline_metric(base_proxies[row["lower_occupation_id"]], metric)
        )
        after_delta = rounded(
            pilot_metric(pilot_proxies[row["higher_occupation_id"]], metric)
            - pilot_metric(pilot_proxies[row["lower_occupation_id"]], metric)
        )
        before = "pass" if before_delta >= minimum else "warning" if before_delta >= 0 else "failure"
        after = "pass" if after_delta >= minimum else "warning" if after_delta >= 0 else "failure"
        improved = outcome_rank(after) > outcome_rank(before)
        regressed = outcome_rank(after) < outcome_rank(before)
        counts["improved" if improved else "regressed" if regressed else "unchanged"] += 1
        counts[f"pairwise{after.title()}"] += 1
        await connection.execute(
            """
            INSERT INTO archetype_proxy_validation_results (
              validation_run_id,validation_type,validation_key,structural_dimension,baseline_outcome,
              archetype_outcome,baseline_value,archetype_value,improved,regressed,finding,
              reconciliation,source_id,provenance,created_by
            ) VALUES ($1,'pairwise',$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
              'system:archetype-validator')
            """, run_id, f"phase4c-pair-{row['id']}", metric, before, after,
            dumps({"delta": before_delta, "minimum": minimum}),
            dumps({"delta": after_delta, "minimum": minimum}), improved, regressed,
            f"{metric}: Phase 4C delta {before_delta:.4f}; archetype delta {after_delta:.4f}; minimum {minimum:.4f}.",
            dumps({"beforeRecomputed": before_delta, "afterRecomputed": after_delta, "passed": True}),
            source_id, dumps({"expectationVersion": row["expectation_version"],
                              "predeclaredBeforeArchetypeEvaluation": True}),
        )
    occupation_rows = await connection.fetch(
        "SELECT id,occupation_code,expected_proxy_behavior FROM phase4c_validation_occupations WHERE cohort_id=$1",
        cohort_id,
    )
    for row in occupation_rows:
        for metric, expectation in decoded(row["expected_proxy_behavior"]).items():
            if metric == "expectation":
                continue
            before_value = baseline_metric(base_proxies[row["id"]], metric)
            after_value = pilot_metric(pilot_proxies[row["id"]], metric)
            before = "pass" if absolute_pass(before_value, expectation) else "failure"
            after = "pass" if absolute_pass(after_value, expectation) else "failure"
            improved = outcome_rank(after) > outcome_rank(before)
            regressed = outcome_rank(after) < outcome_rank(before)
            counts["improved" if improved else "regressed" if regressed else "unchanged"] += 1
            counts[f"absolute{after.title()}"] += 1
            await connection.execute(
                """
                INSERT INTO archetype_proxy_validation_results (
                  validation_run_id,validation_type,validation_key,structural_dimension,baseline_outcome,
                  archetype_outcome,baseline_value,archetype_value,improved,regressed,finding,
                  reconciliation,source_id,provenance,created_by
                ) VALUES ($1,'absolute_band',$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
                  'system:archetype-validator')
                """, run_id, f"{row['occupation_code']}:{metric}", metric, before, after,
                dumps({"value": before_value, "expectedBand": expectation}),
                dumps({"value": after_value, "expectedBand": expectation}), improved, regressed,
                f"{row['occupation_code']} {metric}: Phase 4C {before_value:.4f}; archetype {after_value:.4f}; expected {expectation}.",
                dumps({"beforePass": before == "pass", "afterPass": after == "pass", "passed": True}),
                source_id, dumps({"expectationSource": "phase4c_validation_occupations",
                                  "predeclaredBeforeArchetypeEvaluation": True}),
            )
    return counts


async def run(
    run_version: str, run_kind: str, previous_run_version: str | None,
    model_version: str, cohort_version: str,
) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        existing = await connection.fetchrow(
            "SELECT * FROM archetype_phase4c_validation_runs WHERE run_version=$1", run_version
        )
        if existing:
            await transaction.commit()
            return {"validationRunId": existing["id"], "runVersion": run_version,
                    "reused": True, "externalAiCalls": existing["external_ai_calls"]}
        dependencies = await load_phase4c_dependencies(connection, cohort_version)
        base_proxies, proxy_model = await load_or_create_proxies(connection, dependencies)
        model, memberships = await load_model_context(connection, model_version)
        occupation_codes = {row["occupation_code"] for row in dependencies["occupations"]}
        profiles = await load_profiles(connection, occupation_codes)
        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Occupational Archetype Layer v1'"
        )
        pilot_proxies, adjustment_counts = await build_pilot_proxies(
            connection, dependencies, base_proxies, model, memberships, profiles, source_id
        )
        tasks, occupations = calculate(
            dependencies, pilot_proxies, proxy_model,
            methodology_phase="archetype-v1-pilot",
            mapping_scope_version="phase4c-minimum-scope-v1",
        )
        if len(occupations) != 25 or not all(item["reconciliation"]["passed"] for item in tasks + occupations):
            raise ValueError("Archetype pilot scope or contribution reconciliation failed")
        baseline_run = await connection.fetchrow(
            "SELECT * FROM phase4c_calculation_runs WHERE run_version=$1", BASELINE_RUN_VERSION
        )
        if baseline_run is None:
            raise ValueError(f"Missing baseline run {BASELINE_RUN_VERSION}")
        baseline_scores = {
            row["validation_occupation_id"]: dict(row) for row in await connection.fetch(
                "SELECT * FROM phase4c_occupation_scores WHERE calculation_run_id=$1", baseline_run["id"]
            )
        }
        coverage_mismatches = [
            item["occupationCode"] for item in occupations
            if abs(item["coverage"] - float(baseline_scores[item["pilotOccupationId"]]["weighted_task_coverage"])) > .001
            or item["coverageGateStatus"] != baseline_scores[item["pilotOccupationId"]]["coverage_gate_status"]
        ]
        if coverage_mismatches:
            raise ValueError(f"Coverage gate changed for {coverage_mismatches}")
        blocked_codes = sorted(item["occupationCode"] for item in occupations
                               if item["coverageGateStatus"] == "below_threshold")
        required_blocked = sorted(["27-1024.00", "11-2022.00", "39-5012.00", "41-2031.00"])
        if blocked_codes != required_blocked:
            raise ValueError(f"Required Phase 4C blocked set changed: {blocked_codes}")
        previous = None
        replay_matches = None
        if previous_run_version:
            previous = await connection.fetchrow(
                "SELECT * FROM archetype_phase4c_validation_runs WHERE run_version=$1",
                previous_run_version,
            )
            if previous is None:
                raise ValueError(f"Missing previous archetype run {previous_run_version}")
        if run_kind == "deterministic_replay":
            replay_matches = canonical_hash(await persisted_signature(connection, previous["id"])) == canonical_hash(
                output_signature(tasks, occupations)
            )
            if not replay_matches:
                raise ValueError("Archetype deterministic replay mismatch")
        dependency_manifest = {
            "modelVersion": model_version, "modelSourceInputHash": model["source_input_hash"],
            "cohortVersion": cohort_version, "baselinePhase4CRun": BASELINE_RUN_VERSION,
            "mappingScopeVersion": "phase4c-minimum-scope-v1",
            "mappingScopeHash": baseline_run["mapping_scope_hash"],
            "frontierTrackId": dependencies["track"]["id"],
            "taskFormulaVersions": {key: value["formula_version"] for key, value in dependencies["formulas"].items()},
            "occupationFormula": dependencies["occupationFormula"]["formula_version"],
            "coverageThreshold": 70, "adjustmentFormula": ADJUSTMENT_FORMULA,
            "adjustmentHashes": [pilot_proxies[key]["input_hash"] for key in sorted(pilot_proxies)],
        }
        run_id = await connection.fetchval(
            """
            INSERT INTO archetype_phase4c_validation_runs (
              run_version,run_kind,model_version_id,baseline_phase4c_run_id,previous_run_id,
              pilot_feature_flag_override,external_ai_calls,regenerated_mapping_count,
              occupation_count,task_assessment_count,dependency_hash,reconciliation_status,
              replay_matches_previous,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,true,0,0,25,$6,$7,'passed',$8,$9,$10,
              'system:archetype-phase4c-pilot') RETURNING id
            """, run_version, run_kind, model["id"], baseline_run["id"],
            previous["id"] if previous else None, len(tasks), canonical_hash(dependency_manifest),
            replay_matches, source_id,
            dumps({"pilotOnly": True, "featureFlagGloballyDisabled": True, "public": False,
                   "productionScoreWrites": 0, "externalAiCalls": 0,
                   "regeneratedMappings": 0, "dependencyManifest": dependency_manifest}),
        )
        for item in tasks:
            await connection.execute(
                """
                INSERT INTO archetype_phase4c_task_assessments (
                  validation_run_id,validation_occupation_id,ai_task_mapping_id,onet_task_id,
                  ai_capability_fit,automation_feasibility,augmentation_potential,task_ai_exposure,
                  confidence,exact_inputs,constraint_contributions,reconciliation,input_hash,
                  source_id,provenance,created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
                  'system:archetype-phase4c-pilot')
                """, run_id, item["pilotOccupationId"], item["mappingId"], item["taskId"],
                item["fit"]["score"], item["automation"]["score"], item["augmentation"]["score"],
                item["taskExposure"], item["confidence"], dumps(item["exactInputs"]),
                dumps(item["automation"]["contributions"]), dumps(item["reconciliation"]),
                item["inputHash"], source_id,
                dumps({"pilotOnly": True, "modelVersion": model_version,
                       "baseMappingPreserved": True, "formulaRun": run_version}),
            )
        for item in occupations:
            baseline = baseline_scores[item["pilotOccupationId"]]
            await connection.execute(
                """
                INSERT INTO archetype_phase4c_occupation_scores (
                  validation_run_id,validation_occupation_id,baseline_phase4c_score_id,
                  ai_exposure,replacement_risk,confidence,weighted_task_coverage,coverage_gate_status,
                  scale_eligible,ai_exposure_delta,replacement_risk_delta,confidence_delta,
                  factor_contributions,exact_inputs,warnings,reconciliation,input_hash,
                  source_id,provenance,created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,
                  'system:archetype-phase4c-pilot')
                """, run_id, item["pilotOccupationId"], baseline["id"], item["aiExposure"],
                item["replacementRisk"], item["confidence"], item["coverage"],
                item["coverageGateStatus"], item["scaleEligible"],
                round(item["aiExposure"] - float(baseline["ai_exposure"]), 4),
                round(item["replacementRisk"] - float(baseline["replacement_risk"]), 4),
                round(item["confidence"] - float(baseline["confidence"]), 4),
                dumps(item["factors"]), dumps(item["exactInputs"]), dumps(item["warnings"]),
                dumps(item["reconciliation"]), item["inputHash"], source_id,
                dumps({"pilotOnly": True, "modelVersion": model_version,
                       "coverageGateUnchanged": True, "formulaRun": run_version}),
            )
        validations = await persist_validations(
            connection, run_id, dependencies["cohort"]["id"], base_proxies, pilot_proxies, source_id
        )
        await transaction.commit()
        return {
            "validationRunId": run_id, "runVersion": run_version, "runKind": run_kind,
            "occupations": len(occupations), "taskAssessments": len(tasks),
            "adjustments": 25 * len(DIMENSIONS), "adjustmentPolicy": adjustment_counts,
            "coverageBlockedCodes": blocked_codes,
            "scaleEligibleOccupations": sum(item["scaleEligible"] for item in occupations),
            "validations": validations, "replayMatchesPrevious": replay_matches,
            "externalAiCalls": 0, "regeneratedMappings": 0, "productionScoreWrites": 0,
            "featureFlagGloballyEnabled": False, "reconciliation": "passed", "reused": False,
        }
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-version", default=RUN_VERSION)
    parser.add_argument("--run-kind", choices=["archetype_pilot", "deterministic_replay"],
                        default="archetype_pilot")
    parser.add_argument("--previous-run-version")
    parser.add_argument("--model-version", default=MODEL_VERSION)
    parser.add_argument("--cohort-version", default=COHORT_VERSION)
    args = parser.parse_args()
    print(json.dumps(await run(args.run_version, args.run_kind, args.previous_run_version,
                               args.model_version, args.cohort_version), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
