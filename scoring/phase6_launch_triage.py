"""Deterministic launch-quality triage over persisted Phase 5 candidate scores.

This module is pure: it takes already-persisted candidate rows and returns findings. It
never rescores, never calls an AI model, and never reads the frontier index. Running it
twice over the same rows returns the same findings.

WHY THIS EXISTS, AND WHAT CHANGED FROM PHASE 5
----------------------------------------------
`phase5_analysis.py` already computes eleven anomaly checks, but its launch recommendation
is `launch_pool[:THRESHOLDS["launchTargetCount"]]` — the 400 best-sorted candidates that
carry no `error` finding. Two consequences:

  1. The cohort size is a target, not a quality boundary. If 600 candidates were defensible
     the extra 200 were dropped anyway; if only 250 were, 150 weak ones were included.
  2. `launchMinimumCoverage` (80) and `launchMinimumConfidence` (75) are declared in
     THRESHOLDS but never applied as filters — only as sort keys. They are described in the
     corpus report as "preferred".

This module inverts that. The thresholds are unchanged — they are the project's own stated
launch preferences, and inventing new numbers here would be a methodology change rather than
a triage. What changes is that they are *enforced*, and the cohort is whatever passes.

SEVERITY
--------
critical  Integrity failure or a credibility-destroying contradiction. Never launchable,
          and a signal that something upstream needs investigating.
high      A defensible score that is not defensible *enough* to put a name on at launch.
          Excluded from the initial cohort; revisitable once the weak input improves.
medium    Launchable, but flagged for editorial attention.
low       Informational. Recorded so the corpus is described honestly, never excluding.

Launch eligibility is: no critical findings AND no high findings. Nothing else.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

TRIAGE_POLICY_VERSION = "phase6-launch-triage-v1"

# Inherited verbatim from phase5_analysis.THRESHOLDS. Where Phase 5 declared a launch
# preference we apply it; where it declared an anomaly threshold we reuse it so a finding
# here means the same thing it meant there.
GATES: dict[str, float] = {
    "minimumWeightedCoverage": 80.0,       # phase5 launchMinimumCoverage
    "minimumConfidence": 75.0,             # phase5 launchMinimumConfidence
    "maximumProvisionalSensitivity": 3.0,  # phase5 provisionalSensitivity
    "maximumSingleFactorShare": 0.55,      # phase5 singleFactorShare
    "maximumSingleTaskShare": 0.25,        # phase5 singleTaskShare
    "maximumExposureReplacementGap": 25.0, # phase5 exposureReplacementGap
    "severeConstraintLevel": 70.0,         # phase5 severeConstraint
    "highReplacementRisk": 70.0,           # phase5 highReplacementRisk
    "lowReplacementRisk": 40.0,            # phase5 lowReplacementRisk
    "digitalPhysicalMaximum": 30.0,        # phase5 digitalPhysicalMaximum
    "digitalHumanMaximum": 40.0,           # phase5 digitalHumanMaximum
    "digitalAutomationMinimum": 70.0,      # phase5 digitalAutomationMinimum
    "extremeLow": 5.0,                     # phase5 extremeLow
    "extremeHigh": 95.0,                   # phase5 extremeHigh
    "relatedSocDiscontinuity": 30.0,       # phase5 relatedSocDiscontinuity
}

# finding code -> (severity, one-line justification for that severity)
SEVERITY_POLICY: dict[str, tuple[str, str]] = {
    "score_out_of_range": (
        "critical", "A score outside 0-100 is a calculation integrity failure, not a weak score."),
    "reconciliation_failed": (
        "critical", "Stored contributions do not sum to the stored score; the score cannot be explained."),
    "not_review_ready": (
        "critical", "Candidate did not clear the Phase 5 coverage and confidence gates."),
    "high_replacement_despite_severe_constraints": (
        "critical",
        "High replacement risk for work with severe physical, human or accountability "
        "constraints is the most reputationally damaging failure the product can make."),
    "low_replacement_despite_digital_routine_composition": (
        "critical",
        "Low replacement risk for highly digital, routine work destroys credibility with "
        "exactly the readers most able to judge it."),
    "weighted_coverage_below_launch_minimum": (
        "high", "Below the coverage the project itself set as the launch minimum."),
    "confidence_below_launch_minimum": (
        "high", "Below the confidence the project itself set as the launch minimum."),
    "provisional_input_sensitivity": (
        "high",
        "The score moves materially when the provisional regulation, adoption and "
        "labour-market models are neutralised, so it is really a claim about those models."),
    "single_factor_dependence": (
        "high", "One factor dominates the score, so the published number is that factor wearing a suit."),
    "exposure_replacement_gap": (
        "high", "A large exposure/replacement gap needs an explanation the page cannot yet give."),
    "extreme_score": (
        "high", "Extreme scores attract the most scrutiny and carry the least measurement headroom."),
    "single_task_dependence": (
        "medium", "One task drives most of the exposure; the task mix should be checked editorially."),
    "related_soc_score_discontinuity": (
        "medium", "Neighbouring occupations diverge more than expected; may be real, may be an artefact."),
    "confidence_coverage_inconsistency": (
        "medium", "Confidence and coverage disagree in a way worth an editorial look."),
    "structural_proxy_missing_data": (
        "medium", "A structural proxy fell back to incomplete source evidence."),
    "provisional_models_in_use": (
        "low",
        "Every score carries the provisional adoption and labour-market models at 25% of "
        "replacement weight. Universal, disclosed, and not an exclusion on its own."),
}

BLOCKING_SEVERITIES = ("critical", "high")

# Structural proxy keys that represent real-world resistance to automation.
CONSTRAINT_KEYS = (
    "physical-presence", "environment-variability", "accountability",
    "consequence-severity", "human-dependency", "regulation",
)


def _finding(code: str, detail: str, observed: Any, expected: Any) -> dict[str, Any]:
    severity, justification = SEVERITY_POLICY[code]
    return {
        "code": code,
        "severity": severity,
        "severityJustification": justification,
        "detail": detail,
        "observed": observed,
        "expected": expected,
    }


def triage_occupation(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Findings for one candidate. `row` uses the persisted phase5_occupation_scores shape."""
    findings: list[dict[str, Any]] = []

    exposure = row.get("aiExposure")
    replacement = row.get("replacementRisk")
    coverage = float(row["weightedTaskCoverage"])
    confidence = float(row["confidence"])
    proxy_values = (row.get("structuralProxyInputs") or {}).get("values") or {}

    # --- integrity -----------------------------------------------------------
    if row.get("candidateStatus") != "review_ready":
        findings.append(_finding(
            "not_review_ready", "Candidate is not review-ready.",
            {"candidateStatus": row.get("candidateStatus"),
             "coverageGateStatus": row.get("coverageGateStatus"),
             "confidenceGateStatus": row.get("confidenceGateStatus")},
            {"candidateStatus": "review_ready"}))
        # Everything below assumes a scored candidate; a blocked one has no score to judge.
        if exposure is None or replacement is None:
            return findings

    exposure = float(exposure)
    replacement = float(replacement)

    if not (0 <= exposure <= 100) or not (0 <= replacement <= 100):
        findings.append(_finding(
            "score_out_of_range", "A published score is outside the 0-100 index range.",
            {"aiExposure": exposure, "replacementRisk": replacement}, {"range": [0, 100]}))

    reconciliation = row.get("reconciliation") or {}
    if reconciliation and reconciliation.get("passed") is False:
        findings.append(_finding(
            "reconciliation_failed", "Stored derivation does not reconcile to the stored score.",
            reconciliation, {"passed": True}))

    # --- launch gates the project already declared ---------------------------
    if coverage < GATES["minimumWeightedCoverage"]:
        findings.append(_finding(
            "weighted_coverage_below_launch_minimum",
            "Weighted task coverage is below the declared launch minimum.",
            {"weightedTaskCoverage": coverage},
            {"minimum": GATES["minimumWeightedCoverage"]}))

    if confidence < GATES["minimumConfidence"]:
        findings.append(_finding(
            "confidence_below_launch_minimum",
            "Confidence is below the declared launch minimum.",
            {"confidence": confidence}, {"minimum": GATES["minimumConfidence"]}))

    # --- residual provisional-model uncertainty ------------------------------
    sensitivity = row.get("provisionalSensitivity") or {}
    maximum_impact = float(sensitivity.get("maximumAbsoluteScoreImpact", 0.0))
    if maximum_impact >= GATES["maximumProvisionalSensitivity"]:
        findings.append(_finding(
            "provisional_input_sensitivity",
            "Neutralising the provisional regulation/adoption/labour models moves the score materially.",
            {"maximumAbsoluteScoreImpact": maximum_impact,
             "regulationNeutralReplacementRiskDelta": sensitivity.get("regulationNeutralReplacementRiskDelta"),
             "adoptionNeutralReplacementRiskDelta": sensitivity.get("adoptionNeutralReplacementRiskDelta"),
             "labourNeutralReplacementRiskDelta": sensitivity.get("labourNeutralReplacementRiskDelta")},
            {"maximum": GATES["maximumProvisionalSensitivity"]}))

    findings.append(_finding(
        "provisional_models_in_use",
        "Replacement risk includes the provisional adoption and labour-market proxies.",
        {"provisionalWeightShare": 0.25,
         "provisionalVersions": sensitivity.get("provisionalVersions")},
        {"disclosure": "required on the public page and in the methodology"}))

    # --- single-factor dominance ---------------------------------------------
    factors = row.get("factorContributions") or []
    if factors and replacement > 0:
        dominant = max(factors, key=lambda item: abs(float(item["weightedContribution"])))
        share = abs(float(dominant["weightedContribution"])) / replacement
        if share > GATES["maximumSingleFactorShare"]:
            findings.append(_finding(
                "single_factor_dependence",
                "One factor supplies most of the replacement-risk score.",
                {"factor": dominant["factor"], "share": round(share, 4),
                 "weightedContribution": float(dominant["weightedContribution"])},
                {"maximumShare": GATES["maximumSingleFactorShare"]}))

    # --- single-task dominance ------------------------------------------------
    tasks = row.get("taskContributions") or []
    if tasks and exposure > 0:
        dominant_task = max(tasks, key=lambda item: abs(float(item["aiExposureContribution"])))
        share = abs(float(dominant_task["aiExposureContribution"])) / exposure
        if share > GATES["maximumSingleTaskShare"]:
            findings.append(_finding(
                "single_task_dependence",
                "One task supplies a large share of AI Exposure.",
                {"onetTaskId": dominant_task.get("onetTaskId"),
                 "statement": dominant_task.get("statement"),
                 "share": round(share, 4)},
                {"maximumShare": GATES["maximumSingleTaskShare"]}))

    # --- exposure vs replacement ---------------------------------------------
    gap = abs(exposure - replacement)
    if gap >= GATES["maximumExposureReplacementGap"]:
        findings.append(_finding(
            "exposure_replacement_gap",
            "AI Exposure and Replacement Risk diverge more than the page can currently explain.",
            {"aiExposure": exposure, "replacementRisk": replacement, "gap": round(gap, 4)},
            {"maximumGap": GATES["maximumExposureReplacementGap"]}))

    # --- structural contradictions -------------------------------------------
    severe = {
        key: float(proxy_values[key]) for key in CONSTRAINT_KEYS
        if key in proxy_values and float(proxy_values[key]) >= GATES["severeConstraintLevel"]
    }
    if severe and replacement >= GATES["highReplacementRisk"]:
        findings.append(_finding(
            "high_replacement_despite_severe_constraints",
            "High replacement risk despite severe real-world constraints.",
            {"replacementRisk": replacement, "severeConstraints": severe},
            {"maximumReplacementRisk": GATES["highReplacementRisk"],
             "severeConstraintLevel": GATES["severeConstraintLevel"]}))

    physical = float(proxy_values.get("physical-presence", 100.0))
    human = float(proxy_values.get("human-dependency", 100.0))
    automation_factor = next(
        (float(item["value"]) for item in factors if item["factor"] == "taskAutomationExposure"), 0.0)
    if (replacement <= GATES["lowReplacementRisk"]
            and physical <= GATES["digitalPhysicalMaximum"]
            and human <= GATES["digitalHumanMaximum"]
            and automation_factor >= GATES["digitalAutomationMinimum"]):
        findings.append(_finding(
            "low_replacement_despite_digital_routine_composition",
            "Low replacement risk for highly digital, highly automatable work.",
            {"replacementRisk": replacement, "physicalPresence": physical,
             "humanDependency": human, "taskAutomationExposure": automation_factor},
            {"minimumReplacementRisk": GATES["lowReplacementRisk"]}))

    # --- extremes and coherence ----------------------------------------------
    if exposure <= GATES["extremeLow"] or exposure >= GATES["extremeHigh"] \
            or replacement <= GATES["extremeLow"] or replacement >= GATES["extremeHigh"]:
        findings.append(_finding(
            "extreme_score", "A published score sits at the extreme of the index.",
            {"aiExposure": exposure, "replacementRisk": replacement},
            {"low": GATES["extremeLow"], "high": GATES["extremeHigh"]}))

    if confidence >= GATES["minimumConfidence"] and coverage < GATES["minimumWeightedCoverage"] - 10:
        findings.append(_finding(
            "confidence_coverage_inconsistency",
            "Confidence is high while weighted coverage is well below the launch minimum.",
            {"confidence": confidence, "weightedTaskCoverage": coverage},
            {"note": "confidence should track coverage"}))

    missing_policy = (row.get("structuralProxyInputs") or {}).get("missingDataPolicy")
    if isinstance(missing_policy, dict) and missing_policy.get("missingFamilies"):
        findings.append(_finding(
            "structural_proxy_missing_data",
            "A structural proxy family fell back because source evidence was missing.",
            missing_policy, {"missingFamilies": []}))

    return findings


def soc_family_discontinuities(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Flag candidates whose SOC family spreads further than Phase 5 expects.

    Corpus-level, so it cannot live in `triage_occupation`. Keyed by candidate id.
    """
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        code = str(row.get("occupationCode") or "")
        if len(code) >= 7:
            families[code[:7]].append(row)

    flagged: dict[int, dict[str, Any]] = {}
    for family, members in families.items():
        if len(members) < 2:
            continue
        exposures = [float(item["aiExposure"]) for item in members if item.get("aiExposure") is not None]
        replacements = [float(item["replacementRisk"]) for item in members if item.get("replacementRisk") is not None]
        if not exposures or not replacements:
            continue
        exposure_range = max(exposures) - min(exposures)
        replacement_range = max(replacements) - min(replacements)
        if max(exposure_range, replacement_range) <= GATES["relatedSocDiscontinuity"]:
            continue
        for member in members:
            flagged[member["candidateOccupationId"]] = _finding(
                "related_soc_score_discontinuity",
                f"SOC family {family} spreads further than expected.",
                {"socFamily": family, "members": len(members),
                 "aiExposureRange": round(exposure_range, 4),
                 "replacementRiskRange": round(replacement_range, 4)},
                {"maximumRange": GATES["relatedSocDiscontinuity"]})
    return flagged


def triage_corpus(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Full triage. Returns per-occupation results and the cohort that falls out of them."""
    discontinuities = soc_family_discontinuities(rows)

    results: list[dict[str, Any]] = []
    for row in rows:
        findings = triage_occupation(row)
        discontinuity = discontinuities.get(row["candidateOccupationId"])
        if discontinuity:
            findings.append(discontinuity)
        severities = Counter(item["severity"] for item in findings)
        blocking = [item for item in findings if item["severity"] in BLOCKING_SEVERITIES]
        results.append({
            "candidateOccupationId": row["candidateOccupationId"],
            "occupationCode": row.get("occupationCode"),
            "title": row.get("title"),
            "aiExposure": row.get("aiExposure"),
            "replacementRisk": row.get("replacementRisk"),
            "confidence": row.get("confidence"),
            "weightedTaskCoverage": row.get("weightedTaskCoverage"),
            "launchEligible": not blocking,
            "blockingCodes": sorted({item["code"] for item in blocking}),
            "highestSeverity": (
                "critical" if severities["critical"] else
                "high" if severities["high"] else
                "medium" if severities["medium"] else
                "low" if severities["low"] else None),
            "severityCounts": {key: severities[key] for key in ("critical", "high", "medium", "low")},
            "findings": findings,
        })

    eligible = [item for item in results if item["launchEligible"]]
    excluded = [item for item in results if not item["launchEligible"]]

    exclusion_reasons = Counter()
    for item in excluded:
        for code in item["blockingCodes"]:
            exclusion_reasons[code] += 1

    severity_totals = Counter()
    finding_totals = Counter()
    for item in results:
        for finding in item["findings"]:
            severity_totals[finding["severity"]] += 1
            finding_totals[finding["code"]] += 1

    return {
        "policyVersion": TRIAGE_POLICY_VERSION,
        "gates": GATES,
        "candidatesAssessed": len(results),
        "launchCohortSize": len(eligible),
        "excludedCount": len(excluded),
        # Deliberately absent: any target cohort size. The cohort is whatever passes.
        "cohortSelection": "all candidates with no critical and no high findings",
        "severityTotals": {key: severity_totals[key] for key in ("critical", "high", "medium", "low")},
        "findingTotals": dict(finding_totals),
        "exclusionReasons": dict(exclusion_reasons),
        "occupationsWithMediumFindings": sum(
            1 for item in eligible if item["severityCounts"]["medium"] > 0),
        "results": results,
    }
