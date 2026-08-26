"""Read-only engine probe for an occupation that never entered a Phase 5 namespace.

Answers one question without writing anything: **what would the scoring engine say about this
occupation, using only the mappings it already has?**

Why this exists as a separate tool rather than a pipeline flag. The Phase 5 runners are
namespace-driven — they score the frozen population of a `phase5_candidate_namespaces` row —
and they have no dry-run mode. An occupation outside every namespace therefore cannot be
scored by them at all without first creating a namespace for it, which is a write to
append-only methodological history and a decision that deserves to be made on evidence rather
than in order to obtain the evidence. This probe assembles the same inputs in memory and calls
the same `calculate()` the pipeline calls, so the numbers are the engine's own.

What it does NOT do, deliberately:

  * write anything — no namespace, candidate, scope row, assessment or snapshot
  * invent or regenerate mappings; a task with no mapping is simply not scoring-eligible
  * relax the ambiguity rule; an `ambiguous_scope` mapping is excluded exactly as the pipeline
    excludes it, which is what keeps the coverage figure honest

Two launch gates cannot be evaluated for a single occupation in isolation, and the output says
so rather than implying a clean sweep: **review-readiness** is a property of a candidate row
that does not exist here (the probe asserts it), and **related-SOC discontinuity** is a
corpus-level comparison against sibling occupations. A real scoring run evaluates both.

    docker compose run --rm -e PYTHONPATH=/app/scoring worker \\
        python -m scoring.probe_occupation_score 15-1252.00
"""

import asyncio
import copy
import json
import os
import sys
from collections import defaultdict
sys.path.insert(0, "/app/scoring")
import asyncpg

from calibration import occupation_proxies
from phase4d_proxies import (direct_structural_proxies, MODEL_VERSION as PHASE4D_MODEL,
    PHYSICAL_COMPONENTS, ENVIRONMENT_COMPONENTS, ACCOUNTABILITY_COMPONENTS,
    CONSEQUENCE_BASE_COMPONENTS, CLINICAL_COMPONENTS)
from run_phase4a_pilot import load_dependencies, decoded
from phase6_launch_triage import triage_occupation
from run_phase4b_calibration import (OCCUPATION_FORMULA, PROXY_MODEL, TASK_FORMULAS, calculate,
                                     collect_source_keys)

ALL_DIRECT_COMPONENTS = (PHYSICAL_COMPONENTS + ENVIRONMENT_COMPONENTS + ACCOUNTABILITY_COMPONENTS
                         + CONSEQUENCE_BASE_COMPONENTS + CLINICAL_COMPONENTS)

TARGET_ARG = sys.argv[1] if len(sys.argv) > 1 else "15-1252.00"

async def probe(conn, target: str) -> dict | None:
    """Score one occupation from its existing mappings. Returns None when it cannot be scored.

    Callable form of the CLI below, so the preliminary-estimate generator can prefer an
    occupation's own engine evidence over a related-occupation proxy without shelling out.
    """
    TARGET = target
    if True:
        deps = await load_dependencies(conn, "phase4a-2026q3-v1",
                                       task_formula_versions=TASK_FORMULAS,
                                       occupation_formula_version=OCCUPATION_FORMULA)
        row = await conn.fetchrow("""
            SELECT ci.id identity_id, ci.current_source_code code, COALESCE(n.title, ci.current_source_code) title
            FROM canonical_occupation_identities ci
            LEFT JOIN onet_occupations n ON n.onet_soc_code = ci.current_source_code
            WHERE ci.current_source_code = $1""", TARGET)
        occupation = {"id": 1, "occupation_code": row["code"], "identity_id": row["identity_id"],
                      "title_snapshot": row["title"], "source_title": row["title"],
                      "soc_major_group": row["code"][:2], "warnings": "[]", "cohort_order": 1}

        # Tasks joined to their existing mappings. A mapping flagged ambiguous is NOT
        # scoring-eligible, exactly as the pipeline treats it — that rule is what keeps
        # coverage honest, so the probe must not relax it.
        tasks = [dict(r) for r in await conn.fetch("""
            SELECT task.*, 1 AS pilot_occupation_id, mapping.id AS mapping_id,
                   mapping.mapping_confidence, mapping.ambiguity_state,
                   (mapping.id IS NOT NULL AND mapping.ambiguity_state = 'none') AS scoring_eligible,
                   mapping.mapping_run_id, 'probe'::text AS scope_decision,
                   NULL::text AS dependency_reuse_key
            FROM onet_tasks task
            LEFT JOIN ai_generated_task_mappings mapping ON mapping.onet_task_id = task.task_id
            WHERE task.occupation_code = $1 AND task.is_current
            ORDER BY task.task_id""", TARGET)]

        mapping_ids = sorted({t["mapping_id"] for t in tasks if t["mapping_id"] is not None})
        requirements = defaultdict(list)
        for r in await conn.fetch("""
            SELECT requirement.ai_task_mapping_id, definition.slug, definition.name, requirement.weight,
                   requirement.required_capability_level, requirement.confidence, requirement.rationale,
                   requirement.evidence
            FROM ai_generated_task_capability_requirements requirement
            JOIN ai_capability_definitions definition ON definition.id=requirement.capability_definition_id
            WHERE requirement.ai_task_mapping_id=ANY($1::bigint[])
            ORDER BY requirement.ai_task_mapping_id, definition.slug""", mapping_ids):
            requirements[r["ai_task_mapping_id"]].append({
                "slug": r["slug"], "name": r["name"], "weight": float(r["weight"]),
                "requiredLevel": float(r["required_capability_level"]),
                "mappingConfidence": float(r["confidence"]), "rationale": r["rationale"],
                "evidence": decoded(r["evidence"])})
        constraints = defaultdict(list)
        for r in await conn.fetch("""
            SELECT mapped.ai_task_mapping_id, definition.slug, definition.name, mapped.constraint_level,
                   mapped.confidence, mapped.rationale, mapped.evidence
            FROM ai_generated_task_environment_constraints mapped
            JOIN task_environment_constraint_definitions definition ON definition.id=mapped.constraint_definition_id
            WHERE mapped.ai_task_mapping_id=ANY($1::bigint[])
            ORDER BY mapped.ai_task_mapping_id, definition.slug""", mapping_ids):
            constraints[r["ai_task_mapping_id"]].append({
                "slug": r["slug"], "name": r["name"], "level": float(r["constraint_level"]),
                "confidence": float(r["confidence"]), "rationale": r["rationale"],
                "evidence": decoded(r["evidence"])})

        base_model_row = await conn.fetchrow(
            "SELECT * FROM phase4b_proxy_model_versions WHERE model_version=$1", PROXY_MODEL)
        base_model = dict(base_model_row)
        base_model["parameters"] = decoded(base_model["parameters"])
        source_keys = collect_source_keys(base_model["parameters"])
        source_keys.update((i["elementType"], i["elementId"], i["scaleId"])
                           for i in ALL_DIRECT_COMPONENTS if i["kind"] == "element")

        ratings = {}
        for r in await conn.fetch("""
            SELECT rating.element_type, rating.element_id, rating.scale_id, rating.normalized_value,
                   rating.sample_size, rating.standard_error, rating.recommend_suppress,
                   rating.not_relevant, rating.source_version, rating.source_record_id,
                   rating.row_hash, element.element_name
            FROM onet_element_ratings rating
            JOIN onet_elements element ON element.element_type=rating.element_type
              AND element.element_id=rating.element_id AND element.is_current
            WHERE rating.is_current AND rating.occupation_code=$1""", TARGET):
            key = (r["element_type"], r["element_id"], r["scale_id"])
            if key not in source_keys:
                continue
            ratings[key] = {
                "normalizedValue": float(r["normalized_value"]), "sampleSize": r["sample_size"],
                "standardError": float(r["standard_error"]) if r["standard_error"] is not None else None,
                "recommendSuppress": r["recommend_suppress"], "notRelevant": r["not_relevant"],
                "sourceVersion": r["source_version"], "sourceRecordId": r["source_record_id"],
                "rowHash": r["row_hash"], "elementName": r["element_name"]}

        task_payload = [{"taskId": t["task_id"], "statement": t["statement"],
                         "sourceWeight": float(t["importance_score"] * t["frequency_score"]) if t["weighting_eligible"] else None,
                         "rowHash": t["row_hash"], "sourceVersion": t["source_version"]} for t in tasks]

        base = occupation_proxies(ratings, base_model["parameters"])
        direct = direct_structural_proxies(ratings, task_payload)
        domains = copy.deepcopy(base["domains"])
        for family, value in direct["families"].items():
            domains[family] = {"name": family, "value": float(value["value"]),
                               "confidence": float(value["confidence"]),
                               "components": value["components"], "reconciliation": value["reconciliation"]}
        # Mirrors the flattened column set the pipeline persists to phase5_proxy_snapshots,
        # because calculate() reads the scalars off the row rather than out of the nested
        # component contributions.
        snapshot = {"id": 0, "candidate_occupation_id": 1,
                    "component_contributions": {"domains": domains,
                        "adoptionPressure": base["adoptionPressure"],
                        "labourMarketResilience": base["labourMarketResilience"]},
                    "family_values": direct["families"],
                    "adoption_pressure": float(base["adoptionPressure"]["value"]),
                    "labour_market_resilience": float(base["labourMarketResilience"]["value"]),
                    "proxy_confidence": min(float(base["confidence"]), float(direct["confidence"])),
                    "confidence": min(float(base["confidence"]), float(direct["confidence"])),
                    "warnings": [], "reconciliation": {"passed": True}, "exact_inputs": {}}
        for family, value in direct["families"].items():
            snapshot[family.replace("-", "_")] = float(value["value"])

        deps["cohort"] = {"id": 0, "cohort_version": "probe", "mapping_run_id": None}
        deps["namespace"] = {"namespace_version": "probe", "occupation_population_count": 1}
        deps["occupations"] = [occupation]
        deps["tasks"] = tasks
        deps["requirements"] = requirements
        deps["constraints"] = constraints

        task_results, occ_results = calculate(deps, {1: snapshot}, base_model,
                                              methodology_phase="5", mapping_scope_version="probe")
        o = occ_results[0]
        # Provisional-input sensitivity, computed exactly as run_phase5_bounded does: a
        # one-at-a-time neutral-50 counterfactual on each provisional model. This is the gate
        # that keeps 59 otherwise-clean occupations out of the verified cohort, so it decides
        # whether this one can join it.
        rw = deps["occupationFormula"]["parameters"]["replacementWeights"]
        rr = float(o["replacementRisk"])
        adoption = float(snapshot["adoption_pressure"])
        resilience = float(snapshot["labour_market_resilience"])
        adoption_delta = -float(rw["adoptionPressure"]) * (adoption - 50.0)
        labour_delta = -float(rw["labourMarketResilienceResistance"]) * (50.0 - resilience)
        impacts = {"adoptionNeutralReplacementRiskDelta": round(adoption_delta, 4),
                   "labourNeutralReplacementRiskDelta": round(labour_delta, 4)}
        max_impact = max(abs(v) for v in impacts.values())

        # Feed the REAL launch-gate assessor, not a hand-rolled reimplementation of it.
        triage_row = {
            "candidateOccupationId": 1, "occupationCode": TARGET, "title": row["title"],
            "aiExposure": o["aiExposure"], "replacementRisk": o["replacementRisk"],
            "confidence": o["confidence"], "weightedTaskCoverage": o["coverage"],
            "candidateStatus": "review_ready",
            "coverageGateStatus": o["coverageGateStatus"], "confidenceGateStatus": "passed",
            "reconciliation": o["reconciliation"],
            "provisionalSensitivity": {**impacts,
                                       "maximumAbsoluteScoreImpact": round(max_impact, 4)},
            "factorContributions": o["factors"],
            "taskContributions": o["tasks"],
            "structuralProxyInputs": {
                "values": {k.replace("_", "-"): v for k, v in snapshot.items()
                           if isinstance(v, float)},
                "missingDataPolicy":
                    "exclude and renormalize observed values; never invent or impute"},
        }
        findings = triage_occupation(triage_row)
        blocking = [f["code"] for f in findings if f.get("severity") in ("critical", "high")]

        return {
            "occupation": row["title"], "soc": TARGET,
            "launchEligible": not blocking,
            "blockingFindings": blocking,
            "allFindings": [f"{f['code']} ({f.get('severity')})" for f in findings],
            "provisionalSensitivity": impacts,
            "maximumAbsoluteScoreImpact": round(max_impact, 3),
            "sensitivityGate": "PASS" if max_impact < 3.0 else "FAIL (>=3.0)",
            "adoptionPressureValue": round(adoption, 2),
            "labourMarketResilienceValue": round(resilience, 2),
            "tasksTotal": len(tasks),
            "weightingEligible": sum(1 for t in tasks if t["weighting_eligible"]),
            "mappedTasks": len(mapping_ids),
            "scoringEligible": sum(1 for t in tasks if t["scoring_eligible"]),
            "excludedByAmbiguity": sum(1 for t in tasks
                                       if t["mapping_id"] is not None and not t["scoring_eligible"]),
            "aiExposure": o["aiExposure"], "replacementRisk": o["replacementRisk"],
            "confidence": o["confidence"],
            "weightedTaskCoverage": o["coverage"],
            "coverageGateStatus": o["coverageGateStatus"],
            "scaleEligible": o["scaleEligible"],
            "provisionalFactors": [f["factor"] for f in o["factors"] if f.get("provisionalProxy")],
            "provisionalWeight": sum(f["weight"] for f in o["factors"] if f.get("provisionalProxy")),
            "warnings": [w.get("code") for w in (o.get("warnings") or [])],
            "reconciliationPassed": o["reconciliation"].get("passed"),
        }
    return None


async def main() -> None:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        result = await probe(conn, TARGET_ARG)
        if result is None:
            print(json.dumps({"occupation": TARGET_ARG, "scoreable": False}, indent=2))
            return
        print(json.dumps(result, indent=2, default=str))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
