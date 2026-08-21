"""Pure, deterministic Phase 4A pilot scoring formulas."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def rounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 4)


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def capability_fit(
    requirements: list[dict[str, Any]], frontier: dict[str, dict[str, Any]], parameters: dict[str, Any]
) -> dict[str, Any]:
    exponent = float(parameters["shortfallExponent"])
    floor = float(parameters["geometricFloor"])
    contributions = []
    weighted_log_total = 0.0
    weight_total = sum(float(item["weight"]) for item in requirements)
    if not requirements or abs(weight_total - 1.0) > 0.0001:
        raise ValueError(f"Capability weights must reconcile to 1.0, got {weight_total}")

    critical_caps = []
    for item in requirements:
        slug = item["slug"]
        if slug not in frontier:
            raise ValueError(f"No commercially deployable Frontier value for {slug}")
        required = float(item["requiredLevel"])
        ai_value = float(frontier[slug]["score"])
        match = 100.0 if required <= 0 or ai_value >= required else 100.0 * (ai_value / required) ** exponent
        weight = float(item["weight"])
        weighted_log = weight * math.log(max(floor, match))
        weighted_log_total += weighted_log
        critical = weight >= float(parameters["criticalWeightThreshold"]) or (
            weight >= float(parameters["criticalSecondaryWeightThreshold"])
            and required >= float(parameters["criticalRequiredLevelThreshold"])
        )
        cap = None
        if critical and match < float(parameters["bottleneckMatchThreshold"]):
            cap = min(100.0, match + float(parameters["bottleneckHeadroom"]))
            critical_caps.append(cap)
        contributions.append(
            {
                **item,
                "currentCommercialAI": rounded(ai_value),
                "frontierEntryId": frontier[slug]["entryId"],
                "frontierConfidence": rounded(float(frontier[slug]["confidence"])),
                "frontierEvidenceIds": frontier[slug]["evidenceIds"],
                "capabilityMatch": rounded(match),
                "criticalCapability": critical,
                "bottleneckCap": rounded(cap) if cap is not None else None,
                "weightedLogContribution": round(weighted_log, 8),
            }
        )
    geometric = math.exp(weighted_log_total / weight_total)
    final = min([geometric, *critical_caps]) if critical_caps else geometric
    return {
        "score": rounded(final),
        "geometricMean": rounded(geometric),
        "criticalBottleneckCap": rounded(min(critical_caps)) if critical_caps else None,
        "contributions": contributions,
        "reconciliation": {
            "normalizedWeightTotal": round(weight_total, 7),
            "weightedLogTotal": round(weighted_log_total, 8),
            "recomputedScore": rounded(final),
            "passed": abs(rounded(final) - rounded(final)) < 0.0001,
        },
    }


def automation_feasibility(
    fit: float, constraints: list[dict[str, Any]], parameters: dict[str, Any]
) -> dict[str, Any]:
    mapped = {item["slug"]: item for item in constraints}
    fixed_weights = parameters["constraintWeights"]
    contributions = []
    burden = 0.0
    critical_caps = []
    for slug, weight_value in fixed_weights.items():
        item = mapped.get(slug)
        level = float(item["level"]) if item else 0.0
        weight = float(weight_value)
        contribution = level * weight
        burden += contribution
        cap = None
        if (
            item
            and level >= float(parameters["criticalConstraintThreshold"])
            and slug in parameters["bottleneckCapStrength"]
        ):
            cap = max(0.0, 100.0 - level * float(parameters["bottleneckCapStrength"][slug]))
            critical_caps.append(cap)
        contributions.append(
            {
                "slug": slug,
                "level": rounded(level),
                "fixedWeight": weight,
                "burdenContribution": rounded(contribution),
                "explicitlyMapped": item is not None,
                "mappingConfidence": rounded(float(item["confidence"])) if item else None,
                "mappingEvidence": item["evidence"] if item else [],
                "criticalConstraint": cap is not None,
                "bottleneckCap": rounded(cap) if cap is not None else None,
            }
        )
    resistance = 100.0 - burden
    blended = float(parameters["capabilityFitWeight"]) * fit + float(
        parameters["constraintResistanceWeight"]
    ) * resistance
    final = min([blended, *critical_caps]) if critical_caps else blended
    return {
        "score": rounded(final),
        "constraintBurden": rounded(burden),
        "constraintResistance": rounded(resistance),
        "preBottleneckScore": rounded(blended),
        "criticalBottleneckCap": rounded(min(critical_caps)) if critical_caps else None,
        "contributions": contributions,
        "reconciliation": {
            "fixedWeightTotal": round(sum(float(value) for value in fixed_weights.values()), 7),
            "burdenContributionTotal": rounded(sum(item["burdenContribution"] for item in contributions)),
            "recomputedScore": rounded(final),
            "passed": abs(rounded(burden) - rounded(sum(item["burdenContribution"] for item in contributions)))
            <= 0.001,
        },
    }


def augmentation_potential(fit: float, automation: float, parameters: dict[str, Any]) -> dict[str, Any]:
    fit_contribution = float(parameters["capabilityFitWeight"]) * fit
    complement_contribution = float(parameters["humanComplementWeight"]) * (100.0 - automation)
    score = fit_contribution + complement_contribution
    return {
        "score": rounded(score),
        "fitContribution": rounded(fit_contribution),
        "humanComplementContribution": rounded(complement_contribution),
        "recomputedScore": rounded(score),
    }


def weighted_average(items: list[dict[str, Any]], value_key: str, weight_key: str) -> float:
    denominator = sum(float(item[weight_key]) for item in items)
    if denominator <= 0:
        raise ValueError("A weighted average requires positive total weight")
    return sum(float(item[value_key]) * float(item[weight_key]) for item in items) / denominator
