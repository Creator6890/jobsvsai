"""Pure deterministic Phase 4B calibration formulas and proxy transforms."""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

try:
    from .pilot import rounded
except ImportError:  # Direct script execution from /app/scoring.
    from pilot import rounded


def _component_value(
    component: dict[str, Any], ratings: dict[tuple[str, str, str], dict[str, Any]], domains: dict[str, Any]
) -> tuple[float | None, dict[str, Any]]:
    if "derivedDomain" in component:
        domain = domains.get(component["derivedDomain"])
        if domain is None:
            return None, {"status": "missing", "reason": "derived_domain_missing"}
        return float(domain["value"]), {
            "status": "used",
            "source": "derived_domain",
            "derivedDomain": component["derivedDomain"],
            "sourceConfidence": domain["confidence"],
        }
    key = (component["elementType"], component["elementId"], component["scaleId"])
    rating = ratings.get(key)
    if rating is None:
        return None, {"status": "missing", "reason": "source_rating_missing", "sourceKey": key}
    if rating.get("recommendSuppress") or rating.get("notRelevant"):
        return None, {
            "status": "suppressed",
            "reason": "source_suppression_or_not_relevant",
            "sourceKey": key,
            "rating": rating,
        }
    value = float(rating["normalizedValue"])
    if component.get("transform") == "inverse":
        value = 100.0 - value
    return value, {"status": "used", "source": "onet_element_rating", "sourceKey": key, "rating": rating}


def weighted_components(
    name: str,
    components: list[dict[str, Any]],
    ratings: dict[tuple[str, str, str], dict[str, Any]],
    domains: dict[str, Any],
    parameters: dict[str, Any],
    confidence_ceiling: float | None = None,
) -> dict[str, Any]:
    entries = []
    available_weight = 0.0
    missing_weight = 0.0
    suppressed_weight = 0.0
    no_sample_weight = 0.0
    small_sample_weight = 0.0
    for component in components:
        configured_weight = float(component["weight"])
        value, source = _component_value(component, ratings, domains)
        if source["status"] == "used":
            available_weight += configured_weight
            rating = source.get("rating")
            if rating:
                sample_size = rating.get("sampleSize")
                if sample_size is None:
                    no_sample_weight += configured_weight
                elif int(sample_size) < int(parameters["smallSampleThreshold"]):
                    small_sample_weight += configured_weight
        elif source["status"] == "suppressed":
            suppressed_weight += configured_weight
        else:
            missing_weight += configured_weight
        entries.append(
            {
                "label": component["label"],
                "configuredWeight": configured_weight,
                "rawValue": rounded(value) if value is not None else None,
                **source,
            }
        )
    if available_weight <= 0:
        raise ValueError(f"No usable source components for proxy {name}")
    value = 0.0
    for entry in entries:
        if entry["status"] != "used":
            entry["normalizedWeight"] = 0.0
            entry["weightedContribution"] = 0.0
            continue
        normalized_weight = float(entry["configuredWeight"]) / available_weight
        contribution = normalized_weight * float(entry["rawValue"])
        entry["normalizedWeight"] = round(normalized_weight, 8)
        entry["weightedContribution"] = rounded(contribution)
        value += contribution
    total_weight = sum(float(item["configuredWeight"]) for item in entries)
    missing_ratio = missing_weight / total_weight
    suppressed_ratio = suppressed_weight / total_weight
    no_sample_ratio = no_sample_weight / total_weight
    small_sample_ratio = small_sample_weight / total_weight
    confidence = float(parameters["baseConfidence"])
    confidence -= missing_ratio * float(parameters["missingComponentPenaltyMaximum"])
    confidence -= suppressed_ratio * float(parameters["suppressedComponentPenalty"])
    confidence -= no_sample_ratio * float(parameters["missingSampleSizePenalty"])
    confidence -= small_sample_ratio * float(parameters["smallSamplePenalty"])
    if confidence_ceiling is not None:
        confidence = min(confidence, confidence_ceiling)
    return {
        "name": name,
        "value": rounded(value),
        "confidence": rounded(confidence),
        "components": entries,
        "reconciliation": {
            "configuredWeightTotal": round(total_weight, 8),
            "availableConfiguredWeight": round(available_weight, 8),
            "normalizedUsedWeightTotal": round(
                sum(float(item["normalizedWeight"]) for item in entries), 8
            ),
            "weightedContributionTotal": rounded(
                sum(float(item["weightedContribution"]) for item in entries)
            ),
            "missingWeight": round(missing_weight, 8),
            "suppressedWeight": round(suppressed_weight, 8),
            "passed": abs(rounded(value) - rounded(sum(float(item["weightedContribution"]) for item in entries)))
            <= 0.001,
        },
    }


def occupation_proxies(
    ratings: dict[tuple[str, str, str], dict[str, Any]], parameters: dict[str, Any]
) -> dict[str, Any]:
    domains: dict[str, Any] = {}
    for name, components in parameters["domains"].items():
        domains[name] = weighted_components(name, components, ratings, domains, parameters)
    adoption_config = parameters["adoptionPressure"]
    adoption = weighted_components(
        "adoption-pressure",
        adoption_config["components"],
        ratings,
        domains,
        parameters,
        float(adoption_config["confidenceCeiling"]),
    )
    resilience_config = parameters["labourMarketResilience"]
    resilience = weighted_components(
        "labour-market-resilience",
        resilience_config["components"],
        ratings,
        domains,
        parameters,
        float(resilience_config["confidenceCeiling"]),
    )
    overall_confidence = min(
        mean([float(item["confidence"]) for item in domains.values()]),
        float(adoption["confidence"]),
        float(resilience["confidence"]),
    )
    return {
        "domains": domains,
        "adoptionPressure": adoption,
        "labourMarketResilience": resilience,
        "confidence": rounded(overall_confidence),
        "warnings": [
            {
                "code": "provisional_structural_adoption_proxy",
                "detail": adoption_config["interpretation"],
            },
            {
                "code": "provisional_structural_labour_resilience_proxy",
                "detail": resilience_config["interpretation"],
            },
        ],
        "reconciliation": {
            "domainsPassed": all(item["reconciliation"]["passed"] for item in domains.values()),
            "adoptionPassed": adoption["reconciliation"]["passed"],
            "resiliencePassed": resilience["reconciliation"]["passed"],
            "passed": all(item["reconciliation"]["passed"] for item in domains.values())
            and adoption["reconciliation"]["passed"]
            and resilience["reconciliation"]["passed"],
        },
    }


def capability_fit_v2(
    requirements: list[dict[str, Any]], frontier: dict[str, dict[str, Any]], parameters: dict[str, Any]
) -> dict[str, Any]:
    weight_total = sum(float(item["weight"]) for item in requirements)
    if not requirements or abs(weight_total - 1.0) > 0.0001:
        raise ValueError(f"Capability weights must reconcile to 1.0, got {weight_total}")
    slope = float(parameters["logisticSlope"])
    floor = float(parameters["geometricFloor"])
    contributions = []
    log_total = 0.0
    critical_caps = []
    for item in requirements:
        current = frontier[item["slug"]]
        margin = float(current["score"]) - float(item["requiredLevel"])
        match = 100.0 / (1.0 + math.exp(-margin / slope))
        weight = float(item["weight"])
        weighted_log = weight * math.log(max(floor, match))
        log_total += weighted_log
        critical = weight >= float(parameters["criticalWeightThreshold"]) or (
            weight >= float(parameters["criticalSecondaryWeightThreshold"])
            and float(item["requiredLevel"]) >= float(parameters["criticalRequiredLevelThreshold"])
        )
        cap = None
        if critical and match < float(parameters["bottleneckMatchThreshold"]):
            cap = min(100.0, match + float(parameters["bottleneckHeadroom"]))
            critical_caps.append(cap)
        contributions.append(
            {
                **item,
                "currentCommercialAI": rounded(float(current["score"])),
                "frontierEntryId": current["entryId"],
                "frontierConfidence": rounded(float(current["confidence"])),
                "frontierEvidenceIds": current["evidenceIds"],
                "capabilityMargin": rounded(margin),
                "capabilityMatch": rounded(match),
                "criticalCapability": critical,
                "bottleneckCap": rounded(cap) if cap is not None else None,
                "weightedLogContribution": round(weighted_log, 8),
            }
        )
    geometric = math.exp(log_total / weight_total)
    score = min([geometric, *critical_caps]) if critical_caps else geometric
    return {
        "score": rounded(score),
        "geometricMean": rounded(geometric),
        "criticalBottleneckCap": rounded(min(critical_caps)) if critical_caps else None,
        "contributions": contributions,
        "reconciliation": {
            "normalizedWeightTotal": round(weight_total, 8),
            "weightedLogTotal": round(log_total, 8),
            "recomputedScore": rounded(score),
            "passed": True,
        },
    }


def consolidated_constraints(
    task_constraints: list[dict[str, Any]], proxy: dict[str, Any], parameters: dict[str, Any]
) -> list[dict[str, Any]]:
    direct = {item["slug"]: item for item in task_constraints}
    result = []
    for domain, fixed_weight in parameters["domainWeights"].items():
        direct_slug = parameters["directConstraintMap"].get(domain)
        direct_item = direct.get(direct_slug) if direct_slug else None
        if direct_item:
            result.append(
                {
                    "slug": domain,
                    "level": float(direct_item["level"]),
                    "confidence": float(direct_item["confidence"]),
                    "source": "direct_task_mapping",
                    "directConstraintSlug": direct_slug,
                    "evidence": direct_item["evidence"],
                    "fixedWeight": float(fixed_weight),
                }
            )
        elif domain in parameters["proxyDomains"]:
            proxy_domain = proxy["domains"][domain]
            result.append(
                {
                    "slug": domain,
                    "level": float(proxy_domain["value"]),
                    "confidence": float(proxy_domain["confidence"]),
                    "source": "occupation_metadata_proxy",
                    "proxyDomain": domain,
                    "evidence": proxy_domain["components"],
                    "fixedWeight": float(fixed_weight),
                }
            )
        else:
            result.append(
                {
                    "slug": domain,
                    "level": 0.0,
                    "confidence": None,
                    "source": "no_explicit_constraint_or_approved_proxy",
                    "evidence": [],
                    "fixedWeight": float(fixed_weight),
                }
            )
    return result


def automation_feasibility_v2(
    fit: float, constraints: list[dict[str, Any]], parameters: dict[str, Any]
) -> dict[str, Any]:
    exponent = float(parameters["constraintExponent"])
    burden = 0.0
    critical_caps = []
    contributions = []
    proxy_count = 0
    proxy_confidences = []
    for item in constraints:
        level = float(item["level"])
        transformed = 100.0 * (level / 100.0) ** exponent if level > 0 else 0.0
        contribution = transformed * float(item["fixedWeight"])
        burden += contribution
        cap = None
        if (
            level >= float(parameters["criticalConstraintThreshold"])
            and item["slug"] in parameters["bottleneckCapStrength"]
        ):
            cap = max(0.0, 100.0 - level * float(parameters["bottleneckCapStrength"][item["slug"]]))
            critical_caps.append(cap)
        if item["source"] == "occupation_metadata_proxy":
            proxy_count += 1
            proxy_confidences.append(float(item["confidence"]))
        contributions.append(
            {
                **item,
                "transformedLevel": rounded(transformed),
                "burdenContribution": rounded(contribution),
                "explicitlyMapped": item["source"] == "direct_task_mapping",
                "mappingConfidence": rounded(float(item["confidence"])) if item["confidence"] is not None else None,
                "mappingEvidence": item["evidence"],
                "criticalConstraint": cap is not None,
                "bottleneckCap": rounded(cap) if cap is not None else None,
            }
        )
    resistance = 100.0 - burden
    blended = float(parameters["capabilityFitWeight"]) * fit + float(
        parameters["constraintResistanceWeight"]
    ) * resistance
    score = min([blended, *critical_caps]) if critical_caps else blended
    proxy_ratio = proxy_count / len(constraints)
    proxy_confidence = mean(proxy_confidences) if proxy_confidences else 100.0
    proxy_penalty = min(
        float(parameters["maximumProxyConfidencePenalty"]),
        proxy_ratio * float(parameters["proxyUsagePenaltyWeight"])
        + (100.0 - proxy_confidence) / 100.0 * float(parameters["proxyUncertaintyPenaltyWeight"]),
    )
    return {
        "score": rounded(score),
        "constraintBurden": rounded(burden),
        "constraintResistance": rounded(resistance),
        "preBottleneckScore": rounded(blended),
        "criticalBottleneckCap": rounded(min(critical_caps)) if critical_caps else None,
        "proxyConfidencePenalty": rounded(proxy_penalty),
        "proxyDomainCount": proxy_count,
        "contributions": contributions,
        "reconciliation": {
            "domainWeightTotal": round(sum(float(item["fixedWeight"]) for item in constraints), 8),
            "burdenContributionTotal": rounded(sum(float(item["burdenContribution"]) for item in contributions)),
            "recomputedScore": rounded(score),
            "passed": abs(rounded(burden) - rounded(sum(float(item["burdenContribution"]) for item in contributions)))
            <= 0.001,
        },
    }


def augmentation_potential_v2(fit: float, automation: float, parameters: dict[str, Any]) -> dict[str, Any]:
    complement = (max(0.0, 1.0 - automation / 100.0)) ** float(parameters["complementExponent"])
    multiplier = float(parameters["collaborationFloor"]) + float(
        parameters["constraintComplementWeight"]
    ) * complement
    score = fit * multiplier
    return {
        "score": rounded(score),
        "capabilityFit": rounded(fit),
        "automationComplement": rounded(complement * 100.0),
        "collaborationFloorContribution": rounded(fit * float(parameters["collaborationFloor"])),
        "constraintComplementContribution": rounded(
            fit * float(parameters["constraintComplementWeight"]) * complement
        ),
        "recomputedScore": rounded(score),
    }


def distribution_summary(values: list[float]) -> dict[str, Any]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Cannot summarize an empty distribution")

    def percentile(fraction: float) -> float:
        position = (len(ordered) - 1) * fraction
        lower = int(math.floor(position))
        upper = int(math.ceil(position))
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {
        "count": len(ordered),
        "minimum": rounded(ordered[0]),
        "p10": rounded(percentile(0.10)),
        "p25": rounded(percentile(0.25)),
        "median": rounded(percentile(0.50)),
        "p75": rounded(percentile(0.75)),
        "p90": rounded(percentile(0.90)),
        "maximum": rounded(ordered[-1]),
        "mean": rounded(mean(ordered)),
        "standardDeviation": rounded(pstdev(ordered)),
        "atOrAbove90": sum(value >= 90 for value in ordered),
        "atOrAbove95": sum(value >= 95 for value in ordered),
    }
