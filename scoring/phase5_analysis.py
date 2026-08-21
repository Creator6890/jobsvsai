"""Deterministic corpus diagnostics and anomaly rules for Phase 5."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from typing import Any

try:
    from .pilot import canonical_hash, rounded
except ImportError:
    from pilot import canonical_hash, rounded


POLICY_VERSION = "phase5-corpus-anomaly-policy-v2"
THRESHOLDS = {
    "extremeLow": 5,
    "extremeHigh": 95,
    "maximumExtremeShare": 0.20,
    "minimumStandardDeviation": 5,
    "severeConstraint": 70,
    "highReplacementRisk": 70,
    "digitalPhysicalMaximum": 30,
    "digitalHumanMaximum": 40,
    "digitalAdoptionMinimum": 65,
    "digitalAutomationMinimum": 70,
    "lowReplacementRisk": 40,
    "exposureReplacementGap": 25,
    "relatedSocDiscontinuity": 30,
    "singleFactorShare": 0.55,
    "singleTaskShare": 0.25,
    "provisionalSensitivity": 3,
    "launchMinimumCoverage": 80,
    "launchMinimumConfidence": 75,
    "launchTargetCount": 400,
}
CHECKS = [
    "extreme_score_saturation",
    "unexpected_near_zero_variance",
    "score_out_of_range",
    "confidence_coverage_inconsistency",
    "high_replacement_despite_severe_constraints",
    "low_replacement_despite_digital_routine_composition",
    "related_soc_score_discontinuity",
    "single_factor_dependence",
    "single_task_dependence",
    "exposure_replacement_gap",
    "provisional_input_sensitivity",
]


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return rounded(ordered[lower])
    return rounded(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower))


def distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "minimum": rounded(min(values)),
        "p05": percentile(values, .05),
        "p10": percentile(values, .10),
        "p25": percentile(values, .25),
        "median": percentile(values, .50),
        "p75": percentile(values, .75),
        "p90": percentile(values, .90),
        "p95": percentile(values, .95),
        "maximum": rounded(max(values)),
        "mean": rounded(statistics.fmean(values)),
        "standardDeviation": rounded(statistics.pstdev(values)),
    }


def pearson(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right)
    )
    return rounded(numerator / denominator if denominator else 0.0)


def finding(
    anomaly_type: str,
    severity: str,
    explanation: str,
    metric_values: dict[str, Any],
    threshold_values: dict[str, Any],
    occupation_id: int | None = None,
) -> dict[str, Any]:
    payload = {
        "candidateOccupationId": occupation_id,
        "anomalyType": anomaly_type,
        "severity": severity,
        "metricValues": metric_values,
        "thresholdValues": threshold_values,
        "explanation": explanation,
    }
    payload["inputHash"] = canonical_hash(payload)
    return payload


def analyze(
    occupations: list[dict[str, Any]],
    total_source_occupations: int,
    mapping_counts: dict[str, int],
    external_ai_calls: int,
    estimated_ai_tokens: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scored = [row for row in occupations if row["calculationStatus"] == "scored"]
    exposures = [float(row["aiExposure"]) for row in scored]
    replacements = [float(row["replacementRisk"]) for row in scored]
    confidences = [float(row["confidence"]) for row in occupations]
    coverages = [float(row["coverage"]) for row in occupations]
    anomalies: list[dict[str, Any]] = []

    for name, values in (("aiExposure", exposures), ("replacementRisk", replacements)):
        extreme_count = sum(value <= THRESHOLDS["extremeLow"] or value >= THRESHOLDS["extremeHigh"] for value in values)
        extreme_share = extreme_count / len(values) if values else 0.0
        if extreme_share > THRESHOLDS["maximumExtremeShare"]:
            anomalies.append(finding(
                "extreme_score_saturation", "error",
                f"{name} has an excessive share of values in the extreme tails.",
                {"metric": name, "extremeCount": extreme_count, "extremeShare": rounded(extreme_share)},
                {"low": THRESHOLDS["extremeLow"], "high": THRESHOLDS["extremeHigh"],
                 "maximumShare": THRESHOLDS["maximumExtremeShare"]},
            ))
        standard_deviation = statistics.pstdev(values) if len(values) > 1 else 0.0
        if standard_deviation < THRESHOLDS["minimumStandardDeviation"]:
            anomalies.append(finding(
                "unexpected_near_zero_variance", "error",
                f"{name} variance is below the configured corpus minimum.",
                {"metric": name, "standardDeviation": rounded(standard_deviation)},
                {"minimumStandardDeviation": THRESHOLDS["minimumStandardDeviation"]},
            ))

    for row in occupations:
        occupation_id = row["candidateOccupationId"]
        if row["calculationStatus"] == "scored":
            values = {"aiExposure": row["aiExposure"], "replacementRisk": row["replacementRisk"],
                      "confidence": row["confidence"], "coverage": row["coverage"]}
            if any(float(value) < 0 or float(value) > 100 for value in values.values()):
                anomalies.append(finding(
                    "score_out_of_range", "error", "A persisted candidate metric is outside 0–100.",
                    values, {"minimum": 0, "maximum": 100}, occupation_id,
                ))
        if (row["coverage"] < 70 and row["candidateStatus"] != "blocked") or (
            row["candidateStatus"] == "review_ready" and row["confidence"] < 70
        ):
            anomalies.append(finding(
                "confidence_coverage_inconsistency", "error",
                "Candidate status conflicts with the unchanged coverage or confidence gate.",
                {"coverage": row["coverage"], "confidence": row["confidence"],
                 "candidateStatus": row["candidateStatus"]},
                {"minimumCoverage": 70, "minimumConfidence": 70}, occupation_id,
            ))
        if row["calculationStatus"] != "scored":
            continue
        proxy = row["proxyValues"]
        if row["replacementRisk"] >= THRESHOLDS["highReplacementRisk"] and (
            proxy["physical-presence"] >= THRESHOLDS["severeConstraint"]
            or proxy["human-dependency"] >= THRESHOLDS["severeConstraint"]
        ):
            anomalies.append(finding(
                "high_replacement_despite_severe_constraints", "warning",
                "Replacement Risk is high despite a severe physical or human constraint signal.",
                {"replacementRisk": row["replacementRisk"], "physicalPresence": proxy["physical-presence"],
                 "humanDependency": proxy["human-dependency"]},
                {"highReplacementRisk": THRESHOLDS["highReplacementRisk"],
                 "severeConstraint": THRESHOLDS["severeConstraint"]}, occupation_id,
            ))
        task_automation = next(
            (factor["value"] for factor in row["factors"] if factor["factor"] == "taskAutomationExposure"), 0
        )
        if (
            row["replacementRisk"] <= THRESHOLDS["lowReplacementRisk"]
            and proxy["physical-presence"] <= THRESHOLDS["digitalPhysicalMaximum"]
            and proxy["human-dependency"] <= THRESHOLDS["digitalHumanMaximum"]
            and proxy["adoption-pressure"] >= THRESHOLDS["digitalAdoptionMinimum"]
            and task_automation >= THRESHOLDS["digitalAutomationMinimum"]
        ):
            anomalies.append(finding(
                "low_replacement_despite_digital_routine_composition", "warning",
                "Replacement Risk is low despite a highly digital, automation-feasible task composition.",
                {"replacementRisk": row["replacementRisk"], "physicalPresence": proxy["physical-presence"],
                 "humanDependency": proxy["human-dependency"], "adoptionPressure": proxy["adoption-pressure"],
                 "taskAutomationExposure": task_automation},
                {key: THRESHOLDS[key] for key in (
                    "lowReplacementRisk", "digitalPhysicalMaximum", "digitalHumanMaximum",
                    "digitalAdoptionMinimum", "digitalAutomationMinimum")}, occupation_id,
            ))
        gap = float(row["aiExposure"]) - float(row["replacementRisk"])
        if abs(gap) >= THRESHOLDS["exposureReplacementGap"]:
            anomalies.append(finding(
                "exposure_replacement_gap", "warning",
                "AI Exposure and Replacement Risk differ by more than the configured review threshold.",
                {"aiExposure": row["aiExposure"], "replacementRisk": row["replacementRisk"],
                 "signedGap": rounded(gap)},
                {"absoluteGap": THRESHOLDS["exposureReplacementGap"]}, occupation_id,
            ))
        factor_total = sum(abs(float(item["weightedContribution"])) for item in row["factors"])
        largest_factor = max(row["factors"], key=lambda item: abs(float(item["weightedContribution"])))
        factor_share = abs(float(largest_factor["weightedContribution"])) / factor_total if factor_total else 0
        if factor_share >= THRESHOLDS["singleFactorShare"]:
            anomalies.append(finding(
                "single_factor_dependence", "warning",
                "Replacement Risk depends excessively on one factor contribution.",
                {"factor": largest_factor["factor"], "share": rounded(factor_share),
                 "weightedContribution": largest_factor["weightedContribution"]},
                {"maximumShare": THRESHOLDS["singleFactorShare"]}, occupation_id,
            ))
        if row["tasks"]:
            largest_task_share = max(float(item["normalizedCoveredWeight"]) for item in row["tasks"])
            if largest_task_share >= THRESHOLDS["singleTaskShare"]:
                anomalies.append(finding(
                    "single_task_dependence", "warning",
                    "Occupation aggregation depends excessively on one covered task.",
                    {"largestNormalizedCoveredTaskWeight": rounded(largest_task_share)},
                    {"maximumShare": THRESHOLDS["singleTaskShare"]}, occupation_id,
                ))
        if row["provisionalSensitivity"]["maximumAbsoluteScoreImpact"] >= THRESHOLDS["provisionalSensitivity"]:
            anomalies.append(finding(
                "provisional_input_sensitivity", "warning",
                "Candidate score is materially sensitive to regulation, adoption, or labour-market provisional inputs.",
                row["provisionalSensitivity"],
                {"minimumAbsoluteImpact": THRESHOLDS["provisionalSensitivity"]}, occupation_id,
            ))

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored:
        groups[row["occupationCode"][:5]].append(row)
    soc_outliers: list[dict[str, Any]] = []
    for family, rows in groups.items():
        if len(rows) < 2:
            continue
        exposure_range = max(row["aiExposure"] for row in rows) - min(row["aiExposure"] for row in rows)
        replacement_range = max(row["replacementRisk"] for row in rows) - min(row["replacementRisk"] for row in rows)
        if max(exposure_range, replacement_range) < THRESHOLDS["relatedSocDiscontinuity"]:
            continue
        item = {
            "socFamily": family,
            "occupationCount": len(rows),
            "aiExposureRange": rounded(exposure_range),
            "replacementRiskRange": rounded(replacement_range),
            "occupations": [
                {"candidateOccupationId": row["candidateOccupationId"], "occupationCode": row["occupationCode"],
                 "title": row["title"], "aiExposure": row["aiExposure"],
                 "replacementRisk": row["replacementRisk"]}
                for row in sorted(rows, key=lambda value: value["occupationCode"])
            ],
        }
        soc_outliers.append(item)
        for row in rows:
            anomalies.append(finding(
                "related_soc_score_discontinuity", "warning",
                "Closely related SOC occupations have an unusually wide candidate-score range; no value was tuned.",
                {"socFamily": family, "aiExposureRange": rounded(exposure_range),
                 "replacementRiskRange": rounded(replacement_range)},
                {"maximumExpectedRange": THRESHOLDS["relatedSocDiscontinuity"]},
                row["candidateOccupationId"],
            ))

    anomaly_counts = Counter(item["candidateOccupationId"] for item in anomalies if item["candidateOccupationId"] is not None)
    error_occupations = {
        item["candidateOccupationId"] for item in anomalies
        if item["candidateOccupationId"] is not None and item["severity"] == "error"
    }
    launch_pool = [
        row for row in occupations
        if row["candidateStatus"] == "review_ready"
        and row["candidateOccupationId"] not in error_occupations
    ]
    launch_pool.sort(key=lambda row: (
        row["provisionalSensitivity"]["maximumAbsoluteScoreImpact"] >= THRESHOLDS["provisionalSensitivity"],
        anomaly_counts[row["candidateOccupationId"]],
        -row["confidence"], -row["coverage"], row["occupationCode"],
    ))
    recommended = launch_pool[:THRESHOLDS["launchTargetCount"]]

    sorted_exposure = sorted(scored, key=lambda row: row["aiExposure"])
    sorted_replacement = sorted(scored, key=lambda row: row["replacementRisk"])
    sorted_gap = sorted(scored, key=lambda row: abs(row["aiExposure"] - row["replacementRisk"]), reverse=True)
    top_n = lambda rows: [
        {"occupationCode": row["occupationCode"], "title": row["title"],
         "aiExposure": row["aiExposure"], "replacementRisk": row["replacementRisk"],
         "confidence": row["confidence"], "coverage": row["coverage"]}
        for row in rows
    ]
    provisional_sorted = sorted(
        scored, key=lambda row: row["provisionalSensitivity"]["maximumAbsoluteScoreImpact"], reverse=True
    )
    severity_counts = Counter(item["severity"] for item in anomalies)
    type_counts = Counter(item["anomalyType"] for item in anomalies)
    report = {
        "corpusSummary": {
            "totalSourceOccupations": total_source_occupations,
            "scoringReadyOccupationsAttempted": len(occupations),
            "candidateCalculationsCompleted": len(scored),
            "reviewReadyOccupations": sum(row["candidateStatus"] == "review_ready" for row in occupations),
            "blockedOccupations": sum(row["candidateStatus"] == "blocked" for row in occupations),
            "coverageBlockedOccupations": sum(row["coverage"] < 70 for row in occupations),
            "confidenceBlockedOccupations": sum(row["coverage"] >= 70 and row["confidence"] < 70 for row in occupations),
            "publicActivations": 0,
            "productionScoreWrites": 0,
        },
        "distributions": {
            "weightedCoverage": distribution(coverages),
            "confidence": distribution(confidences),
            "aiExposure": distribution(exposures),
            "replacementRisk": distribution(replacements),
        },
        "percentiles": {
            "fractions": [0, .05, .10, .25, .50, .75, .90, .95, 1],
            "aiExposure": [percentile(exposures, fraction) for fraction in (0, .05, .10, .25, .50, .75, .90, .95, 1)],
            "replacementRisk": [percentile(replacements, fraction) for fraction in (0, .05, .10, .25, .50, .75, .90, .95, 1)],
        },
        "correlation": {
            "metric": "pearson",
            "aiExposureVsReplacementRisk": pearson(exposures, replacements),
            "count": len(scored),
        },
        "extremes": {
            "highestAiExposure": top_n(sorted_exposure[-20:][::-1]),
            "lowestAiExposure": top_n(sorted_exposure[:20]),
            "highestReplacementRisk": top_n(sorted_replacement[-20:][::-1]),
            "lowestReplacementRisk": top_n(sorted_replacement[:20]),
            "largestExposureReplacementGaps": top_n(sorted_gap[:30]),
        },
        "socOutliers": sorted(soc_outliers, key=lambda row: max(row["aiExposureRange"], row["replacementRiskRange"]), reverse=True),
        "provisionalImpact": {
            "flagThreshold": THRESHOLDS["provisionalSensitivity"],
            "flaggedOccupations": sum(
                row["provisionalSensitivity"]["maximumAbsoluteScoreImpact"] >= THRESHOLDS["provisionalSensitivity"]
                for row in scored
            ),
            "highestImpact": [
                {"occupationCode": row["occupationCode"], "title": row["title"],
                 **row["provisionalSensitivity"]}
                for row in provisional_sorted[:30]
            ],
        },
        "anomalySummary": {
            "totalFindings": len(anomalies),
            "bySeverity": dict(severity_counts),
            "byType": dict(type_counts),
            "occupationsFlagged": len(anomaly_counts),
        },
        "mappingReuseSummary": {
            **mapping_counts,
            "externalAiCalls": external_ai_calls,
            "estimatedAiTokens": estimated_ai_tokens,
        },
        "recommendedLaunchCohort": {
            "status": "identified_not_activated",
            "targetCount": THRESHOLDS["launchTargetCount"],
            "recommendedCount": len(recommended),
            "selectionPolicy": {
                "candidateStatus": "review_ready",
                "minimumCoverage": 70,
                "minimumConfidence": 70,
                "preferredCoverage": THRESHOLDS["launchMinimumCoverage"],
                "preferredConfidence": THRESHOLDS["launchMinimumConfidence"],
                "provisionalSensitivity": "flagged and deprioritized, not hidden or automatically activated",
                "occupationErrorsAllowed": 0,
                "ranking": "low provisional sensitivity, then fewest anomalies, confidence, coverage, SOC",
            },
            "occupations": [
                {"occupationCode": row["occupationCode"], "title": row["title"],
                 "aiExposure": row["aiExposure"], "replacementRisk": row["replacementRisk"],
                 "confidence": row["confidence"], "coverage": row["coverage"],
                 "warningCount": anomaly_counts[row["candidateOccupationId"]]}
                for row in recommended
            ],
            "activated": False,
        },
    }
    return anomalies, report
