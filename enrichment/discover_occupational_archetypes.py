"""Discover and persist the draft Occupational Archetype Layer v1.

The discovery is deliberately offline and deterministic.  It clusters current
O*NET occupations using normalized skill, ability, work-activity and
work-context ratings plus hashed task-language features.  SOC codes, titles and
industry labels are never features; titles are used only after discovery to
make candidate clusters inspectable.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import asyncpg

try:
    from scoring.calibration import occupation_proxies
    from scoring.pilot import canonical_hash
except ImportError:
    from calibration import occupation_proxies
    from pilot import canonical_hash


MODEL_VERSION = "occupational-archetype-v1-draft-2026q3"
BASELINE_VERSION = "archetype-structural-baseline-v1"
CLUSTER_COUNT = 28
TASK_BUCKETS = 48
MAX_ITERATIONS = 40
SOURCE_SCALES = {
    "skill": "LV",
    "ability": "LV",
    "work_activity": "IM",
    "work_context": "CX",
}
DIMENSIONS = (
    "physical-presence",
    "physical-manipulation",
    "mobility-real-world-operation",
    "environment-variability",
    "human-dependency",
    "regulation",
    "accountability",
    "consequence-severity",
    "real-time-interaction",
    "privacy-sensitivity",
    "adoption-pressure",
)
STOPWORDS = {
    "about", "after", "against", "also", "among", "and", "before", "being", "between",
    "from", "have", "into", "other", "such", "that", "their", "them", "then", "these",
    "they", "this", "those", "through", "using", "with", "work", "workers", "including",
    "ensure", "provide", "prepare", "perform", "maintain", "determine", "develop", "review",
}


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def rounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 4)


def words(statement: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-z][a-z-]{3,}", statement.lower())
        if token not in STOPWORDS
    ]


def task_bucket(token: str) -> int:
    return int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % TASK_BUCKETS


def distance_squared(left: list[float], right: list[float]) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right))


def mean_vector(vectors: list[list[float]], width: int) -> list[float]:
    if not vectors:
        return [0.0] * width
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(width)]


def deterministic_kmeans(
    vectors: list[list[float]], keys: list[str], cluster_count: int
) -> tuple[list[int], list[list[float]], list[float], list[float], int]:
    """Farthest-point initialization and stable tie-breaking; no RNG is used."""
    width = len(vectors[0])
    first = max(range(len(vectors)), key=lambda i: (sum(v * v for v in vectors[i]), keys[i]))
    centers = [vectors[first][:]]
    chosen = {first}
    while len(centers) < cluster_count:
        candidate = max(
            (index for index in range(len(vectors)) if index not in chosen),
            key=lambda index: (
                min(distance_squared(vectors[index], center) for center in centers),
                keys[index],
            ),
        )
        chosen.add(candidate)
        centers.append(vectors[candidate][:])

    assignments = [-1] * len(vectors)
    iterations = 0
    for iterations in range(1, MAX_ITERATIONS + 1):
        next_assignments = [
            min(range(cluster_count), key=lambda c: (distance_squared(vector, centers[c]), c))
            for vector in vectors
        ]
        if next_assignments == assignments:
            break
        assignments = next_assignments
        members = [[vectors[i] for i, value in enumerate(assignments) if value == c] for c in range(cluster_count)]
        for cluster, cluster_vectors in enumerate(members):
            if cluster_vectors:
                centers[cluster] = mean_vector(cluster_vectors, width)
            else:
                farthest = max(
                    range(len(vectors)),
                    key=lambda index: min(distance_squared(vectors[index], center) for center in centers),
                )
                centers[cluster] = vectors[farthest][:]

    nearest: list[float] = []
    second: list[float] = []
    for vector, assigned in zip(vectors, assignments):
        distances = sorted(
            (math.sqrt(distance_squared(vector, center)), cluster)
            for cluster, center in enumerate(centers)
        )
        assigned_distance = next(value for value, cluster in distances if cluster == assigned)
        next_distance = next(value for value, cluster in distances if cluster != assigned)
        nearest.append(assigned_distance)
        second.append(next_distance)
    return assignments, centers, nearest, second, iterations


def structural_value(
    ratings: dict[tuple[str, str, str], dict[str, Any]],
    specifications: list[tuple[tuple[str, str, str], float]],
) -> tuple[float | None, float, list[dict[str, Any]]]:
    available = [(key, weight, ratings[key]) for key, weight in specifications if key in ratings]
    expected_weight = sum(weight for _, weight in specifications)
    if not available:
        return None, 0.0, []
    weight = sum(item[1] for item in available)
    value = sum(item[1] * float(item[2]["normalizedValue"]) for item in available) / weight
    evidence = [
        {
            "elementType": key[0], "elementId": key[1], "scaleId": key[2],
            "normalizedValue": row["normalizedValue"], "rowHash": row["rowHash"],
            "sourceVersion": row["sourceVersion"], "weight": factor,
        }
        for key, factor, row in available
    ]
    return rounded(value), rounded(100 * weight / expected_weight), evidence


def safe_phase4b_component(
    name: str,
    components: list[dict[str, Any]],
    ratings: dict[tuple[str, str, str], dict[str, Any]],
    domains: dict[str, dict[str, Any]],
    parameters: dict[str, Any],
    confidence_ceiling: float | None = None,
) -> dict[str, Any]:
    """Mirror the v1 component transform while permitting an absent source domain.

    The Phase 4B calculator intentionally raises when an occupation has no usable
    component. Discovery spans a wider set of O*NET occupations, so an absent
    domain is represented as null and excluded from its cluster baseline.
    """
    used = []
    configured_total = sum(float(item["weight"]) for item in components)
    for component in components:
        source = None
        value = None
        if "derivedDomain" in component:
            source = domains.get(component["derivedDomain"])
            if source and source["value"] is not None:
                value = float(source["value"])
        else:
            key = (component["elementType"], component["elementId"], component["scaleId"])
            source = ratings.get(key)
            if source and not source.get("recommendSuppress") and not source.get("notRelevant"):
                value = float(source["normalizedValue"])
                if component.get("transform") == "inverse":
                    value = 100.0 - value
        if value is not None:
            used.append((component, value, source))
    if not used:
        return {"name": name, "value": None, "confidence": 0.0, "components": [],
                "formula": "phase4b-domain-proxy-v1"}
    available = sum(float(component["weight"]) for component, _, _ in used)
    value = sum(float(component["weight"]) * raw for component, raw, _ in used) / available
    missing_ratio = (configured_total - available) / configured_total
    confidence = float(parameters["baseConfidence"]) - missing_ratio * float(
        parameters["missingComponentPenaltyMaximum"]
    )
    if confidence_ceiling is not None:
        confidence = min(confidence, confidence_ceiling)
    evidence = [
        {"label": component["label"], "configuredWeight": component["weight"],
         "normalizedWeight": round(float(component["weight"]) / available, 8),
         "rawValue": rounded(raw),
         "source": "derived_domain" if "derivedDomain" in component else "onet_element_rating"}
        for component, raw, _ in used
    ]
    return {"name": name, "value": rounded(value), "confidence": rounded(confidence),
            "components": evidence, "formula": "phase4b-domain-proxy-v1"}


def structural_profile(
    ratings: dict[tuple[str, str, str], dict[str, Any]], proxy_parameters: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    phase4b_domains: dict[str, dict[str, Any]] = {}
    for name, components in proxy_parameters["domains"].items():
        phase4b_domains[name] = safe_phase4b_component(
            name, components, ratings, phase4b_domains, proxy_parameters
        )
    adoption_config = proxy_parameters["adoptionPressure"]
    adoption = safe_phase4b_component(
        "adoption-pressure", adoption_config["components"], ratings, phase4b_domains,
        proxy_parameters, float(adoption_config["confidenceCeiling"]),
    )
    profile: dict[str, dict[str, Any]] = {}
    for dimension in (
        "physical-presence", "environment-variability", "human-dependency", "regulation",
        "accountability", "consequence-severity",
    ):
        domain = phase4b_domains[dimension]
        profile[dimension] = {
            "value": float(domain["value"]) if domain["value"] is not None else None,
            "confidence": float(domain["confidence"]),
            "formula": "phase4b-domain-proxy-v1", "evidence": domain.get("components", []),
        }
    profile["adoption-pressure"] = {
        "value": float(adoption["value"]) if adoption["value"] is not None else None,
        "confidence": float(adoption["confidence"]),
        "formula": "phase4b-adoption-pressure-v1",
        "evidence": adoption.get("components", []),
    }

    extra_specs = {
        "physical-manipulation": [
            (("ability", "1.A.2.a.2", "LV"), .27), (("ability", "1.A.2.a.3", "LV"), .23),
            (("ability", "1.A.2.c.2", "LV"), .10), (("work_activity", "4.A.3.a.2", "IM"), .25),
            (("work_activity", "4.A.3.b.4", "IM"), .08), (("work_activity", "4.A.3.b.5", "IM"), .07),
        ],
        "mobility-real-world-operation": [
            (("work_activity", "4.A.3.a.1", "IM"), .30), (("work_activity", "4.A.3.a.4", "IM"), .24),
            (("work_context", "4.C.2.a.1.c", "CX"), .09), (("work_context", "4.C.2.a.1.d", "CX"), .09),
            (("work_context", "4.C.2.a.1.e", "CX"), .08), (("work_context", "4.C.2.a.1.f", "CX"), .08),
            (("work_context", "4.C.2.d.1.d", "CX"), .12),
        ],
        "real-time-interaction": [
            (("work_context", "4.C.1.a.2.l", "CX"), .28), (("work_context", "4.C.1.a.4", "CX"), .26),
            (("work_context", "4.C.1.a.2.c", "CX"), .12), (("work_context", "4.C.3.d.1", "CX"), .20),
            (("work_context", "4.C.3.d.3", "CX"), .14),
        ],
        "privacy-sensitivity": [
            (("work_activity", "4.A.2.a.3", "IM"), .30), (("work_activity", "4.A.2.b.3", "IM"), .20),
            (("work_activity", "4.A.2.b.2", "IM"), .15), (("work_context", "4.C.1.b.1.f", "CX"), .10),
        ],
    }
    for dimension, specifications in extra_specs.items():
        value, completeness, evidence = structural_value(ratings, specifications)
        confidence = min(completeness, 70.0 if dimension == "privacy-sensitivity" else 82.0)
        profile[dimension] = {
            "value": value, "confidence": confidence,
            "formula": f"archetype-source-evidence-{dimension}-v1", "evidence": evidence,
        }
    # Privacy is deliberately penalized: public O*NET characteristics are an indirect signal only.
    if profile["privacy-sensitivity"]["value"] is not None:
        value = profile["privacy-sensitivity"]["value"]
        supporting = [(value, .55)]
        if profile["regulation"]["value"] is not None:
            supporting.append((profile["regulation"]["value"], .25))
        if profile["consequence-severity"]["value"] is not None:
            supporting.append((profile["consequence-severity"]["value"], .20))
        total = sum(weight for _, weight in supporting)
        profile["privacy-sensitivity"]["value"] = rounded(
            sum(raw * weight for raw, weight in supporting) / total
        )
        profile["privacy-sensitivity"]["confidence"] = min(
            60.0, profile["privacy-sensitivity"]["confidence"]
        )
    return profile


async def load_inputs(connection: asyncpg.Connection) -> dict[str, Any]:
    occupations = [
        dict(row) for row in await connection.fetch(
            "SELECT onet_soc_code,title,row_hash,source_version FROM onet_occupations WHERE is_current ORDER BY onet_soc_code"
        )
    ]
    codes = [row["onet_soc_code"] for row in occupations]
    rows = await connection.fetch(
        """
        SELECT rating.occupation_code,rating.element_type,rating.element_id,rating.scale_id,
               rating.normalized_value,rating.sample_size,rating.standard_error,
               rating.recommend_suppress,rating.not_relevant,rating.row_hash,rating.source_version,
               element.element_name
        FROM onet_element_ratings rating
        JOIN onet_elements element ON element.element_type=rating.element_type
          AND element.element_id=rating.element_id AND element.is_current
        WHERE rating.is_current AND rating.occupation_code=ANY($1::text[])
        ORDER BY rating.occupation_code,rating.element_type,rating.element_id,rating.scale_id
        """, codes,
    )
    values: dict[str, dict[str, float]] = defaultdict(dict)
    labels: dict[str, str] = {}
    rating_hashes = []
    ratings_by_code: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if SOURCE_SCALES.get(row["element_type"]) == row["scale_id"]:
            feature = f"onet:{row['element_type']}:{row['element_id']}:{row['scale_id']}"
            values[row["occupation_code"]][feature] = float(row["normalized_value"]) / 100.0
            labels[feature] = row["element_name"]
        rating_hashes.append(row["row_hash"])
        ratings_by_code[row["occupation_code"]][
            (row["element_type"], row["element_id"], row["scale_id"])
        ] = {
            "normalizedValue": float(row["normalized_value"]), "rowHash": row["row_hash"],
            "sourceVersion": row["source_version"], "sampleSize": row["sample_size"],
            "standardError": float(row["standard_error"]) if row["standard_error"] is not None else None,
            "recommendSuppress": row["recommend_suppress"], "notRelevant": row["not_relevant"],
        }
    task_rows = await connection.fetch(
        "SELECT occupation_code,statement,row_hash,source_version FROM onet_tasks WHERE is_current ORDER BY occupation_code,task_id"
    )
    document_frequency: Counter[str] = Counter()
    tokens_by_code: dict[str, Counter[str]] = defaultdict(Counter)
    task_hashes = []
    for row in task_rows:
        tokens = words(row["statement"])
        tokens_by_code[row["occupation_code"]].update(tokens)
        document_frequency.update(set(tokens))
        task_hashes.append(row["row_hash"])
    occupation_count = len(occupations)
    for code, counter in tokens_by_code.items():
        total = max(1, sum(counter.values()))
        buckets = [0.0] * TASK_BUCKETS
        for token, count in counter.items():
            idf = math.log((1 + occupation_count) / (1 + document_frequency[token])) + 1.0
            buckets[task_bucket(token)] += count / total * idf
        norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
        for bucket, value in enumerate(buckets):
            feature = f"task-language:bucket-{bucket:02d}"
            values[code][feature] = value / norm
            labels[feature] = f"Task-language feature {bucket:02d}"
    return {
        "occupations": occupations, "values": values, "labels": labels,
        "ratingsByCode": ratings_by_code,
        "sourceHash": canonical_hash({"ratings": rating_hashes, "tasks": task_hashes}),
    }


def feature_matrix(inputs: dict[str, Any]) -> tuple[list[str], list[list[float]], list[float], dict[str, Any]]:
    features = sorted({feature for values in inputs["values"].values() for feature in values})
    raw = [[inputs["values"][row["onet_soc_code"]].get(feature, 0.0) for feature in features]
           for row in inputs["occupations"]]
    means = [statistics.fmean(row[index] for row in raw) for index in range(len(features))]
    deviations = [
        math.sqrt(statistics.fmean((row[index] - means[index]) ** 2 for row in raw)) or 1.0
        for index in range(len(features))
    ]
    group_sizes = Counter(
        "task-language" if feature.startswith("task-language") else feature.split(":")[1]
        for feature in features
    )
    vectors = []
    completeness = []
    onet_features = [feature for feature in features if feature.startswith("onet:")]
    for source_row, raw_row in zip(inputs["occupations"], raw):
        code_values = inputs["values"][source_row["onet_soc_code"]]
        completeness.append(100.0 * sum(feature in code_values for feature in onet_features) / len(onet_features))
        vector = []
        for index, feature in enumerate(features):
            group = "task-language" if feature.startswith("task-language") else feature.split(":")[1]
            vector.append(((raw_row[index] - means[index]) / deviations[index]) / math.sqrt(group_sizes[group]))
        vectors.append(vector)
    metadata = {
        "features": features,
        "means": {feature: round(means[i], 8) for i, feature in enumerate(features)},
        "standardDeviations": {feature: round(deviations[i], 8) for i, feature in enumerate(features)},
        "groupSizes": dict(group_sizes),
    }
    return features, vectors, completeness, metadata


async def run(model_version: str) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        existing = await connection.fetchrow(
            "SELECT id,cluster_count FROM occupational_archetype_model_versions WHERE model_version=$1",
            model_version,
        )
        if existing:
            await transaction.commit()
            return {"modelVersionId": existing["id"], "modelVersion": model_version,
                    "archetypes": existing["cluster_count"], "reused": True}
        inputs = await load_inputs(connection)
        features, all_vectors, all_completeness, normalization = feature_matrix(inputs)
        eligible_indexes = [index for index, value in enumerate(all_completeness) if value >= 65.0]
        excluded_codes = [
            row["onet_soc_code"] for index, row in enumerate(inputs["occupations"])
            if index not in set(eligible_indexes)
        ]
        discovery_occupations = [inputs["occupations"][index] for index in eligible_indexes]
        vectors = [all_vectors[index] for index in eligible_indexes]
        completeness = [all_completeness[index] for index in eligible_indexes]
        keys = [row["onet_soc_code"] for row in discovery_occupations]
        assignments, centers, nearest, second, iterations = deterministic_kmeans(
            vectors, keys, CLUSTER_COUNT
        )
        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Occupational Archetype Layer v1'"
        )
        flag_id = await connection.fetchval(
            "SELECT id FROM scoring_enrichment_feature_flags WHERE flag_key='occupational_archetype_layer'"
        )
        implementation_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        model_id = await connection.fetchval(
            """
            INSERT INTO occupational_archetype_model_versions (
              model_version,name,description,status,source_version,algorithm,cluster_count,random_seed,
              feature_schema,normalization_policy,discovery_configuration,feature_flag_id,
              source_input_hash,implementation_hash,source_id,provenance,created_by
            ) VALUES ($1,'JobsVsAI Occupational Archetype Layer v1',
              'Draft offline work-characteristic archetypes; not industry or SOC groupings.',
              'draft','O*NET 30.3','deterministic-farthest-point-kmeans-v1',$2,0,$3,$4,$5,$6,$7,$8,$9,$10,
              'system:archetype-discovery') RETURNING id
            """, model_version, CLUSTER_COUNT,
            dumps({"sources": SOURCE_SCALES, "taskLanguageBuckets": TASK_BUCKETS,
                   "featureCount": len(features), "minimumFeatureCompleteness": 65,
                   "excludedOccupationCount": len(excluded_codes),
                   "excludes": ["SOC", "title", "industry"]}),
            dumps(normalization),
            dumps({"initialization": "farthest-point", "iterations": iterations,
                   "maximumIterations": MAX_ITERATIONS, "distance": "euclidean",
                   "membershipPolicy": "primary plus optional near-tie secondary"}),
            flag_id, inputs["sourceHash"], implementation_hash, source_id,
            dumps({"additive": True, "versioned": True, "public": False,
                   "productionScoresModified": False, "externalAiCalls": 0}),
        )
        members = defaultdict(list)
        for index, cluster in enumerate(assignments):
            members[cluster].append(index)
        # Stable presentation order is based on source-derived representatives, not raw center index.
        presentation = sorted(
            range(CLUSTER_COUNT),
            key=lambda cluster: min(keys[index] for index in members[cluster]),
        )
        code_for_cluster = {cluster: f"A{position + 1:02d}" for position, cluster in enumerate(presentation)}
        definition_ids: dict[int, int] = {}
        profiles: dict[str, dict[str, dict[str, Any]]] = {}
        proxy_row = await connection.fetchrow(
            "SELECT parameters FROM phase4b_proxy_model_versions WHERE model_version='phase4b-occupation-proxy-v1'"
        )
        proxy_parameters = json.loads(proxy_row["parameters"]) if isinstance(proxy_row["parameters"], str) else proxy_row["parameters"]
        for code in keys:
            profiles[code] = structural_profile(inputs["ratingsByCode"][code], proxy_parameters)

        for cluster in presentation:
            indexes = members[cluster]
            ranked_features = sorted(
                ((centers[cluster][index], features[index]) for index in range(len(features))
                 if features[index].startswith("onet:")), reverse=True,
            )[:8]
            representatives = sorted(indexes, key=lambda index: (nearest[index], keys[index]))[:5]
            code = code_for_cluster[cluster]
            top_labels = [inputs["labels"][feature] for _, feature in ranked_features[:2]]
            name = f"{top_labels[0]} + {top_labels[1]} Work ({code})"
            rep_payload = [
                {"occupationCode": keys[index], "title": discovery_occupations[index]["title"],
                 "distance": round(nearest[index], 8)} for index in representatives
            ]
            separations = [(second[index] - nearest[index]) / max(second[index], .000001) for index in indexes]
            definition_id = await connection.fetchval(
                """
                INSERT INTO occupational_archetype_definitions (
                  model_version_id,archetype_code,name,description,interpretation_status,centroid,
                  top_features,representative_occupations,member_count,quality_metrics,source_id,
                  provenance,created_by
                ) VALUES ($1,$2,$3,$4,'candidate',$5,$6,$7,$8,$9,$10,$11,
                  'system:archetype-discovery') RETURNING id
                """, model_id, code, name,
                f"Candidate work-characteristic cluster led by {top_labels[0]} and {top_labels[1]}; "
                f"representatives: {', '.join(item['title'] for item in rep_payload[:3])}.",
                dumps({features[index]: round(value, 8) for index, value in enumerate(centers[cluster])}),
                dumps([{"feature": feature, "label": inputs["labels"][feature], "centroidZ": round(value, 8)}
                       for value, feature in ranked_features]), dumps(rep_payload), len(indexes),
                dumps({"meanNearestDistance": round(statistics.fmean(nearest[index] for index in indexes), 8),
                       "meanSeparation": round(statistics.fmean(separations), 8),
                       "meanFeatureCompleteness": round(statistics.fmean(completeness[index] for index in indexes), 4),
                       "singleton": len(indexes) == 1}), source_id,
                dumps({"source": "O*NET 30.3", "titleUse": "post-discovery interpretation only"}),
            )
            definition_ids[cluster] = definition_id
            for dimension in DIMENSIONS:
                observations = [profiles[keys[index]][dimension] for index in indexes
                                if profiles[keys[index]][dimension]["value"] is not None]
                if not observations:
                    raise ValueError(f"No source-supported {dimension} values for {code}")
                baseline = statistics.fmean(float(item["value"]) for item in observations)
                dispersion = statistics.pstdev(float(item["value"]) for item in observations)
                source_confidence = statistics.fmean(float(item["confidence"]) for item in observations)
                confidence = rounded(source_confidence * min(1.0, math.sqrt(len(observations) / 8))
                                     * max(.45, 1 - dispersion / 100))
                await connection.execute(
                    """
                    INSERT INTO archetype_structural_baselines (
                      archetype_definition_id,baseline_version,structural_dimension,baseline_value,
                      confidence,supporting_occupation_count,source_dispersion,formula_version,
                      exact_inputs,source_id,provenance,created_by
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,'archetype-member-mean-v1',$8,$9,$10,
                      'system:archetype-baseline')
                    """, definition_id, BASELINE_VERSION, dimension, rounded(baseline), confidence,
                    len(observations), round(dispersion, 4),
                    dumps({"memberOccupationCodes": [keys[index] for index in indexes],
                           "observations": [{"value": item["value"], "confidence": item["confidence"],
                                             "formula": item["formula"]} for item in observations],
                           "aggregation": "unweighted arithmetic mean; no missing-value invention"}),
                    source_id, dumps({"modelVersion": model_version, "sourceVersion": "O*NET 30.3"}),
                )

        secondary_count = 0
        for index, code in enumerate(keys):
            distances = sorted(
                (math.sqrt(distance_squared(vectors[index], centers[cluster])), cluster)
                for cluster in range(CLUSTER_COUNT)
            )
            d1, primary = distances[0]
            d2, secondary = distances[1]
            primary_strength = rounded(100 * d2 / max(.000001, d1 + d2))
            secondary_strength = rounded(100 * d1 / max(.000001, d1 + d2))
            confidence = rounded(.65 * max(0, (primary_strength - 50) * 2) + .35 * completeness[index])
            evidence = {
                "modelVersion": model_version, "featureSchemaHash": canonical_hash(normalization),
                "nearestDistance": round(d1, 8), "secondDistance": round(d2, 8),
                "separationRatio": round((d2 - d1) / max(d2, .000001), 8),
                "postDiscoveryTitleUseOnly": True,
            }
            await connection.execute(
                """
                INSERT INTO occupation_archetype_memberships (
                  model_version_id,archetype_definition_id,occupation_code,membership_role,
                  membership_strength,membership_confidence,distance_to_centroid,distance_rank,
                  feature_completeness,evidence,source_id,provenance,created_by
                ) VALUES ($1,$2,$3,'primary',$4,$5,$6,1,$7,$8,$9,$10,'system:archetype-discovery')
                """, model_id, definition_ids[primary], code, primary_strength, confidence,
                round(d1, 8), rounded(completeness[index]), dumps(evidence), source_id,
                dumps({"sourceVersion": "O*NET 30.3", "role": "primary"}),
            )
            if secondary_strength >= 42 and d2 <= 1.38 * max(d1, .000001):
                secondary_count += 1
                await connection.execute(
                    """
                    INSERT INTO occupation_archetype_memberships (
                      model_version_id,archetype_definition_id,occupation_code,membership_role,
                      membership_strength,membership_confidence,distance_to_centroid,distance_rank,
                      feature_completeness,evidence,source_id,provenance,created_by
                    ) VALUES ($1,$2,$3,'secondary',$4,$5,$6,2,$7,$8,$9,$10,
                      'system:archetype-discovery')
                    """, model_id, definition_ids[secondary], code, secondary_strength,
                    rounded(confidence * .8), round(d2, 8), rounded(completeness[index]),
                    dumps(evidence), source_id,
                    dumps({"sourceVersion": "O*NET 30.3", "role": "secondary"}),
                )
        await transaction.commit()
        sizes = [len(members[cluster]) for cluster in range(CLUSTER_COUNT)]
        return {
            "modelVersionId": model_id, "modelVersion": model_version, "archetypes": CLUSTER_COUNT,
            "occupations": len(keys), "excludedForInsufficientFeatures": len(excluded_codes),
            "features": len(features), "iterations": iterations,
            "secondaryMemberships": secondary_count, "minimumClusterSize": min(sizes),
            "maximumClusterSize": max(sizes), "singletonClusters": sum(size == 1 for size in sizes),
            "externalAiCalls": 0, "productionScoreWrites": 0, "featureFlagEnabled": False,
            "reused": False,
        }
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-version", default=MODEL_VERSION)
    args = parser.parse_args()
    print(json.dumps(await run(args.model_version), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
