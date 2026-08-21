"""Run launch-quality triage over persisted Phase 5 candidate scores.

Read-only with respect to every phase5_* table. Writes only to the phase6_launch_triage_*
tables created in migration 027. Makes no AI calls and does not rescore: it reads what the
Phase 5 run already persisted and classifies it.

  docker compose run --rm worker python -m scoring.run_phase6_launch_triage \
      --run-version phase6-triage-2026q3-v1

Add --dry-run to print the report without writing anything.
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

try:
    from .phase6_launch_triage import GATES, TRIAGE_POLICY_VERSION, triage_corpus
except ImportError:  # Direct script execution from /app/scoring.
    from phase6_launch_triage import GATES, TRIAGE_POLICY_VERSION, triage_corpus


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


async def latest_calculation_run(
    connection: asyncpg.Connection, run_version: str | None = None
) -> asyncpg.Record:
    """The candidate run to triage. Named explicitly, or the most recent bounded corpus."""
    if run_version is not None:
        run = await connection.fetchrow("""
          SELECT id, run_version, run_kind, created_at
          FROM phase5_calculation_runs
          WHERE run_version = $1 AND run_kind = 'bounded_corpus'
        """, run_version)
        if run is None:
            raise SystemExit(f"No bounded_corpus calculation run named {run_version}.")
        return run
    run = await connection.fetchrow("""
      SELECT id, run_version, run_kind, created_at
      FROM phase5_calculation_runs
      WHERE run_kind = 'bounded_corpus'
      ORDER BY created_at DESC, id DESC LIMIT 1
    """)
    if run is None:
        raise SystemExit(
            "No Phase 5 bounded_corpus calculation run found. Run the Phase 5 corpus scoring "
            "first; triage classifies persisted candidates and never produces them."
        )
    return run


async def load_candidates(connection: asyncpg.Connection, calculation_run_id: int) -> list[dict[str, Any]]:
    """Every candidate in the run, in the shape `phase6_launch_triage` expects."""
    rows = await connection.fetch("""
      SELECT score.candidate_occupation_id,
             candidate.occupation_code,
             candidate.title_snapshot AS title,
             score.calculation_status,
             score.candidate_status,
             score.coverage_gate_status,
             score.confidence_gate_status,
             score.ai_exposure,
             score.replacement_risk,
             score.confidence,
             score.weighted_task_coverage,
             score.provisional_sensitivity,
             score.factor_contributions,
             score.task_contributions,
             score.structural_proxy_inputs,
             score.reconciliation,
             score.warnings
      FROM phase5_occupation_scores score
      JOIN phase5_candidate_occupations candidate ON candidate.id = score.candidate_occupation_id
      WHERE score.calculation_run_id = $1
      ORDER BY candidate.occupation_code
    """, calculation_run_id)

    return [{
        "candidateOccupationId": row["candidate_occupation_id"],
        "occupationCode": row["occupation_code"],
        "title": row["title"],
        "calculationStatus": row["calculation_status"],
        "candidateStatus": row["candidate_status"],
        "coverageGateStatus": row["coverage_gate_status"],
        "confidenceGateStatus": row["confidence_gate_status"],
        "aiExposure": plain(row["ai_exposure"]),
        "replacementRisk": plain(row["replacement_risk"]),
        "confidence": plain(row["confidence"]),
        "weightedTaskCoverage": plain(row["weighted_task_coverage"]),
        "provisionalSensitivity": decoded(row["provisional_sensitivity"]),
        "factorContributions": decoded(row["factor_contributions"]),
        "taskContributions": decoded(row["task_contributions"]),
        "structuralProxyInputs": decoded(row["structural_proxy_inputs"]),
        "reconciliation": decoded(row["reconciliation"]),
        "warnings": decoded(row["warnings"]),
    } for row in rows]


async def persist(
    connection: asyncpg.Connection, run_version: str, calculation_run_id: int, report: dict[str, Any]
) -> int:
    source_id = await connection.fetchval("SELECT id FROM data_sources ORDER BY id LIMIT 1")
    triage_run_id = await connection.fetchval("""
      INSERT INTO phase6_launch_triage_runs (
        run_key, policy_version, source_calculation_run_id, gates,
        candidates_assessed, launch_cohort_size, excluded_count,
        severity_totals, finding_totals, exclusion_reasons, cohort_selection,
        input_hash, source_id, provenance, created_by)
      VALUES ($1,$2,$3,$4::jsonb,$5,$6,$7,$8::jsonb,$9::jsonb,$10::jsonb,$11,$12,$13,$14::jsonb,$15)
      RETURNING id
    """, run_version, TRIAGE_POLICY_VERSION, calculation_run_id, json.dumps(GATES),
         report["candidatesAssessed"], report["launchCohortSize"], report["excludedCount"],
         json.dumps(report["severityTotals"]), json.dumps(report["findingTotals"]),
         json.dumps(report["exclusionReasons"]), report["cohortSelection"],
         canonical_hash({"policy": TRIAGE_POLICY_VERSION, "run": calculation_run_id, "gates": GATES}),
         source_id, json.dumps({"readOnlyOverPhase5": True, "aiCalls": 0}), "system:phase6-triage")

    for item in report["results"]:
        await connection.execute("""
          INSERT INTO phase6_launch_triage_results (
            triage_run_id, candidate_occupation_id, occupation_code, title,
            ai_exposure, replacement_risk, confidence, weighted_task_coverage,
            launch_eligible, highest_severity, blocking_codes, severity_counts, findings)
          VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12::jsonb,$13::jsonb)
        """, triage_run_id, item["candidateOccupationId"], item["occupationCode"], item["title"],
             item["aiExposure"], item["replacementRisk"], item["confidence"],
             item["weightedTaskCoverage"], item["launchEligible"], item["highestSeverity"],
             json.dumps(item["blockingCodes"]), json.dumps(item["severityCounts"]),
             json.dumps(item["findings"]))
    return triage_run_id


def summarise(report: dict[str, Any], run: asyncpg.Record) -> dict[str, Any]:
    """The operator-facing summary. Deliberately excludes per-occupation detail."""
    excluded = [item for item in report["results"] if not item["launchEligible"]]
    return {
        "policyVersion": report["policyVersion"],
        "sourceCalculationRun": {"id": run["id"], "version": run["run_version"]},
        "candidatesAssessed": report["candidatesAssessed"],
        "launchCohortSize": report["launchCohortSize"],
        "excludedCount": report["excludedCount"],
        "cohortSelection": report["cohortSelection"],
        "severityTotals": report["severityTotals"],
        "exclusionReasons": report["exclusionReasons"],
        "findingTotals": report["findingTotals"],
        "cohortWithMediumFindings": report["occupationsWithMediumFindings"],
        "excludedByHighestSeverity": {
            severity: sum(1 for item in excluded if item["highestSeverity"] == severity)
            for severity in ("critical", "high")
        },
        "sampleExclusions": [
            {"occupationCode": item["occupationCode"], "title": item["title"],
             "highestSeverity": item["highestSeverity"], "blockingCodes": item["blockingCodes"]}
            for item in excluded[:25]
        ],
    }


async def run(
    run_version: str, dry_run: bool, source_run_version: str | None = None
) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    try:
        calculation_run = await latest_calculation_run(connection, source_run_version)
        candidates = await load_candidates(connection, calculation_run["id"])
        if not candidates:
            raise SystemExit(f"Calculation run {calculation_run['run_version']} has no persisted scores.")

        report = triage_corpus(candidates)
        summary = summarise(report, calculation_run)

        if dry_run:
            summary["persisted"] = False
            return summary

        transaction = connection.transaction()
        await transaction.start()
        try:
            triage_run_id = await persist(connection, run_version, calculation_run["id"], report)
            await transaction.commit()
        except Exception:
            await transaction.rollback()
            raise
        summary["persisted"] = True
        summary["triageRunId"] = triage_run_id
        return summary
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-version", required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="Classify and print without writing anything.")
    parser.add_argument("--source-run-version",
                        help="Phase 5 bounded_corpus run to triage. Defaults to the most recent.")
    args = parser.parse_args()
    print(json.dumps(await run(args.run_version, args.dry_run, args.source_run_version), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
