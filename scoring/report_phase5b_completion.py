"""Read-only analysis of Phase 5B against Phase 5, and of the re-triage against its baseline.

Produces every number the Phase 5B reports quote. Writes nothing to the database: it reads
the two candidate runs, the two mapping-scope namespaces, the two triage runs and the two
anomaly sets, and emits one JSON payload.

  docker compose run --rm -e PYTHONPATH=/app/scoring worker \
      python -m scoring.report_phase5b_completion --out /tmp/phase5b.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
from collections import defaultdict
from typing import Any

import asyncpg


BASE_RUN = "phase5-bounded-corpus-v2-2026q3"
COMPLETION_RUN = "phase5b-coverage-completion-2026q3-v1"
BASE_NAMESPACE = "phase5-candidate-2026q3-v1"
COMPLETION_NAMESPACE = "phase5b-candidate-2026q3-v1"
BASELINE_TRIAGE = "phase6-triage-2026q3-v1"
COMPLETION_TRIAGE = "phase6-triage-postcoverage-2026q3-v1"

LAUNCH_COVERAGE_GATE = 80.0
LAUNCH_CONFIDENCE_GATE = 75.0
SCORING_ELIGIBILITY_THRESHOLD = 70.0


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def describe(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)

    def percentile(fraction: float) -> float:
        if not ordered:
            return 0.0
        position = fraction * (len(ordered) - 1)
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        weight = position - lower
        return ordered[lower] * (1 - weight) + ordered[upper] * weight

    return {
        "n": len(ordered),
        "mean": round(statistics.fmean(ordered), 4) if ordered else 0.0,
        "sd": round(statistics.pstdev(ordered), 4) if len(ordered) > 1 else 0.0,
        "min": round(ordered[0], 4) if ordered else 0.0,
        "p10": round(percentile(0.10), 4),
        "p25": round(percentile(0.25), 4),
        "p50": round(percentile(0.50), 4),
        "p75": round(percentile(0.75), 4),
        "p90": round(percentile(0.90), 4),
        "p95": round(percentile(0.95), 4),
        "max": round(ordered[-1], 4) if ordered else 0.0,
    }


def bucket(value: float) -> str:
    if value >= 90:
        return "atLeast90"
    if value >= 85:
        return "from85to8999"
    if value >= 80:
        return "from80to8499"
    if value >= 75:
        return "from75to7999"
    if value >= 70:
        return "from70to7499"
    return "below70"


async def scores(connection: asyncpg.Connection, run_version: str) -> dict[str, dict[str, Any]]:
    rows = await connection.fetch("""
      SELECT candidate.occupation_code, candidate.title_snapshot AS title,
             score.ai_exposure, score.replacement_risk, score.confidence,
             score.weighted_task_coverage, score.eligible_task_count, score.source_task_count,
             score.candidate_status, score.coverage_gate_status, score.confidence_gate_status,
             score.provisional_sensitivity, score.factor_contributions
      FROM phase5_occupation_scores score
      JOIN phase5_calculation_runs run ON run.id = score.calculation_run_id
      JOIN phase5_candidate_occupations candidate ON candidate.id = score.candidate_occupation_id
      WHERE run.run_version = $1
    """, run_version)
    return {
        row["occupation_code"]: {
            "title": row["title"],
            "exposure": float(row["ai_exposure"]),
            "replacement": float(row["replacement_risk"]),
            "confidence": float(row["confidence"]),
            "coverage": float(row["weighted_task_coverage"]),
            "eligibleTasks": row["eligible_task_count"],
            "sourceTasks": row["source_task_count"],
            "candidateStatus": row["candidate_status"],
            "coverageGate": row["coverage_gate_status"],
            "confidenceGate": row["confidence_gate_status"],
            "provisionalSensitivity": (
                json.loads(row["provisional_sensitivity"])
                if isinstance(row["provisional_sensitivity"], str)
                else row["provisional_sensitivity"]
            ),
        }
        for row in rows
    }


async def analyse(out_path: str | None) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    try:
        base = await scores(connection, BASE_RUN)
        completed = await scores(connection, COMPLETION_RUN)
        shared = sorted(set(base) & set(completed))

        # ---------------- Step 8: mapping scope, before and after ----------------
        scope_counts: dict[str, dict[str, int]] = {}
        for label, namespace_version in (("phase5", BASE_NAMESPACE), ("phase5b", COMPLETION_NAMESPACE)):
            rows = await connection.fetch("""
              SELECT scope.scope_decision, count(*) AS n
              FROM phase5_task_mapping_scope scope
              JOIN phase5_candidate_namespaces namespace ON namespace.id = scope.namespace_id
              WHERE namespace.namespace_version = $1
              GROUP BY 1
            """, namespace_version)
            scope_counts[label] = {row["scope_decision"]: row["n"] for row in rows}

        # Where every task Phase 5 left after its 70% stopping rule ended up.
        transitions = {
            f'{row["before"]}->{row["after"]}': row["n"]
            for row in await connection.fetch("""
              SELECT before.scope_decision AS before, after.scope_decision AS after, count(*) AS n
              FROM phase5_task_mapping_scope before
              JOIN phase5_candidate_namespaces base_ns ON base_ns.id = before.namespace_id
              JOIN phase5_candidate_namespaces new_ns ON new_ns.namespace_version = $2
              JOIN phase5_task_mapping_scope after
                ON after.namespace_id = new_ns.id AND after.onet_task_id = before.onet_task_id
              WHERE base_ns.namespace_version = $1
              GROUP BY 1,2 ORDER BY 1,2
            """, BASE_NAMESPACE, COMPLETION_NAMESPACE)
        }

        # ---------------- Step 12: why coverage still falls short ----------------
        # Classified from the scope decisions themselves, by residual unmapped weight.
        shortfall_rows = await connection.fetch("""
          SELECT candidate.occupation_code,
                 sum(scope.source_weight) FILTER (
                   WHERE scope.scope_decision = 'unmapped_insufficient_evidence') AS ambiguous_weight,
                 sum(scope.source_weight) FILTER (
                   WHERE scope.scope_decision = 'unmapped_after_gate') AS after_target_weight,
                 count(*) FILTER (WHERE scope.scope_decision = 'source_weight_ineligible') AS missing_weight_tasks,
                 count(*) FILTER (WHERE scope.scope_decision = 'unmapped_insufficient_evidence') AS ambiguous_tasks,
                 count(*) FILTER (WHERE scope.scope_decision = 'unmapped_after_gate') AS after_target_tasks,
                 sum(scope.source_weight) AS weighted_total
          FROM phase5_task_mapping_scope scope
          JOIN phase5_candidate_namespaces namespace ON namespace.id = scope.namespace_id
          JOIN phase5_candidate_occupations candidate ON candidate.id = scope.candidate_occupation_id
          WHERE namespace.namespace_version = $1
          GROUP BY 1
        """, COMPLETION_NAMESPACE)
        shortfall = {row["occupation_code"]: dict(row) for row in shortfall_rows}

        # ---------------- Step 9 / Step 7: score movement ----------------
        deltas: list[dict[str, Any]] = []
        for code in shared:
            before, after = base[code], completed[code]
            deltas.append({
                "occupationCode": code,
                "title": after["title"],
                "exposureBefore": before["exposure"], "exposureAfter": after["exposure"],
                "exposureDelta": round(after["exposure"] - before["exposure"], 4),
                "replacementBefore": before["replacement"], "replacementAfter": after["replacement"],
                "replacementDelta": round(after["replacement"] - before["replacement"], 4),
                "confidenceDelta": round(after["confidence"] - before["confidence"], 4),
                "coverageBefore": before["coverage"], "coverageAfter": after["coverage"],
                "coverageDelta": round(after["coverage"] - before["coverage"], 4),
                "eligibleTaskDelta": after["eligibleTasks"] - before["eligibleTasks"],
            })
        exposure_abs = [abs(item["exposureDelta"]) for item in deltas]
        replacement_abs = [abs(item["replacementDelta"]) for item in deltas]
        combined_abs = [max(a, b) for a, b in zip(exposure_abs, replacement_abs)]
        unchanged = [item for item in deltas if item["eligibleTaskDelta"] == 0]
        rescored = [item for item in deltas if item["eligibleTaskDelta"] != 0]
        unchanged_moved = [
            item for item in unchanged
            if abs(item["exposureDelta"]) > 0.0001 or abs(item["replacementDelta"]) > 0.0001
        ]

        task_counts = {
            label: await connection.fetchval("""
              SELECT count(*) FROM phase5_task_assessments assessment
              JOIN phase5_calculation_runs run ON run.id = assessment.calculation_run_id
              WHERE run.run_version = $1
            """, version)
            for label, version in (("phase5", BASE_RUN), ("phase5b", COMPLETION_RUN))
        }
        # A task assessed in both runs from the same mapping is reused evidence, not new work.
        reused_assessments = await connection.fetchval("""
          SELECT count(*)
          FROM phase5_task_assessments before
          JOIN phase5_calculation_runs base_run ON base_run.id = before.calculation_run_id
          JOIN phase5_calculation_runs new_run ON new_run.run_version = $2
          JOIN phase5_task_assessments after
            ON after.calculation_run_id = new_run.id
           AND after.onet_task_id = before.onet_task_id
           AND after.ai_task_mapping_id = before.ai_task_mapping_id
          WHERE base_run.run_version = $1
        """, BASE_RUN, COMPLETION_RUN)

        # Newly included tasks behind the largest movements.
        biggest = sorted(deltas, key=lambda item: -max(
            abs(item["exposureDelta"]), abs(item["replacementDelta"])))[:10]
        drivers: dict[str, list[dict[str, Any]]] = {}
        for item in biggest:
            rows = await connection.fetch("""
              SELECT task.statement, assessment.task_ai_exposure, assessment.source_weight,
                     assessment.ai_capability_fit, assessment.automation_feasibility
              FROM phase5_task_assessments assessment
              JOIN phase5_calculation_runs run ON run.id = assessment.calculation_run_id
              JOIN phase5_candidate_occupations candidate
                ON candidate.id = assessment.candidate_occupation_id
              JOIN onet_tasks task ON task.task_id = assessment.onet_task_id
              WHERE run.run_version = $1 AND candidate.occupation_code = $2
                AND assessment.onet_task_id NOT IN (
                  SELECT prior.onet_task_id FROM phase5_task_assessments prior
                  JOIN phase5_calculation_runs prior_run ON prior_run.id = prior.calculation_run_id
                  WHERE prior_run.run_version = $3
                )
              ORDER BY assessment.source_weight DESC NULLS LAST
              LIMIT 5
            """, COMPLETION_RUN, item["occupationCode"], BASE_RUN)
            drivers[item["occupationCode"]] = [{
                "statement": row["statement"],
                "taskExposure": float(row["task_ai_exposure"]),
                "sourceWeight": float(row["source_weight"]) if row["source_weight"] is not None else None,
                "capabilityFit": float(row["ai_capability_fit"]),
                "automationFeasibility": float(row["automation_feasibility"]),
            } for row in rows]

        # ---------------- Step 11: cohort membership ----------------
        triage: dict[str, dict[str, dict[str, Any]]] = {}
        for label, run_key in (("baseline", BASELINE_TRIAGE), ("completed", COMPLETION_TRIAGE)):
            rows = await connection.fetch("""
              SELECT result.occupation_code, result.title, result.launch_eligible,
                     result.highest_severity, result.blocking_codes, result.findings,
                     result.ai_exposure, result.replacement_risk, result.confidence,
                     result.weighted_task_coverage
              FROM phase6_launch_triage_results result
              JOIN phase6_launch_triage_runs run ON run.id = result.triage_run_id
              WHERE run.run_key = $1
            """, run_key)
            triage[label] = {
                row["occupation_code"]: {
                    "title": row["title"],
                    "eligible": row["launch_eligible"],
                    "highestSeverity": row["highest_severity"],
                    "blockingCodes": json.loads(row["blocking_codes"])
                    if isinstance(row["blocking_codes"], str) else row["blocking_codes"],
                    "findings": json.loads(row["findings"])
                    if isinstance(row["findings"], str) else row["findings"],
                    "exposure": float(row["ai_exposure"]) if row["ai_exposure"] is not None else None,
                    "replacement": float(row["replacement_risk"]) if row["replacement_risk"] is not None else None,
                    "confidence": float(row["confidence"]),
                    "coverage": float(row["weighted_task_coverage"]),
                }
                for row in rows
            }
        baseline_eligible = {code for code, row in triage["baseline"].items() if row["eligible"]}
        completed_eligible = {code for code, row in triage["completed"].items() if row["eligible"]}

        # Remaining coverage failures, classified by what actually blocks them.
        still_short: list[dict[str, Any]] = []
        for code, row in triage["completed"].items():
            if "weighted_coverage_below_launch_minimum" not in row["blockingCodes"]:
                continue
            detail = shortfall.get(code, {})
            total = float(detail.get("weighted_total") or 0)
            ambiguous = float(detail.get("ambiguous_weight") or 0)
            after_target = float(detail.get("after_target_weight") or 0)
            if total > 0 and ambiguous / total >= 0.10:
                reason = "ambiguous_or_insufficient_task_descriptions"
            elif detail.get("missing_weight_tasks", 0) and ambiguous == 0 and after_target == 0:
                reason = "missing_task_importance_or_frequency"
            elif ambiguous > 0:
                reason = "ambiguous_or_insufficient_task_descriptions"
            elif after_target > 0:
                reason = "mappable_weight_remaining_below_target"
            else:
                reason = "other"
            still_short.append({
                "occupationCode": code, "title": row["title"], "coverage": row["coverage"],
                "reason": reason,
                "ambiguousTasks": detail.get("ambiguous_tasks", 0),
                "afterTargetTasks": detail.get("after_target_tasks", 0),
                "missingWeightTasks": detail.get("missing_weight_tasks", 0),
                "ambiguousWeightShare": round(ambiguous / total, 4) if total else None,
            })
        shortfall_reasons: dict[str, int] = defaultdict(int)
        for item in still_short:
            shortfall_reasons[item["reason"]] += 1

        # ---------------- Step 13: provisional sensitivity ----------------
        def sensitivity_values(source: dict[str, dict[str, Any]]) -> list[float]:
            return [
                float((row["provisionalSensitivity"] or {}).get("maximumAbsoluteScoreImpact", 0.0))
                for row in source.values()
            ]

        completed_sensitivity = {
            code: float((row["provisionalSensitivity"] or {}).get("maximumAbsoluteScoreImpact", 0.0))
            for code, row in completed.items()
        }
        only_sensitivity = sorted(
            code for code, row in triage["completed"].items()
            if row["blockingCodes"] == ["provisional_input_sensitivity"]
        )
        sensitivity_families: dict[str, int] = defaultdict(int)
        for code, value in completed_sensitivity.items():
            if value >= 3.0:
                sensitivity_families[code.split("-")[0]] += 1

        # ---------------- Step 14: anomalies ----------------
        anomalies: dict[str, dict[str, int]] = {}
        anomaly_codes: dict[str, dict[str, list[str]]] = {}
        for label, version in (("phase5", BASE_RUN), ("phase5b", COMPLETION_RUN)):
            rows = await connection.fetch("""
              SELECT finding.anomaly_type, candidate.occupation_code
              FROM phase5_anomaly_findings finding
              JOIN phase5_calculation_runs run ON run.id = finding.calculation_run_id
              JOIN phase5_candidate_occupations candidate ON candidate.id = finding.candidate_occupation_id
              WHERE run.run_version = $1
            """, version)
            counts: dict[str, int] = defaultdict(int)
            by_type: dict[str, list[str]] = defaultdict(list)
            for row in rows:
                counts[row["anomaly_type"]] += 1
                by_type[row["anomaly_type"]].append(row["occupation_code"])
            anomalies[label] = dict(sorted(counts.items()))
            anomaly_codes[label] = {key: sorted(value) for key, value in by_type.items()}

        payload: dict[str, Any] = {
            "runs": {"base": BASE_RUN, "completion": COMPLETION_RUN},
            "mappingScope": {
                "phase5": scope_counts["phase5"],
                "phase5b": scope_counts["phase5b"],
                "transitions": transitions,
            },
            "coverage": {
                "before": describe([row["coverage"] for row in base.values()]),
                "after": describe([row["coverage"] for row in completed.values()]),
                "bucketsBefore": dict(sorted(
                    ((key, sum(1 for row in base.values() if bucket(row["coverage"]) == key))
                     for key in ("atLeast90", "from85to8999", "from80to8499", "from75to7999",
                                 "from70to7499", "below70")))),
                "bucketsAfter": dict(sorted(
                    ((key, sum(1 for row in completed.values() if bucket(row["coverage"]) == key))
                     for key in ("atLeast90", "from85to8999", "from80to8499", "from75to7999",
                                 "from70to7499", "below70")))),
                "atOrAboveLaunchGateBefore": sum(
                    row["coverage"] >= LAUNCH_COVERAGE_GATE for row in base.values()),
                "atOrAboveLaunchGateAfter": sum(
                    row["coverage"] >= LAUNCH_COVERAGE_GATE for row in completed.values()),
                "belowScoringThresholdAfter": sum(
                    row["coverage"] < SCORING_ELIGIBILITY_THRESHOLD for row in completed.values()),
            },
            "confidence": {
                "before": describe([row["confidence"] for row in base.values()]),
                "after": describe([row["confidence"] for row in completed.values()]),
            },
            "evidenceReuse": {
                "taskAssessmentsPhase5": task_counts["phase5"],
                "taskAssessmentsPhase5b": task_counts["phase5b"],
                "assessmentsReusingIdenticalMapping": reused_assessments,
                "newlyAssessedTasks": task_counts["phase5b"] - reused_assessments,
                "occupationsWithNoNewEligibleTask": len(unchanged),
                "occupationsWithNewEligibleTasks": len(rescored),
                "occupationsUnchangedInEvidenceButMovedScore": len(unchanged_moved),
            },
            "scoreImpact": {
                "meanAbsoluteExposureChange": round(statistics.fmean(exposure_abs), 4),
                "meanAbsoluteReplacementChange": round(statistics.fmean(replacement_abs), 4),
                "exposureDeltaDistribution": describe(exposure_abs),
                "replacementDeltaDistribution": describe(replacement_abs),
                "p95AbsoluteScoreDelta": describe(combined_abs)["p95"],
                "maximumExposureChange": round(max(exposure_abs), 4),
                "maximumReplacementChange": round(max(replacement_abs), 4),
                "occupationsOver5Points": sum(value > 5 for value in combined_abs),
                "occupationsOver10Points": sum(value > 10 for value in combined_abs),
                "largestMovements": biggest,
                "largestMovementDrivers": drivers,
            },
            "triageComparison": {
                "baselineCohort": len(baseline_eligible),
                "completedCohort": len(completed_eligible),
                "newlyEligible": sorted(completed_eligible - baseline_eligible),
                "noLongerEligible": sorted(baseline_eligible - completed_eligible),
                "retained": sorted(baseline_eligible & completed_eligible),
            },
            "remainingCoverageFailures": {
                "total": len(still_short),
                "byReason": dict(sorted(shortfall_reasons.items())),
                "occupations": sorted(still_short, key=lambda item: item["coverage"]),
            },
            "provisionalSensitivity": {
                "before": describe(sensitivity_values(base)),
                "after": describe(sensitivity_values(completed)),
                "failingAfter": sum(value >= 3.0 for value in completed_sensitivity.values()),
                "between3And4": sum(3.0 <= value < 4.0 for value in completed_sensitivity.values()),
                "above5": sum(value > 5.0 for value in completed_sensitivity.values()),
                "blockedOnlyByThisRule": only_sensitivity,
                "blockedOnlyByThisRuleCount": len(only_sensitivity),
                "affectedSocFamilies": dict(sorted(sensitivity_families.items())),
            },
            "anomalies": {
                "phase5": anomalies["phase5"],
                "phase5b": anomalies["phase5b"],
                "resolved": {
                    key: sorted(set(anomaly_codes["phase5"].get(key, []))
                                - set(anomaly_codes["phase5b"].get(key, [])))
                    for key in set(anomaly_codes["phase5"]) | set(anomaly_codes["phase5b"])
                },
                "introduced": {
                    key: sorted(set(anomaly_codes["phase5b"].get(key, []))
                                - set(anomaly_codes["phase5"].get(key, [])))
                    for key in set(anomaly_codes["phase5"]) | set(anomaly_codes["phase5b"])
                },
            },
            "launchCohort": sorted(
                ({
                    "occupationCode": code,
                    "title": triage["completed"][code]["title"],
                    "aiExposure": triage["completed"][code]["exposure"],
                    "replacementRisk": triage["completed"][code]["replacement"],
                    "confidence": triage["completed"][code]["confidence"],
                    "weightedTaskCoverage": triage["completed"][code]["coverage"],
                    "mediumFindings": [
                        finding["code"] for finding in triage["completed"][code]["findings"]
                        if finding.get("severity") == "medium"
                    ],
                } for code in completed_eligible),
                key=lambda item: item["occupationCode"],
            ),
        }
        if out_path:
            with open(out_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        return payload
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()
    payload = await analyse(args.out)
    summary = {key: value for key, value in payload.items()
               if key not in ("launchCohort", "remainingCoverageFailures")}
    summary["scoreImpact"] = {
        key: value for key, value in summary["scoreImpact"].items()
        if key not in ("largestMovements", "largestMovementDrivers")
    }
    summary["triageComparison"] = {
        key: (value if not isinstance(value, list) else len(value))
        for key, value in summary["triageComparison"].items()
    }
    summary["remainingCoverageFailureCount"] = payload["remainingCoverageFailures"]["total"]
    summary["remainingCoverageFailuresByReason"] = payload["remainingCoverageFailures"]["byReason"]
    summary["launchCohortSize"] = len(payload["launchCohort"])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
