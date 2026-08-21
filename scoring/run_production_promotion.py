"""Promote approved Phase 5/5B candidate scores into the production score store.

One promotion run, one transaction. Either every approved occupation lands with its full
derivation and both reconciliations pass, or nothing is written.

What this does NOT do:

  * it does not publish or activate anything — `occupation_publications.activation_status`
    is never touched, and `publishable` on a snapshot means "editorially permissible",
    not "public";
  * it does not flip `scoring_model_versions.is_active` — it refuses to run if the model it
    is about to stamp is the active one, because promotion must not change what the legacy
    worker writes;
  * it does not recalculate anything — every number is carried from the persisted candidate
    run, and the reconciliations verify the carry rather than recompute the score;
  * it does not touch the legacy chain, Phase 4/5 data, or any editorial row.

Selection is explicit by design. The eligible set is the launch-eligible cohort of a named
Phase 6 triage run; promoting all of it requires `--approve-full-cohort`, and promoting a
subset requires a file of approved SOC codes. There is no path that promotes "everything
scored".

  # review first — writes nothing
  docker compose run --rm -e PYTHONPATH=/app/scoring worker \
      python -m scoring.run_production_promotion \
      --run-key phase6-promotion-2026q3-v1 \
      --triage-run-key phase6-triage-postcoverage-2026q3-v1 \
      --approve-full-cohort --dry-run

  # then, only with explicit approval, drop --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from decimal import Decimal
from typing import Any

import asyncpg


PROMOTION_POLICY_VERSION = "phase6-production-promotion-v1"
ENGINE_FAMILY = "jobsvsai-engine-v2"

# Reconciliation tolerance. Contributions are persisted rounded to 4 decimal places, so a
# sum can differ from the stored score in the last place. Anything larger is a real defect.
RECONCILIATION_TOLERANCE = 0.01

# The launch gates, restated here so promotion refuses anything the triage would not have
# passed. These are not new thresholds: they are `phase6_launch_triage.GATES` verbatim.
LAUNCH_MINIMUM_COVERAGE = 80.0
LAUNCH_MINIMUM_CONFIDENCE = 75.0
EXPECTED_MODEL_VERSION = "JVS 2.0.0-phase4b"
FORBIDDEN_MODEL_VERSION = "JVS 1.0.3"

FACTOR_LABELS = {
    "taskAutomationExposure": "Task automation exposure",
    "aiCapabilityProximity": "AI capability proximity",
    "humanDependencyResistance": "Human dependency resistance",
    "physicalDependencyResistance": "Physical dependency resistance",
    "adoptionPressure": "Adoption pressure",
    "labourMarketResilienceResistance": "Labour market resilience resistance",
}
FACTOR_ORDER = list(FACTOR_LABELS)
INVERSE_FACTORS = {
    "humanDependencyResistance",
    "physicalDependencyResistance",
    "labourMarketResilienceResistance",
}


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    return value


def decoded(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else plain(value)


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def dumps(value: Any) -> str:
    return json.dumps(plain(value), sort_keys=True, default=str)


async def isolation_snapshot(connection: asyncpg.Connection) -> dict[str, Any]:
    """The state promotion must not change. Compared before and after."""
    row = await connection.fetchrow("""
      SELECT (SELECT count(*) FROM occupation_scores) legacy_occupation_rows,
             (SELECT count(*) FROM task_ai_scores) legacy_task_rows,
             (SELECT count(*) FROM score_history) legacy_history_rows,
             (SELECT count(*) FROM occupation_publications WHERE activation_status='public') public_rows,
             (SELECT version FROM scoring_model_versions WHERE is_active) active_model,
             (SELECT count(*) FROM phase5_occupation_scores) candidate_rows,
             (SELECT enabled FROM scoring_enrichment_feature_flags
              WHERE flag_key='occupational_archetype_layer') archetype_enabled
    """)
    return dict(row)


async def resolve_model(connection: asyncpg.Connection) -> asyncpg.Record:
    model = await connection.fetchrow("""
      SELECT id, version, is_active, methodology_family
      FROM scoring_model_versions
      WHERE methodology_family = $1
      ORDER BY created_at DESC, id DESC LIMIT 1
    """, ENGINE_FAMILY)
    if model is None:
        raise SystemExit(
            f"No scoring model registered in the {ENGINE_FAMILY} family. Migration 026 registers it."
        )
    if model["is_active"]:
        raise SystemExit(
            f"{model['version']} is the active scoring model. Promotion must not run against the "
            "active model: the legacy worker writes under whatever is active, and this phase does "
            "not change that."
        )
    if model["version"] == FORBIDDEN_MODEL_VERSION:
        raise SystemExit(f"Refusing to promote under the legacy model {FORBIDDEN_MODEL_VERSION}.")
    if model["version"] != EXPECTED_MODEL_VERSION:
        raise SystemExit(
            f"Expected to promote under {EXPECTED_MODEL_VERSION}, found {model['version']}."
        )
    return model


async def load_cohort(
    connection: asyncpg.Connection,
    triage_run_key: str,
    approved_codes: set[str] | None,
) -> tuple[asyncpg.Record, list[dict[str, Any]]]:
    triage_run = await connection.fetchrow(
        "SELECT * FROM phase6_launch_triage_runs WHERE run_key = $1", triage_run_key)
    if triage_run is None:
        raise SystemExit(f"No triage run named {triage_run_key}.")

    rows = await connection.fetch("""
      SELECT result.occupation_code, result.title, result.blocking_codes,
             score.id AS candidate_score_id, score.candidate_occupation_id,
             score.ai_exposure, score.replacement_risk, score.confidence,
             score.weighted_task_coverage, score.source_task_count, score.eligible_task_count,
             score.excluded_task_count, score.weighting_eligible_task_count,
             score.coverage_gate_status, score.confidence_gate_status, score.candidate_status,
             score.factor_contributions, score.task_contributions, score.exact_inputs,
             score.provisional_sensitivity, score.warnings, score.blocking_reasons,
             score.reconciliation, score.input_hash AS candidate_input_hash,
             score.created_at AS calculated_at,
             candidate.identity_id, identity.jobs_vs_ai_occupation_id AS occupation_id
      FROM phase6_launch_triage_results result
      JOIN phase6_launch_triage_runs run ON run.id = result.triage_run_id
      JOIN phase5_occupation_scores score
        ON score.candidate_occupation_id = result.candidate_occupation_id
       AND score.calculation_run_id = run.source_calculation_run_id
      JOIN phase5_candidate_occupations candidate ON candidate.id = result.candidate_occupation_id
      JOIN canonical_occupation_identities identity ON identity.id = candidate.identity_id
      WHERE run.run_key = $1 AND result.launch_eligible
      ORDER BY result.occupation_code
    """, triage_run_key)

    cohort = [dict(row) for row in rows]
    if approved_codes is not None:
        eligible_codes = {row["occupation_code"] for row in cohort}
        unknown = sorted(approved_codes - eligible_codes)
        if unknown:
            raise SystemExit(
                "Approved list contains occupations that are not launch-eligible in "
                f"{triage_run_key}: {', '.join(unknown[:10])}"
                + (f" (+{len(unknown) - 10} more)" if len(unknown) > 10 else "")
            )
        cohort = [row for row in cohort if row["occupation_code"] in approved_codes]
    return triage_run, cohort


def build_snapshot_plan(row: dict[str, Any]) -> dict[str, Any]:
    """Everything one snapshot needs, plus its two reconciliations. Pure function."""
    factors = decoded(row["factor_contributions"]) or []
    tasks = decoded(row["task_contributions"]) or []
    replacement_risk = float(row["replacement_risk"])
    ai_exposure = float(row["ai_exposure"])

    factor_total = round(sum(float(item["weightedContribution"]) for item in factors), 4)
    exposure_total = round(sum(float(item["aiExposureContribution"]) for item in tasks), 4)
    factor_ok = abs(factor_total - replacement_risk) <= RECONCILIATION_TOLERANCE
    exposure_ok = abs(exposure_total - ai_exposure) <= RECONCILIATION_TOLERANCE

    missing_factors = sorted(set(FACTOR_ORDER) - {item["factor"] for item in factors})

    # Restates the schema CHECK rather than trusting the caller.
    publishable = (
        row["candidate_status"] == "review_ready"
        and row["coverage_gate_status"] == "passed"
        and row["confidence_gate_status"] == "passed"
        and float(row["weighted_task_coverage"]) >= 70
        and float(row["confidence"]) >= 70
    )
    # Independently restates the launch gates. The cohort came from a triage run that already
    # applied them; re-checking here means a hand-edited approval list cannot smuggle an
    # occupation past them.
    blocking = decoded(row["blocking_codes"]) or []
    gate_failures = []
    if row["candidate_status"] != "review_ready":
        gate_failures.append(f"candidate_status={row['candidate_status']}")
    if row["coverage_gate_status"] != "passed":
        gate_failures.append(f"coverage_gate={row['coverage_gate_status']}")
    if row["confidence_gate_status"] != "passed":
        gate_failures.append(f"confidence_gate={row['confidence_gate_status']}")
    if float(row["weighted_task_coverage"]) < LAUNCH_MINIMUM_COVERAGE:
        gate_failures.append(f"coverage={float(row['weighted_task_coverage']):.2f}<{LAUNCH_MINIMUM_COVERAGE}")
    if float(row["confidence"]) < LAUNCH_MINIMUM_CONFIDENCE:
        gate_failures.append(f"confidence={float(row['confidence']):.2f}<{LAUNCH_MINIMUM_CONFIDENCE}")
    if blocking:
        gate_failures.append(f"blocking_codes={blocking}")
    if not str(row["candidate_input_hash"] or "").strip():
        gate_failures.append("candidate score has no input hash")
    return {
        "occupationCode": row["occupation_code"],
        "title": row["title"],
        "identityId": row["identity_id"],
        "occupationId": row["occupation_id"],
        "candidateScoreId": row["candidate_score_id"],
        "aiExposure": ai_exposure,
        "replacementRisk": replacement_risk,
        "confidence": float(row["confidence"]),
        "coverage": float(row["weighted_task_coverage"]),
        "publishable": publishable,
        "scoringEligibility": "production_ready" if publishable else "blocked",
        "gateFailures": gate_failures,
        "candidateInputHash": row["candidate_input_hash"],
        "factors": factors,
        "tasks": tasks,
        "reconciliation": {
            "replacementContributionTotal": factor_total,
            "replacementRisk": replacement_risk,
            "replacementReconciles": factor_ok,
            "exposureContributionTotal": exposure_total,
            "aiExposure": ai_exposure,
            "exposureReconciles": exposure_ok,
            "factorCount": len(factors),
            "taskCount": len(tasks),
            "missingFactors": missing_factors,
            "passed": factor_ok and exposure_ok and not missing_factors and len(factors) == 6,
        },
    }


async def run(
    run_key: str,
    triage_run_key: str,
    approved_codes: set[str] | None,
    approve_full_cohort: bool,
    dry_run: bool,
    verify_then_rollback: bool = False,
    expect_count: int | None = None,
) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    try:
        if approved_codes is None and not approve_full_cohort:
            raise SystemExit(
                "Refusing to promote without an explicit approval. Pass --approved-codes-file "
                "with the approved SOC codes, or --approve-full-cohort to approve the entire "
                "launch-eligible cohort of the named triage run."
            )
        existing = await connection.fetchrow(
            "SELECT id, status FROM production_promotion_runs WHERE run_key = $1", run_key)
        if existing is not None:
            raise SystemExit(
                f"Promotion run {run_key} already exists (id {existing['id']}, "
                f"status {existing['status']}). Promotion runs are immutable; use a new run key."
            )

        model = await resolve_model(connection)
        triage_run, cohort = await load_cohort(connection, triage_run_key, approved_codes)
        if not cohort:
            raise SystemExit("Approved cohort is empty; nothing to promote.")
        if expect_count is not None and len(cohort) != expect_count:
            raise SystemExit(
                f"Approved cohort resolved to {len(cohort)} occupations, expected {expect_count}. "
                "Refusing to promote a cohort that is not the approved one."
            )
        identities = [row["identity_id"] for row in cohort]
        if len(set(identities)) != len(identities):
            raise SystemExit("Approved cohort contains duplicate identities.")
        if any(identity is None for identity in identities):
            raise SystemExit("Approved cohort contains an occupation with no canonical identity.")

        calculation_run = await connection.fetchrow(
            "SELECT * FROM phase5_calculation_runs WHERE id = $1",
            triage_run["source_calculation_run_id"])
        manifest = (decoded(calculation_run["provenance"]) or {}).get("dependencyManifest", {})
        policy = await connection.fetchrow("""
          SELECT policy.policy_version, rubric.version AS rubric_version,
                 taxonomy.version AS taxonomy_version
          FROM task_mapping_evidence_policy_versions policy
          JOIN task_mapping_rubric_versions rubric ON rubric.id = policy.rubric_version_id
          JOIN ai_capability_taxonomy_versions taxonomy ON taxonomy.id = policy.taxonomy_version_id
          WHERE policy.policy_version = 'mvp-evidence-policy-v1'
        """)

        version_bundle = {
            "frontierIndexVersion": manifest.get("frontierIndexVersion"),
            "frontierTrack": manifest.get("frontierTrack"),
            "structuralProxyModelVersion": manifest.get("phase4dProxyModel"),
            "baseProxyModelVersion": manifest.get("baseProxyModel"),
            "occupationFormulaVersion": manifest.get("occupationFormula"),
            "taskFormulaVersions": manifest.get("formulaVersions", {}),
            "capabilityTaxonomyVersion": policy["taxonomy_version"],
            "mappingRubricVersion": policy["rubric_version"],
            "evidencePolicyVersion": policy["policy_version"],
            "sourceNamespaceVersion": manifest.get("namespaceVersion"),
            "mappingScopeVersion": manifest.get("mappingScopeVersion"),
            "sourceCalculationRunVersion": calculation_run["run_version"],
        }
        if not all(version_bundle[key] for key in (
                "frontierIndexVersion", "frontierTrack", "structuralProxyModelVersion",
                "baseProxyModelVersion", "occupationFormulaVersion")):
            raise SystemExit(
                "Candidate run does not carry a complete dependency manifest; refusing to promote "
                "scores whose provenance cannot be stated."
            )

        plans = [build_snapshot_plan(row) for row in cohort]
        gate_failed = [plan for plan in plans if plan["gateFailures"]]
        failures = [plan for plan in plans if not plan["reconciliation"]["passed"]]
        not_publishable = [plan for plan in plans if not plan["publishable"]]
        missing_editorial = [plan for plan in plans if plan["occupationId"] is None]

        selection_policy = {
            "policyVersion": PROMOTION_POLICY_VERSION,
            "eligibleFrom": triage_run_key,
            "triagePolicyVersion": triage_run["policy_version"],
            "approval": "full_cohort" if approved_codes is None else "explicit_code_list",
            "approvedCount": len(plans),
            "eligibleCount": len(cohort) if approved_codes is None else None,
            "rule": (
                "launch-eligible in the named triage run; no critical or high findings; "
                "no target count and no truncation"
            ),
        }

        summary: dict[str, Any] = {
            "runKey": run_key,
            "promotionPolicyVersion": PROMOTION_POLICY_VERSION,
            "scoringModel": {"id": model["id"], "version": model["version"],
                             "isActive": model["is_active"],
                             "methodologyFamily": model["methodology_family"]},
            "sourceCalculationRun": calculation_run["run_version"],
            "sourceTriageRun": triage_run_key,
            "versionBundle": version_bundle,
            "selectionPolicy": selection_policy,
            "approvedOccupations": len(plans),
            "snapshotsToWrite": len(plans),
            "factorRowsToWrite": sum(len(plan["factors"]) for plan in plans),
            "taskRowsToWrite": sum(len(plan["tasks"]) for plan in plans),
            "publishableSnapshots": len(plans) - len(not_publishable),
            "snapshotsWithoutEditorialOccupation": len(missing_editorial),
            "launchGateRecheckFailures": len(gate_failed),
            "minimumCoverageInCohort": round(min(plan["coverage"] for plan in plans), 4),
            "minimumConfidenceInCohort": round(min(plan["confidence"] for plan in plans), 4),
            "distinctIdentities": len({plan["identityId"] for plan in plans}),
            "reconciliationFailures": len(failures),
            "reconciliationFailureDetail": [
                {"occupationCode": plan["occupationCode"], **plan["reconciliation"]}
                for plan in failures[:10]
            ],
            "isolationBefore": plain(await isolation_snapshot(connection)),
        }

        if gate_failed:
            summary["persisted"] = False
            summary["refused"] = (
                f"{len(gate_failed)} approved occupations do not clear the launch gates on "
                "re-check. Promotion does not override gates."
            )
            summary["gateFailures"] = [
                {"occupationCode": plan["occupationCode"], "failures": plan["gateFailures"]}
                for plan in gate_failed[:20]
            ]
            return summary
        if failures:
            summary["persisted"] = False
            summary["refused"] = (
                "Reconciliation failed for at least one approved occupation. A snapshot whose "
                "contributions do not sum to its score cannot be explained on a public page."
            )
            return summary
        if not_publishable:
            summary["persisted"] = False
            summary["refused"] = (
                f"{len(not_publishable)} approved occupations do not clear the validated gates. "
                "Promotion does not override gates."
            )
            summary["notPublishable"] = [plan["occupationCode"] for plan in not_publishable[:20]]
            return summary

        if dry_run and not verify_then_rollback:
            summary["persisted"] = False
            summary["wouldPromote"] = True
            return summary

        transaction = connection.transaction()
        await transaction.start()
        try:
            source_id = await connection.fetchval("SELECT id FROM data_sources ORDER BY id LIMIT 1")
            run_id = await connection.fetchval("""
              INSERT INTO production_promotion_runs (
                run_key, source_kind, source_namespace_id, source_calculation_run_id,
                scoring_model_version_id, promotion_policy_version, status, occupation_count,
                is_test_fixture, input_version_bundle, selection_policy, input_hash, source_id,
                provenance, created_by)
              VALUES ($1,'phase5_candidate',$2,$3,$4,$5,'in_progress',0,false,
                $6::jsonb,$7::jsonb,$8,$9,$10::jsonb,'system:phase6-promoter')
              RETURNING id
            """, run_key, calculation_run["namespace_id"], calculation_run["id"], model["id"],
                 PROMOTION_POLICY_VERSION, dumps(version_bundle), dumps(selection_policy),
                 canonical_hash({"runKey": run_key, "bundle": version_bundle,
                                 "selection": selection_policy,
                                 "codes": [plan["occupationCode"] for plan in plans]}),
                 source_id,
                 dumps({"phase": "6", "publicActivations": 0, "legacyWrites": 0,
                        "augmentationPublished": False}))

            for plan in plans:
                snapshot_id = await connection.fetchval("""
                  INSERT INTO production_occupation_score_snapshots (
                    promotion_run_id, identity_id, occupation_id, source_candidate_score_id,
                    scoring_model_version_id, ai_exposure, replacement_risk, augmentation_potential,
                    confidence, weighted_task_coverage, source_task_count, eligible_task_count,
                    excluded_task_count, weighting_eligible_task_count, coverage_gate_status,
                    confidence_gate_status, scoring_eligibility, publishable, frontier_index_version,
                    frontier_track, structural_proxy_model_version, base_proxy_model_version,
                    occupation_formula_version, task_formula_versions, capability_taxonomy_version,
                    mapping_rubric_version, evidence_policy_version, calculated_at, exact_inputs,
                    provisional_sensitivity, warnings, blocking_reasons, reconciliation, input_hash,
                    source_id, provenance, created_by)
                  VALUES ($1,$2,$3,$4,$5,$6,$7,NULL,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,
                    $20,$21,$22,$23::jsonb,$24,$25,$26,$27,$28::jsonb,$29::jsonb,$30::jsonb,
                    $31::jsonb,$32::jsonb,$33,$34,$35::jsonb,'system:phase6-promoter')
                  RETURNING id
                """,
                    run_id, plan["identityId"], plan["occupationId"], plan["candidateScoreId"],
                    model["id"], plan["aiExposure"], plan["replacementRisk"],
                    plan["confidence"], plan["coverage"],
                    next(row["source_task_count"] for row in cohort
                         if row["occupation_code"] == plan["occupationCode"]),
                    next(row["eligible_task_count"] for row in cohort
                         if row["occupation_code"] == plan["occupationCode"]),
                    next(row["excluded_task_count"] for row in cohort
                         if row["occupation_code"] == plan["occupationCode"]),
                    next(row["weighting_eligible_task_count"] for row in cohort
                         if row["occupation_code"] == plan["occupationCode"]),
                    next(row["coverage_gate_status"] for row in cohort
                         if row["occupation_code"] == plan["occupationCode"]),
                    next(row["confidence_gate_status"] for row in cohort
                         if row["occupation_code"] == plan["occupationCode"]),
                    plan["scoringEligibility"], plan["publishable"],
                    version_bundle["frontierIndexVersion"], version_bundle["frontierTrack"],
                    version_bundle["structuralProxyModelVersion"],
                    version_bundle["baseProxyModelVersion"],
                    version_bundle["occupationFormulaVersion"],
                    dumps(version_bundle["taskFormulaVersions"]),
                    version_bundle["capabilityTaxonomyVersion"],
                    version_bundle["mappingRubricVersion"],
                    version_bundle["evidencePolicyVersion"],
                    next(row["calculated_at"] for row in cohort
                         if row["occupation_code"] == plan["occupationCode"]),
                    dumps(decoded(next(row["exact_inputs"] for row in cohort
                                       if row["occupation_code"] == plan["occupationCode"]))),
                    dumps(decoded(next(row["provisional_sensitivity"] for row in cohort
                                       if row["occupation_code"] == plan["occupationCode"]))),
                    dumps(decoded(next(row["warnings"] for row in cohort
                                       if row["occupation_code"] == plan["occupationCode"])) or []),
                    dumps(decoded(next(row["blocking_reasons"] for row in cohort
                                       if row["occupation_code"] == plan["occupationCode"])) or []),
                    dumps(plan["reconciliation"]),
                    canonical_hash({"code": plan["occupationCode"],
                                    "exposure": plan["aiExposure"],
                                    "replacement": plan["replacementRisk"],
                                    "bundle": version_bundle}),
                    source_id,
                    dumps({"phase": "6", "promotedFrom": calculation_run["run_version"],
                           "triageRun": triage_run_key, "public": False}))

                await connection.executemany("""
                  INSERT INTO production_score_factor_contributions (
                    snapshot_id, factor_key, factor_label, value, source_proxy_value,
                    transformation, weight, weighted_contribution, is_provisional_proxy,
                    proxy_model_version, placeholder, display_order)
                  VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                """, [(
                    snapshot_id, item["factor"],
                    FACTOR_LABELS.get(item["factor"], item["factor"]),
                    round(float(item["value"]), 4),
                    round(100.0 - float(item["value"]), 4) if item["factor"] in INVERSE_FACTORS
                    else round(float(item["value"]), 4),
                    "inverse: 100 - raw" if item["factor"] in INVERSE_FACTORS else "identity",
                    float(item["weight"]), round(float(item["weightedContribution"]), 4),
                    bool(item.get("provisionalProxy")), item.get("proxyModelVersion"),
                    bool(item.get("placeholder")),
                    FACTOR_ORDER.index(item["factor"]) + 1 if item["factor"] in FACTOR_ORDER else 99,
                ) for item in plan["factors"]])

                await connection.executemany("""
                  INSERT INTO production_score_task_contributions (
                    snapshot_id, onet_task_id, onet_soc_code, task_statement, task_statement_hash,
                    ai_capability_fit, automation_feasibility, augmentation_potential,
                    task_ai_exposure, task_confidence, source_importance, source_frequency,
                    source_weight, normalized_covered_weight, exposure_contribution,
                    weighting_eligible)
                  SELECT $1, assessment.onet_task_id, $2, task.statement, scope.task_statement_hash,
                         assessment.ai_capability_fit, assessment.automation_feasibility,
                         assessment.augmentation_potential, assessment.task_ai_exposure,
                         assessment.confidence, task.importance_score, task.frequency_score,
                         assessment.source_weight, $3, $4, true
                  FROM phase5_task_assessments assessment
                  JOIN onet_tasks task ON task.task_id = assessment.onet_task_id
                  JOIN phase5_task_mapping_scope scope
                    ON scope.onet_task_id = assessment.onet_task_id
                   AND scope.namespace_id = $5
                  WHERE assessment.calculation_run_id = $6 AND assessment.onet_task_id = $7
                """, [(
                    snapshot_id, plan["occupationCode"],
                    round(float(item["normalizedCoveredWeight"]), 6),
                    round(float(item["aiExposureContribution"]), 4),
                    calculation_run["namespace_id"], calculation_run["id"], item["onetTaskId"],
                ) for item in plan["tasks"]])

            # Verify what was written, not what was intended.
            written = await connection.fetchrow("""
              SELECT count(*) snapshots,
                     count(*) FILTER (WHERE publishable) publishable,
                     count(*) FILTER (WHERE augmentation_potential IS NOT NULL) augmentation_rows
              FROM production_occupation_score_snapshots WHERE promotion_run_id = $1
            """, run_id)
            if written["snapshots"] != len(plans):
                raise ValueError("Snapshot count does not match the approved cohort")
            if written["augmentation_rows"]:
                raise ValueError("Occupation-level augmentation must not be promoted")

            drift = await connection.fetch("""
              SELECT snapshot.id,
                     round(abs(coalesce(sum(factor.weighted_contribution),0)
                               - snapshot.replacement_risk), 4) AS factor_drift
              FROM production_occupation_score_snapshots snapshot
              LEFT JOIN production_score_factor_contributions factor ON factor.snapshot_id = snapshot.id
              WHERE snapshot.promotion_run_id = $1
              GROUP BY snapshot.id, snapshot.replacement_risk
              HAVING round(abs(coalesce(sum(factor.weighted_contribution),0)
                               - snapshot.replacement_risk), 4) > $2
            """, run_id, RECONCILIATION_TOLERANCE)
            if drift:
                raise ValueError(
                    f"{len(drift)} promoted snapshots do not reconcile against their persisted "
                    "factor contributions")

            task_drift = await connection.fetch("""
              SELECT snapshot.id,
                     round(abs(coalesce(sum(task.exposure_contribution),0)
                               - snapshot.ai_exposure), 4) AS exposure_drift
              FROM production_occupation_score_snapshots snapshot
              LEFT JOIN production_score_task_contributions task ON task.snapshot_id = snapshot.id
              WHERE snapshot.promotion_run_id = $1
              GROUP BY snapshot.id, snapshot.ai_exposure
              HAVING round(abs(coalesce(sum(task.exposure_contribution),0)
                               - snapshot.ai_exposure), 4) > $2
            """, run_id, RECONCILIATION_TOLERANCE)
            if task_drift:
                raise ValueError(
                    f"{len(task_drift)} promoted snapshots do not reconcile against their "
                    "persisted task contributions")

            reconciliation = {
                "snapshots": written["snapshots"],
                "publishable": written["publishable"],
                "factorReconciliationFailures": 0,
                "taskReconciliationFailures": 0,
                "augmentationPromoted": 0,
                "publicActivations": 0,
                "passed": True,
            }
            await connection.execute("""
              UPDATE production_promotion_runs
              SET status='completed', completed_at=now(), occupation_count=$2,
                  reconciliation=$3::jsonb
              WHERE id=$1
            """, run_id, written["snapshots"], dumps(reconciliation))

            isolation_after = plain(await isolation_snapshot(connection))
            if isolation_after != summary["isolationBefore"]:
                raise ValueError(
                    f"Isolation violation: {summary['isolationBefore']} became {isolation_after}")
            if verify_then_rollback:
                # Exercises the entire write path and every post-write verification, then
                # discards it. Proves the promotion works before the first real one runs.
                await transaction.rollback()
                summary["persisted"] = False
                summary["verifiedThenRolledBack"] = True
                summary["reconciliation"] = reconciliation
                summary["isolationAfter"] = isolation_after
                return summary
            await transaction.commit()
        except Exception:
            await transaction.rollback()
            raise

        summary["persisted"] = True
        summary["promotionRunId"] = run_id
        summary["reconciliation"] = reconciliation
        summary["isolationAfter"] = isolation_after
        return summary
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-key", required=True)
    parser.add_argument("--triage-run-key", required=True)
    parser.add_argument("--approved-codes-file",
                        help="Newline-delimited SOC codes. Must be a subset of the eligible cohort.")
    parser.add_argument("--approve-full-cohort", action="store_true",
                        help="Approve every launch-eligible occupation in the named triage run.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and report without writing anything.")
    parser.add_argument("--expect-count", type=int,
                        help="Refuse unless the approved cohort resolves to exactly this many.")
    parser.add_argument("--verify-then-rollback", action="store_true",
                        help="Execute the full write and all post-write checks, then roll back. "
                             "Leaves no production data; proves the transaction before it is used.")
    args = parser.parse_args()

    approved: set[str] | None = None
    if args.approved_codes_file:
        with open(args.approved_codes_file, encoding="utf-8") as handle:
            approved = {line.strip() for line in handle if line.strip()
                        and not line.startswith("#")}
    print(json.dumps(await run(args.run_key, args.triage_run_key, approved,
                               args.approve_full_cohort, args.dry_run,
                               args.verify_then_rollback, args.expect_count),
                     indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
