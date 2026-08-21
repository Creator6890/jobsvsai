"""Deterministic, direct-source Phase 4D structural proxy formulas."""

from __future__ import annotations

import math
import re
from typing import Any

try:
    from .pilot import rounded
except ImportError:
    from pilot import rounded


MODEL_VERSION = "phase4d-direct-structural-proxy-v2"
FAMILY_VERSIONS = {
    "physical-presence": "phase4d-physical-presence-v2",
    "environment-variability": "phase4d-environment-variability-v2",
    "accountability": "phase4d-duty-accountability-v2",
    "consequence-severity": "phase4d-clinical-consequence-severity-v2",
}


def element(
    element_type: str, element_id: str, scale_id: str, label: str, weight: float,
    transform: str = "linear",
) -> dict[str, Any]:
    return {"kind": "element", "elementType": element_type, "elementId": element_id,
            "scaleId": scale_id, "label": label, "weight": weight, "transform": transform}


def task_signal(signal: str, label: str, weight: float, multiplier: float) -> dict[str, Any]:
    return {"kind": "task_signal", "signal": signal, "label": label, "weight": weight,
            "transform": "weighted_matching_task_share", "multiplier": multiplier}


PHYSICAL_COMPONENTS = [
    element("work_activity", "4.A.3.a.1", "IM", "Performing General Physical Activities", .18),
    element("work_activity", "4.A.3.a.2", "IM", "Handling and Moving Objects", .14),
    element("work_activity", "4.A.3.a.4", "IM", "Operating Vehicles or Equipment", .13),
    element("work_context", "4.C.2.d.1.b", "CX", "Spend Time Standing", .10),
    element("work_context", "4.C.2.d.1.d", "CX", "Spend Time Walking or Running", .08),
    element("work_context", "4.C.2.d.1.g", "CX", "Hands on Objects, Tools, or Controls", .08),
    element("work_context", "4.C.2.a.1.c", "CX", "Outdoors in All Weather", .06),
    element("work_context", "4.C.2.a.1.d", "CX", "Outdoors Under Cover", .03),
    element("work_context", "4.C.2.a.1.e", "CX", "Open Vehicle or Equipment", .05),
    element("work_context", "4.C.2.a.1.f", "CX", "Enclosed Vehicle or Equipment", .04),
    element("work_context", "4.C.2.c.1.d", "CX", "Hazardous Conditions", .03),
    element("work_context", "4.C.2.c.1.e", "CX", "Hazardous Equipment", .03),
    element("work_context", "4.C.2.a.3", "CX", "Physical Proximity", .015),
    task_signal("physical", "Source Tasks Requiring Physical Presence", .035, 2.5),
]

ENVIRONMENT_COMPONENTS = [
    element("work_context", "4.C.2.a.1.c", "CX", "Outdoors in All Weather", .12),
    element("work_context", "4.C.2.a.1.d", "CX", "Outdoors Under Cover", .04),
    element("work_context", "4.C.2.a.1.b", "CX", "Indoors, Not Environmentally Controlled", .09),
    element("work_context", "4.C.2.a.1.e", "CX", "Open Vehicle or Equipment", .07),
    element("work_context", "4.C.2.a.1.f", "CX", "Enclosed Vehicle or Equipment", .04),
    element("work_context", "4.C.2.b.1.a", "CX", "Distracting Noise", .05),
    element("work_context", "4.C.2.b.1.b", "CX", "Very Hot or Cold Temperatures", .06),
    element("work_context", "4.C.2.b.1.d", "CX", "Contaminants", .04),
    element("work_context", "4.C.2.b.1.e", "CX", "Cramped or Awkward Positions", .035),
    element("work_context", "4.C.2.b.1.f", "CX", "Whole Body Vibration", .035),
    element("work_context", "4.C.2.c.1.a", "CX", "Radiation", .015),
    element("work_context", "4.C.2.c.1.b", "CX", "Disease or Infection", .025),
    element("work_context", "4.C.2.c.1.c", "CX", "High Places", .025),
    element("work_context", "4.C.2.c.1.d", "CX", "Hazardous Conditions", .065),
    element("work_context", "4.C.2.c.1.e", "CX", "Hazardous Equipment", .065),
    element("work_context", "4.C.2.e.1.d", "CX", "Common Protective Equipment", .03),
    element("work_context", "4.C.2.e.1.e", "CX", "Specialized Protective Equipment", .02),
    element("work_context", "4.C.3.d.3", "CX", "Equipment-paced Work", .04),
    element("work_activity", "4.A.3.a.4", "IM", "Operating Vehicles or Equipment", .05),
    element("work_context", "4.C.3.b.7", "CX", "Inverse Repeating Same Tasks", .025, "inverse"),
    task_signal("variable_environment", "Source Tasks in Variable Locations or Settings", .06, 3.0),
]

ACCOUNTABILITY_COMPONENTS = [
    element("work_context", "4.C.3.a.1", "CX", "Consequence of Error", .18),
    element("work_context", "4.C.3.a.2.a", "CX", "Impact of Decisions", .17),
    element("work_context", "4.C.3.a.2.b", "CX", "Frequency of Decision Making", .10),
    element("work_context", "4.C.3.a.4", "CX", "Freedom to Make Decisions", .06),
    element("work_context", "4.C.1.c.1", "CX", "Responsibility for Others' Health and Safety", .15),
    element("work_context", "4.C.1.c.2", "CX", "Responsibility for Others' Work Outcomes", .08),
    element("work_activity", "4.A.2.b.1", "IM", "Making Decisions and Solving Problems", .10),
    element("work_activity", "4.A.2.a.3", "IM", "Evaluating Compliance with Standards", .05),
    element("work_activity", "4.A.4.b.1", "IM", "Coordinating the Work of Others", .04),
    element("work_activity", "4.A.4.a.5", "IM", "Assisting and Caring for Others", .03),
    task_signal("duty", "Source Tasks with Explicit Duty or Outcome Responsibility", .04, 2.5),
]

CONSEQUENCE_BASE_COMPONENTS = [
    element("work_context", "4.C.3.a.1", "CX", "Consequence of Error", .36),
    element("work_context", "4.C.3.a.2.a", "CX", "Impact of Decisions", .22),
    element("work_context", "4.C.1.c.1", "CX", "Responsibility for Others' Health and Safety", .18),
    element("work_context", "4.C.2.c.1.d", "CX", "Hazardous Conditions", .12),
    element("work_context", "4.C.2.c.1.e", "CX", "Hazardous Equipment", .12),
]

CLINICAL_COMPONENTS = [
    element("work_activity", "4.A.4.a.5", "IM", "Assisting and Caring for Others", .28),
    element("work_context", "4.C.2.c.1.b", "CX", "Exposure to Disease or Infection", .14),
    task_signal("clinical_treatment", "Treatment and Clinical Care Tasks", .34, 4.0),
    task_signal("clinical_diagnostic", "Diagnostic and Patient Assessment Tasks", .24, 4.0),
]

FORMULA_PARAMETERS = {
    "physical-presence": {"version": FAMILY_VERSIONS["physical-presence"],
                           "aggregation": "0.60 weighted RMS + 0.20 weighted mean + 0.20 mean of top three independent signals",
                           "components": PHYSICAL_COMPONENTS},
    "environment-variability": {"version": FAMILY_VERSIONS["environment-variability"],
                                "aggregation": "0.35 weighted RMS + 0.15 weighted mean + 0.50 mean of top three independent signals",
                                "components": ENVIRONMENT_COMPONENTS},
    "accountability": {"version": FAMILY_VERSIONS["accountability"],
                       "aggregation": "0.70 weighted RMS + 0.30 weighted mean",
                       "components": ACCOUNTABILITY_COMPONENTS},
    "consequence-severity": {
        "version": FAMILY_VERSIONS["consequence-severity"],
        "baseAggregation": "0.65 weighted RMS + 0.35 weighted mean",
        "clinicalAggregation": "weighted RMS",
        "clinicalGate": {
            "minimumClinicalTaskSignal": 15,
            "minimumCareActivityOrDiseaseExposure": 20,
            "minimumConsequenceOrSafetySignal": 35,
            "required": "all three conditions; title and SOC are prohibited",
        },
        "clinicalEnhancer": "base + 0.50 * clinicalStrength * (100-base) / 100",
        "baseComponents": CONSEQUENCE_BASE_COMPONENTS,
        "clinicalComponents": CLINICAL_COMPONENTS,
    },
    "confidence": {"base": 88, "missingWeightPenaltyMaximum": 38,
                   "suppressedWeightPenaltyMaximum": 22,
                   "taskRatingCoveragePenaltyMaximum": 12,
                   "clinicalIndirectEvidenceCeiling": 82},
}

TASK_PATTERNS = {
    "physical": re.compile(
        r"\b(lift|carry|load|unload|install|repair|operate|drive|walk|stand|climb|assemble|"
        r"clean|cook|cut|style|move|handle|position|transport|patrol|restrain|photograph)\w*\b", re.I
    ),
    "variable_environment": re.compile(
        r"\b(site|field|scene|route|road|outdoor|premises|location|travel|emergenc|patrol|"
        r"inspect|respond|weather|traffic|construction)\w*\b", re.I
    ),
    "duty": re.compile(
        r"\b(safety|responsib|supervis|monitor|protect|approve|compliance|care|teach|train|"
        r"assess|evaluate|decide|authorize|ensure|advise|direct)\w*\b", re.I
    ),
    "clinical_treatment": re.compile(
        r"\b(patient|clinical|vital signs|nursing|medical procedure|care plan|wound care|"
        r"prescrib\w* medication|surgery|healthcare)\b", re.I
    ),
    "clinical_diagnostic": re.compile(
        r"(?=.*\b(patient|medical|clinical|disease|symptom|specimen|health condition)\w*\b)"
        r"(?=.*\b(diagnos|assess|examin|test result|vital signs|finding)\w*\b)", re.I
    ),
}


def transformed(value: float, transform: str) -> float:
    if transform == "linear":
        return rounded(value)
    if transform == "inverse":
        return rounded(100.0 - value)
    raise ValueError(f"Unsupported source transformation {transform}")


def task_evidence(tasks: list[dict[str, Any]], signal: str, multiplier: float) -> dict[str, Any]:
    pattern = TASK_PATTERNS[signal]
    eligible = [task for task in tasks if task.get("sourceWeight") is not None]
    total_weight = sum(float(task["sourceWeight"]) for task in eligible)
    matched = [task for task in eligible if pattern.search(task["statement"])]
    matched_weight = sum(float(task["sourceWeight"]) for task in matched)
    share = matched_weight / total_weight if total_weight > 0 else None
    value = rounded(100.0 * share * multiplier) if share is not None else None
    return {
        "value": value,
        "eligibleTaskCount": len(eligible),
        "sourceTaskCount": len(tasks),
        "eligibleWeight": round(total_weight, 8),
        "matchedWeight": round(matched_weight, 8),
        "weightedMatchShare": round(share, 8) if share is not None else None,
        "multiplier": multiplier,
        "matchingTasks": [
            {"taskId": task["taskId"], "statement": task["statement"],
             "sourceWeight": task["sourceWeight"], "rowHash": task["rowHash"],
             "sourceVersion": task["sourceVersion"]}
            for task in matched
        ],
    }


def resolve_components(
    specifications: list[dict[str, Any]],
    ratings: dict[tuple[str, str, str], dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], float, float, float]:
    entries: list[dict[str, Any]] = []
    available_weight = 0.0
    missing_weight = 0.0
    suppressed_weight = 0.0
    for specification in specifications:
        weight = float(specification["weight"])
        if specification["kind"] == "task_signal":
            evidence = task_evidence(tasks, specification["signal"], specification["multiplier"])
            value = evidence["value"]
            status = "used" if value is not None else "missing"
            entry = {**specification, "status": status, "rawNormalizedValue":
                     round(100 * evidence["weightedMatchShare"], 4)
                     if evidence["weightedMatchShare"] is not None else None,
                     "transformedValue": value, "evidence": evidence}
        else:
            key = (specification["elementType"], specification["elementId"], specification["scaleId"])
            rating = ratings.get(key)
            if rating is None:
                status = "missing"
                value = None
            elif rating.get("recommendSuppress") or rating.get("notRelevant"):
                status = "suppressed"
                value = None
            else:
                status = "used"
                value = transformed(float(rating["normalizedValue"]), specification["transform"])
            entry = {
                **specification, "status": status,
                "rawNormalizedValue": float(rating["normalizedValue"]) if rating else None,
                "transformedValue": value,
                "evidence": {
                    "sourceRecordId": rating.get("sourceRecordId") if rating else None,
                    "rowHash": rating.get("rowHash") if rating else None,
                    "sourceVersion": rating.get("sourceVersion") if rating else None,
                    "elementName": rating.get("elementName") if rating else specification["label"],
                    "sampleSize": rating.get("sampleSize") if rating else None,
                    "standardError": rating.get("standardError") if rating else None,
                    "recommendSuppress": rating.get("recommendSuppress") if rating else None,
                    "notRelevant": rating.get("notRelevant") if rating else None,
                },
            }
        if entry["status"] == "used":
            available_weight += weight
        elif entry["status"] == "suppressed":
            suppressed_weight += weight
        else:
            missing_weight += weight
        entries.append(entry)
    if available_weight <= 0:
        raise ValueError("Direct proxy formula has no usable source evidence")
    for entry in entries:
        normalized_weight = float(entry["weight"]) / available_weight if entry["status"] == "used" else 0.0
        entry["normalizedUsedWeight"] = round(normalized_weight, 8)
        value = float(entry["transformedValue"] or 0.0)
        entry["meanContribution"] = rounded(normalized_weight * value)
        entry["squaredContribution"] = round(normalized_weight * value * value, 8)
    return entries, available_weight, missing_weight, suppressed_weight


def confidence(
    entries: list[dict[str, Any]], missing_weight: float, suppressed_weight: float,
    confidence_parameters: dict[str, Any], ceiling: float | None = None,
) -> float:
    total_weight = sum(float(entry["weight"]) for entry in entries)
    value = float(confidence_parameters["base"])
    value -= missing_weight / total_weight * float(confidence_parameters["missingWeightPenaltyMaximum"])
    value -= suppressed_weight / total_weight * float(confidence_parameters["suppressedWeightPenaltyMaximum"])
    task_entries = [entry for entry in entries if entry["kind"] == "task_signal" and entry["status"] == "used"]
    if task_entries:
        minimum_coverage = min(
            entry["evidence"]["eligibleTaskCount"] / max(1, entry["evidence"]["sourceTaskCount"])
            for entry in task_entries
        )
        value -= (1 - minimum_coverage) * float(
            confidence_parameters["taskRatingCoveragePenaltyMaximum"]
        )
    if ceiling is not None:
        value = min(value, ceiling)
    return rounded(value)


def aggregate(
    family: str, specifications: list[dict[str, Any]], ratings: dict[tuple[str, str, str], dict[str, Any]],
    tasks: list[dict[str, Any]], rms_weight: float, mean_weight: float | None = None,
    top_signal_weight: float = 0.0,
) -> dict[str, Any]:
    entries, available, missing, suppressed = resolve_components(specifications, ratings, tasks)
    mean = sum(float(entry["meanContribution"]) for entry in entries)
    rms = math.sqrt(sum(float(entry["squaredContribution"]) for entry in entries))
    if mean_weight is None:
        mean_weight = 1 - rms_weight - top_signal_weight
    if abs(rms_weight + mean_weight + top_signal_weight - 1.0) > .000001:
        raise ValueError("Phase 4D aggregation weights must sum to 1")
    used_values = sorted(
        (float(entry["transformedValue"]) for entry in entries if entry["status"] == "used"),
        reverse=True,
    )
    top_three_mean = sum(used_values[:3]) / min(3, len(used_values))
    result = rounded(rms_weight * rms + mean_weight * mean + top_signal_weight * top_three_mean)
    result_confidence = confidence(entries, missing, suppressed, FORMULA_PARAMETERS["confidence"])
    reconciliation = {
        "configuredWeightTotal": round(sum(float(item["weight"]) for item in specifications), 8),
        "availableConfiguredWeight": round(available, 8),
        "missingConfiguredWeight": round(missing, 8),
        "suppressedConfiguredWeight": round(suppressed, 8),
        "normalizedUsedWeightTotal": round(sum(float(entry["normalizedUsedWeight"]) for entry in entries), 8),
        "weightedMean": rounded(mean), "weightedRms": rounded(rms),
        "topThreeSignalMean": rounded(top_three_mean),
        "aggregationWeights": {"weightedRms": rms_weight, "weightedMean": mean_weight,
                               "topThreeSignalMean": top_signal_weight},
        "recomputedResult": result,
        "passed": abs(result - rounded(
            rms_weight * rms + mean_weight * mean + top_signal_weight * top_three_mean
        )) <= .001,
    }
    return {"family": family, "formulaVersion": FAMILY_VERSIONS[family], "value": result,
            "confidence": result_confidence, "components": entries,
            "missingDataPolicy": "exclude missing/suppressed signals and renormalize used weights; never impute",
            "reconciliation": reconciliation}


def consequence_severity(
    ratings: dict[tuple[str, str, str], dict[str, Any]], tasks: list[dict[str, Any]]
) -> dict[str, Any]:
    base = aggregate("consequence-severity", CONSEQUENCE_BASE_COMPONENTS, ratings, tasks, .65)
    clinical_entries, clinical_available, clinical_missing, clinical_suppressed = resolve_components(
        CLINICAL_COMPONENTS, ratings, tasks
    )
    clinical_strength = rounded(math.sqrt(sum(float(entry["squaredContribution"]) for entry in clinical_entries)))
    values = {
        entry.get("signal") or entry.get("elementId"): float(entry["transformedValue"] or 0)
        for entry in clinical_entries
    }
    base_values = {
        entry.get("elementId"): float(entry["transformedValue"] or 0)
        for entry in base["components"]
    }
    clinical_task_signal = max(values.get("clinical_treatment", 0), values.get("clinical_diagnostic", 0))
    care_or_disease = max(values.get("4.A.4.a.5", 0), values.get("4.C.2.c.1.b", 0))
    consequence_or_safety = max(base_values.get("4.C.3.a.1", 0), base_values.get("4.C.1.c.1", 0))
    gate_checks = {
        "clinicalTaskSignal": {"value": rounded(clinical_task_signal), "minimum": 15,
                               "passed": clinical_task_signal >= 15},
        "careActivityOrDiseaseExposure": {"value": rounded(care_or_disease), "minimum": 20,
                                           "passed": care_or_disease >= 20},
        "consequenceOrSafety": {"value": rounded(consequence_or_safety), "minimum": 35,
                                "passed": consequence_or_safety >= 35},
        "titleOrSocUsed": False,
    }
    gate_passed = all(check["passed"] for check in gate_checks.values() if isinstance(check, dict))
    enhancer = .50 * clinical_strength * (100 - float(base["value"])) / 100 if gate_passed else 0.0
    result = rounded(float(base["value"]) + enhancer)
    clinical_confidence = confidence(
        clinical_entries, clinical_missing, clinical_suppressed, FORMULA_PARAMETERS["confidence"],
        float(FORMULA_PARAMETERS["confidence"]["clinicalIndirectEvidenceCeiling"]),
    )
    result_confidence = rounded(min(float(base["confidence"]), clinical_confidence) if gate_passed
                                else float(base["confidence"]))
    reconciliation = {
        "base": base["reconciliation"], "clinicalConfiguredWeightTotal": 1.0,
        "clinicalAvailableWeight": round(clinical_available, 8),
        "clinicalMissingWeight": round(clinical_missing, 8),
        "clinicalSuppressedWeight": round(clinical_suppressed, 8),
        "clinicalStrength": clinical_strength, "clinicalGatePassed": gate_passed,
        "clinicalEnhancer": rounded(enhancer), "recomputedResult": result,
        "passed": base["reconciliation"]["passed"]
        and abs(result - rounded(float(base["value"]) + enhancer)) <= .001,
    }
    return {
        "family": "consequence-severity", "formulaVersion": FAMILY_VERSIONS["consequence-severity"],
        "value": result, "confidence": result_confidence,
        "components": base["components"], "clinicalComponents": clinical_entries,
        "clinicalGate": gate_checks, "clinicalGatePassed": gate_passed,
        "baseValue": base["value"], "clinicalStrength": clinical_strength,
        "clinicalEnhancer": rounded(enhancer),
        "missingDataPolicy": "exclude and renormalize; clinical enhancer is zero unless all source gates pass",
        "reconciliation": reconciliation,
    }


def direct_structural_proxies(
    ratings: dict[tuple[str, str, str], dict[str, Any]], tasks: list[dict[str, Any]]
) -> dict[str, Any]:
    families = {
        "physical-presence": aggregate(
            "physical-presence", PHYSICAL_COMPONENTS, ratings, tasks, .60, .20, .20
        ),
        "environment-variability": aggregate(
            "environment-variability", ENVIRONMENT_COMPONENTS, ratings, tasks, .35, .15, .50
        ),
        "accountability": aggregate("accountability", ACCOUNTABILITY_COMPONENTS, ratings, tasks, .70),
        "consequence-severity": consequence_severity(ratings, tasks),
    }
    return {
        "families": families,
        "confidence": rounded(min(float(item["confidence"]) for item in families.values())),
        "warnings": [
            {"code": "phase4d_direct_structural_proxy_pilot", "production": False},
            {"code": "clinical_task_language_is_deterministic_source_evidence_not_medical_validation"},
        ],
        "reconciliation": {
            "familiesPassed": {key: item["reconciliation"]["passed"] for key, item in families.items()},
            "passed": all(item["reconciliation"]["passed"] for item in families.values()),
        },
    }
