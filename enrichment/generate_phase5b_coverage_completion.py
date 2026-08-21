"""Phase 5B — task-mapping coverage completion.

Phase 5's mapper stopped generating mappings for an occupation the moment weighted
coverage crossed 70% (`generate_phase5_candidate_mappings.COVERAGE_THRESHOLD`). That is
why corpus coverage clusters at 70-75 and why 868 of 878 candidates fail the Phase 6
launch gate of 80: the gate is being applied to a corpus deliberately built to stop at 70.

This generator continues the mapping work that Phase 5 skipped. It is a *completion* pass,
not a re-run:

  * every mapping Phase 5 (or an earlier phase) already produced is reused by task id or
    statement hash — nothing structurally eligible is regenerated;
  * only tasks Phase 5 left `unmapped_after_gate` are newly attempted;
  * an occupation stops when weighted mapped coverage reaches the completion target, or
    when no defensibly mappable task remains — whichever comes first.

Three thresholds are deliberately distinct and are never conflated:

  70  scoring eligibility     unchanged; enforced by the occupation formula
                              (`minimumWeightedCoverage`), not by this file
  85  mapping completion      this file's target; set above 80 so completion does not
                              manufacture a fresh pile-up immediately above the launch gate
  80  public launch coverage  unchanged; enforced by `phase6_launch_triage`

The target is not a quota. Ambiguity, insufficient-description and no-inference rules are
inherited verbatim from the approved rubric; an occupation that exhausts its defensibly
mappable tasks at 74% is recorded at 74% and is not pushed further.

Determinism and cost: `disposition`, `capability_payload` and `constraint_payload` are
pure functions over the task statement. This pass makes zero external AI calls.

Run:
  docker compose run --rm -e PYTHONPATH=/app/enrichment backend \
      python /app/enrichment/generate_phase5b_coverage_completion.py
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import asyncpg

try:
    from .generate_phase4a_pilot_mappings import (
        FORBIDDEN_INPUTS,
        capability_payload,
        constraint_payload,
        disposition,
    )
except ImportError:
    from generate_phase4a_pilot_mappings import (
        FORBIDDEN_INPUTS,
        capability_payload,
        constraint_payload,
        disposition,
    )


BASE_NAMESPACE_VERSION = "phase5-candidate-2026q3-v1"
NAMESPACE_VERSION = "phase5b-candidate-2026q3-v1"
MAPPING_RUN_VERSION = "phase5b-completion-mapper-v1-2026q3"
MAPPING_SCOPE_VERSION = "phase5b-mapping-completion-v1"
PROMPT_VERSION = "phase5b-deterministic-score-blind-completion-prompt-v1"

# The mapping completion target. Deliberately above the 80 launch gate so that completing
# coverage does not recreate an artificial concentration just above the publication line.
COMPLETION_TARGET = 85.0
# Recorded for provenance only. Neither is enforced here.
SCORING_ELIGIBILITY_THRESHOLD = 70.0
LAUNCH_COVERAGE_GATE = 80.0

PROMPT_TEXT = """JobsVsAI Phase 5B deterministic score-blind coverage-completion mapper v1.
Use only the current O*NET 30.3 task statement, source importance/frequency for
completion ordering, AI Capability Taxonomy v1, Task-to-Capability Rubric v1,
Environment Constraint Taxonomy v1 and MVP Evidence Policy v1. Reuse an existing
validated mapping when the task id and statement hash match, or when the exact
statement hash matches. Continue creating missing mappings until weighted coverage
reaches 85% or no defensibly mappable task remains. Never read Frontier capability
values, task scores, occupation scores, automation outcomes, target distributions,
titles or SOC categories. Do not infer omitted context or invent missing requirements.
Coverage is a stopping condition, never a quota.
"""


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def md5_statement(statement: str) -> str:
    return hashlib.md5(statement.encode(), usedforsecurity=False).hexdigest()


def coverage_bucket(value: float) -> str:
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


async def generate(
    namespace_version: str = NAMESPACE_VERSION,
    run_version: str = MAPPING_RUN_VERSION,
    base_namespace_version: str = BASE_NAMESPACE_VERSION,
    completion_target: float = COMPLETION_TARGET,
) -> dict[str, Any]:
    started = time.perf_counter()
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 5 bounded corpus scoring'"
        )
        policy = await connection.fetchrow(
            """
            SELECT policy.*,rubric.environment_taxonomy_version_id,rubric.version rubric_version,
                   taxonomy.version taxonomy_version
            FROM task_mapping_evidence_policy_versions policy
            JOIN task_mapping_rubric_versions rubric ON rubric.id=policy.rubric_version_id
            JOIN ai_capability_taxonomy_versions taxonomy ON taxonomy.id=policy.taxonomy_version_id
            WHERE policy.policy_version='mvp-evidence-policy-v1'
            """
        )
        if source_id is None or policy is None:
            raise ValueError("Phase 5 source or approved mapping policy is missing")

        base_namespace = await connection.fetchrow(
            "SELECT * FROM phase5_candidate_namespaces WHERE namespace_version=$1",
            base_namespace_version,
        )
        if base_namespace is None:
            raise ValueError(
                f"Phase 5B completes an existing namespace; {base_namespace_version} is missing"
            )

        profile_rows = await connection.fetch(
            """
            SELECT profile.*,identity.id identity_id,occupation.title,
                   occupation.source_version occupation_source_version
            FROM occupation_promotion_profiles profile
            JOIN canonical_occupation_identities identity ON identity.id=profile.identity_id
            JOIN onet_occupations occupation
              ON occupation.onet_soc_code=profile.source_occupation_code AND occupation.is_current
            WHERE profile.scoring_eligible
            ORDER BY profile.source_occupation_code
            """
        )
        population_manifest = [
            {
                "occupationCode": row["source_occupation_code"],
                "identityId": row["identity_id"],
                "lifecyclePolicyVersion": row["lifecycle_policy_version"],
                "scoringPolicyVersion": row["scoring_policy_version"],
                "sourceVersion": row["source_version"],
            }
            for row in profile_rows
        ]
        population_hash = canonical_hash(population_manifest)
        # Phase 5B may only add evidence. A different population would make the score
        # comparison against Phase 5 meaningless.
        if population_hash != base_namespace["occupation_population_hash"]:
            raise ValueError(
                "Scoring-ready population differs from Phase 5; coverage completion requires "
                "an identical population so score deltas are attributable to evidence alone"
            )

        existing_namespace = await connection.fetchrow(
            "SELECT * FROM phase5_candidate_namespaces WHERE namespace_version=$1",
            namespace_version,
        )
        if existing_namespace:
            scope_count = await connection.fetchval(
                "SELECT count(*) FROM phase5_task_mapping_scope WHERE namespace_id=$1",
                existing_namespace["id"],
            )
            task_count = await connection.fetchval(
                """
                SELECT count(*) FROM phase5_candidate_occupations candidate
                JOIN onet_tasks task ON task.occupation_code=candidate.occupation_code AND task.is_current
                WHERE candidate.namespace_id=$1
                """,
                existing_namespace["id"],
            )
            if scope_count == task_count:
                run = await connection.fetchrow(
                    "SELECT * FROM ai_generated_task_mapping_runs WHERE run_version=$1", run_version
                )
                await transaction.commit()
                return {
                    "namespaceId": existing_namespace["id"],
                    "namespaceVersion": namespace_version,
                    "mappingRunId": run["id"] if run else None,
                    "scoringReadyOccupations": existing_namespace["occupation_population_count"],
                    "scopeRows": scope_count,
                    "externalAiCalls": 0,
                    "estimatedAiTokens": 0,
                    "reused": True,
                }
            raise ValueError("Partial Phase 5B namespace exists; refusing to overwrite append-only history")

        exact_policy = {
            "phase": "5B",
            "source": "O*NET 30.3",
            "completes": base_namespace_version,
            "taxonomyVersion": policy["taxonomy_version"],
            "rubricVersion": policy["rubric_version"],
            "evidencePolicyVersion": policy["policy_version"],
            "mappingScopeVersion": MAPPING_SCOPE_VERSION,
            "mappingCompletionTarget": completion_target,
            "scoringEligibilityThreshold": SCORING_ELIGIBILITY_THRESHOLD,
            "launchCoverageGate": LAUNCH_COVERAGE_GATE,
            "thresholdSeparation": (
                "70 decides whether a score may exist, 85 decides when mapping work stops, "
                "80 decides whether a score may be published. Phase 5B changes only the second."
            ),
            "reusePriority": ["exact_task_and_statement_hash", "exact_statement_hash"],
            "missingMappingPolicy": (
                "generate deterministic task-local mappings until the completion target or until "
                "defensibly mappable tasks are exhausted; never impute, never force the target"
            ),
            "targetIsQuota": False,
            "externalAiCallsAllowed": False,
            "publicActivation": False,
            "productionWrites": False,
            "archetypeScoring": False,
            "provisionalModels": ["regulation", "adoption-pressure", "labour-market-resilience"],
        }
        namespace_id = await connection.fetchval(
            """
            INSERT INTO phase5_candidate_namespaces (
              namespace_version,name,status,source_version,scoring_ready_policy_version,
              mapping_scope_version,occupation_population_count,occupation_population_hash,
              coverage_threshold,exact_policy,source_id,provenance,created_by
            ) VALUES ($1,'JobsVsAI Phase 5B coverage completion','candidate','O*NET 30.3',$2,$3,$4,$5,$6,$7,$8,$9,
              'system:phase5b-completion-mapper') RETURNING id
            """,
            namespace_version,
            profile_rows[0]["scoring_policy_version"],
            MAPPING_SCOPE_VERSION,
            len(profile_rows),
            population_hash,
            completion_target,
            json.dumps(exact_policy),
            source_id,
            json.dumps({
                "bounded": True,
                "populationManifestHash": population_hash,
                "completesNamespaceId": base_namespace["id"],
                "completesNamespaceVersion": base_namespace_version,
            }),
        )

        candidate_by_code: dict[str, int] = {}
        for order, row in enumerate(profile_rows, 1):
            snapshot = {
                "lifecycleState": row["lifecycle_state"],
                "ingestionEligible": row["ingestion_eligible"],
                "scoringEligible": row["scoring_eligible"],
                "publicActivationEligible": row["public_activation_eligible"],
                "lifecyclePolicyVersion": row["lifecycle_policy_version"],
                "scoringPolicyVersion": row["scoring_policy_version"],
                "blockingReasons": row["blocking_reasons"],
                "sourceVersion": row["source_version"],
                "evaluatedAt": str(row["evaluated_at"]),
            }
            candidate_id = await connection.fetchval(
                """
                INSERT INTO phase5_candidate_occupations (
                  namespace_id,occupation_code,identity_id,cohort_order,title_snapshot,soc_major_group,
                  promotion_profile_snapshot,source_id,provenance,created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'system:phase5b-completion-mapper') RETURNING id
                """,
                namespace_id,
                row["source_occupation_code"],
                row["identity_id"],
                order,
                row["title"],
                row["source_occupation_code"].split("-")[0],
                json.dumps(snapshot, default=str),
                source_id,
                json.dumps({"populationHash": population_hash, "sourceVersion": row["occupation_source_version"]}),
            )
            candidate_by_code[row["source_occupation_code"]] = candidate_id

        tasks = [
            dict(row)
            for row in await connection.fetch(
                """
                SELECT task.* FROM onet_tasks task
                JOIN phase5_candidate_occupations candidate
                  ON candidate.occupation_code=task.occupation_code AND candidate.namespace_id=$1
                WHERE task.is_current
                ORDER BY candidate.cohort_order,task.task_id
                """,
                namespace_id,
            )
        ]

        # What Phase 5 decided, so the completion pass can report exactly what it inherited
        # and what it changed. Read-only.
        base_decisions = {
            row["onet_task_id"]: row["scope_decision"]
            for row in await connection.fetch(
                "SELECT onet_task_id,scope_decision FROM phase5_task_mapping_scope WHERE namespace_id=$1",
                base_namespace["id"],
            )
        }

        eligible_mapping_rows = await connection.fetch(
            """
            WITH latest_event AS (
              SELECT DISTINCT ON (event.ai_task_mapping_id)
                     event.ai_task_mapping_id,event.scoring_eligible,event.created_at,event.id
              FROM ai_task_mapping_validation_events event
              ORDER BY event.ai_task_mapping_id,event.created_at DESC,event.id DESC
            )
            SELECT mapping.id,mapping.onet_task_id,mapping.mapping_run_id,mapping.task_statement_hash,
                   mapping.mapping_confidence,mapping.created_at
            FROM ai_generated_task_mappings mapping
            JOIN ai_generated_task_mapping_runs run ON run.id=mapping.mapping_run_id
            JOIN latest_event event ON event.ai_task_mapping_id=mapping.id AND event.scoring_eligible
            WHERE run.taxonomy_version_id=$1 AND run.rubric_version_id=$2
              AND run.evidence_policy_version_id=$3
            ORDER BY mapping.id DESC
            """,
            policy["taxonomy_version_id"],
            policy["rubric_version_id"],
            policy["id"],
        )
        exact_mapping: dict[int, dict[str, Any]] = {}
        hash_mapping: dict[str, dict[str, Any]] = {}
        for row in eligible_mapping_rows:
            item = dict(row)
            exact_mapping.setdefault(row["onet_task_id"], item)
            hash_mapping.setdefault(row["task_statement_hash"], item)

        tasks_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for task in tasks:
            task["statement_hash"] = md5_statement(task["statement"])
            task["source_weight"] = (
                float(task["importance_score"] * task["frequency_score"])
                if task["weighting_eligible"] else None
            )
            exact = exact_mapping.get(task["task_id"])
            if exact and exact["task_statement_hash"] == task["statement_hash"]:
                task["reuse"] = ("reused_exact_task", exact)
            elif task["statement_hash"] in hash_mapping:
                task["reuse"] = ("reused_task_hash", hash_mapping[task["statement_hash"]])
            else:
                task["reuse"] = None
            tasks_by_code[task["occupation_code"]].append(task)

        # ---------------------------------------------------------------------
        # Completion selection. Identical to Phase 5 except for the stopping
        # condition: continue until the completion target is reached OR the
        # defensibly mappable tasks are exhausted. Ambiguous statements are
        # skipped, never forced, and never contribute coverage.
        # ---------------------------------------------------------------------
        selected_new: list[dict[str, Any]] = []
        insufficient_ids: set[int] = set()
        selection_rank: dict[int, int] = {}
        inherited_coverage: dict[str, float] = {}
        final_coverage: dict[str, float] = {}
        ceiling_coverage: dict[str, float] = {}
        exhausted_below_target: dict[str, float] = {}
        for code, source_tasks in tasks_by_code.items():
            weighted = [task for task in source_tasks if task["source_weight"] is not None]
            total_weight = sum(float(task["source_weight"]) for task in weighted)
            covered_weight = sum(
                float(task["source_weight"]) for task in weighted if task["reuse"] is not None
            )
            inherited_coverage[code] = 100.0 * covered_weight / total_weight if total_weight else 0.0
            missing = sorted(
                (task for task in weighted if task["reuse"] is None),
                key=lambda task: (-float(task["source_weight"]), task["task_id"]),
            )
            # The most coverage this occupation could ever defensibly reach: everything
            # except statements the rubric judges too thin to map.
            mappable_weight = sum(
                float(task["source_weight"]) for task in missing
                if disposition(task["statement"])[0] == "none"
            )
            ceiling_coverage[code] = (
                100.0 * (covered_weight + mappable_weight) / total_weight if total_weight else 0.0
            )
            for rank, task in enumerate(missing, 1):
                if total_weight > 0 and 100.0 * covered_weight / total_weight >= completion_target:
                    break
                selection_rank[task["task_id"]] = rank
                ambiguity, _, _ = disposition(task["statement"])
                if ambiguity != "none":
                    insufficient_ids.add(task["task_id"])
                    continue
                selected_new.append(task)
                covered_weight += float(task["source_weight"])
            final_coverage[code] = 100.0 * covered_weight / total_weight if total_weight else 0.0
            if final_coverage[code] < completion_target:
                exhausted_below_target[code] = final_coverage[code]

        prompt_hash = hashlib.sha256(PROMPT_TEXT.encode()).hexdigest()
        implementation_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        run_id = await connection.fetchval(
            """
            INSERT INTO ai_generated_task_mapping_runs (
              run_version,taxonomy_version_id,rubric_version_id,evidence_policy_version_id,
              provider_name,model_name,model_version,model_snapshot_date,prompt_name,prompt_version,
              prompt_sha256,system_prompt_sha256,inference_configuration,allowed_input_manifest,
              prohibited_input_attestation,status,input_task_count,output_task_count,source_id,
              evidence,provenance,created_by
            ) VALUES ($1,$2,$3,$4,'JobsVsAI','rubric-authored deterministic mapper','phase5b-v1',
              DATE '2026-08-21','Phase 5B coverage-completion score-blind prompt',$5,$6,$6,$7,$8,true,'completed',$9,$9,$10,$11,$12,
              'system:phase5b-completion-mapper') RETURNING id
            """,
            run_version,
            policy["taxonomy_version_id"],
            policy["rubric_version_id"],
            policy["id"],
            PROMPT_VERSION,
            prompt_hash,
            json.dumps({
                "temperature": 0,
                "maximumCapabilities": 6,
                "runtimeExternalModelCalls": 0,
                "estimatedAiTokens": 0,
                "selectionPolicy":
                    "existing_validated_reuse_then_descending_source_weight_until_85_percent_or_exhausted",
                "taskHashReuse": True,
                "implementationHash": implementation_hash,
            }),
            json.dumps({
                "allowed": ["scoring_ready_membership", "onet_task_id", "onet_task_statement",
                            "onet_task_importance_frequency_for_scope_ordering", "taxonomy_definitions",
                            "mapping_rubric", "mvp_evidence_policy"],
                "prohibited": [*FORBIDDEN_INPUTS, "occupation_title", "soc_category", "phase5_scores"],
            }),
            len(selected_new),
            source_id,
            json.dumps([{"promptSha256": prompt_hash, "implementationSha256": implementation_hash}]),
            json.dumps({"phase": "5B", "bounded": True, "scoreBlind": True,
                        "completesMappingRunVersion": "phase5-bounded-mapper-v1-2026q3",
                        "externalAiCalls": 0, "estimatedAiTokens": 0,
                        "public": False, "productionScoreWrites": 0}),
        )

        capability_ids = {
            row["slug"]: row["id"]
            for row in await connection.fetch(
                "SELECT id,slug FROM ai_capability_definitions WHERE taxonomy_version_id=$1",
                policy["taxonomy_version_id"],
            )
        }
        constraint_ids = {
            row["slug"]: row["id"]
            for row in await connection.fetch(
                "SELECT id,slug FROM task_environment_constraint_definitions WHERE environment_taxonomy_version_id=$1",
                policy["environment_taxonomy_version_id"],
            )
        }
        generated: dict[int, int] = {}
        print(
            f"Phase 5B completion: reusing {len(eligible_mapping_rows)} eligible historical rows; "
            f"generating {len(selected_new)} completion mappings",
            flush=True,
        )
        for index, task in enumerate(selected_new, 1):
            ambiguity, mapping_confidence, rationale = disposition(task["statement"])
            if ambiguity != "none":
                raise ValueError("Selected Phase 5B mapping unexpectedly lacks sufficient task evidence")
            mapping_id = await connection.fetchval(
                """
                INSERT INTO ai_generated_task_mappings (
                  mapping_run_id,onet_task_id,mapping_version,task_statement_hash,ambiguity_state,
                  mapping_confidence,initial_validation_status,initial_review_state,rationale,evidence,provenance
                ) VALUES ($1,$2,'phase5b-task-mapping-v1',$3,'none',$4,'self_checked','ai_self_checked',
                  $5,$6,$7) RETURNING id
                """,
                run_id,
                task["task_id"],
                task["statement_hash"],
                mapping_confidence,
                rationale,
                json.dumps([{"source": "onet_task_statement", "statement": task["statement"],
                             "rowHash": task["row_hash"], "sourceVersion": task["source_version"]}]),
                json.dumps({"phase": "5B", "scoreBlind": True, "promptVersion": PROMPT_VERSION,
                            "selectionRank": selection_rank[task["task_id"]],
                            "phase5Decision": base_decisions.get(task["task_id"]),
                            "inferenceBeyondTaskText": False}),
            )
            for requirement in capability_payload(task["statement"]):
                await connection.execute(
                    """
                    INSERT INTO ai_generated_task_capability_requirements (
                      ai_task_mapping_id,capability_definition_id,weight,required_capability_level,
                      confidence,rationale,evidence,provenance
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                    """,
                    mapping_id,
                    capability_ids[requirement["slug"]],
                    requirement["weight"],
                    requirement["level"],
                    requirement["confidence"],
                    f"Explicit task-local terms support {requirement['slug']}; weight is normalized across supported dimensions.",
                    json.dumps([{"matchedTerms": requirement["matches"], "source": "onet_task_statement"}]),
                    json.dumps({"mapperVersion": "phase5b-v1", "inferenceBeyondTaskText": False}),
                )
            for constraint in constraint_payload(task["statement"]):
                await connection.execute(
                    """
                    INSERT INTO ai_generated_task_environment_constraints (
                      ai_task_mapping_id,constraint_definition_id,constraint_level,confidence,
                      rationale,evidence,provenance
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7)
                    """,
                    mapping_id,
                    constraint_ids[constraint["slug"]],
                    constraint["level"],
                    constraint["confidence"],
                    f"Explicit task-local terms support {constraint['slug']}; absent constraints are not imputed.",
                    json.dumps([{"matchedTerms": constraint["matches"], "source": "onet_task_statement"}]),
                    json.dumps({"mapperVersion": "phase5b-v1", "inferenceBeyondTaskText": False}),
                )
            event_id = await connection.fetchval(
                "SELECT validate_ai_generated_task_mapping($1,$2,$3,$4,$5,$6)",
                mapping_id,
                policy["id"],
                "phase5b-mapping-validator-v1",
                "JobsVsAI deterministic MVP validator",
                "v1",
                "system:phase5b-completion-mapper",
            )
            eligible = await connection.fetchval(
                "SELECT scoring_eligible FROM ai_task_mapping_validation_events WHERE id=$1", event_id
            )
            if not eligible:
                raise ValueError(f"Structurally deterministic mapping failed validation for task {task['task_id']}")
            generated[task["task_id"]] = mapping_id
            if index % 1000 == 0:
                print(f"Validated {index}/{len(selected_new)} completion mappings", flush=True)

        scope_rows: list[tuple[Any, ...]] = []
        counts: dict[str, int] = defaultdict(int)
        # How each Phase 5 decision was resolved this pass, so the completion is auditable
        # against the run it completes rather than merely asserted.
        transitions: dict[str, int] = defaultdict(int)
        for task in tasks:
            mapping_id = None
            source_mapping_task_id = None
            mapping_run_id = None
            rank = selection_rank.get(task["task_id"])
            if task["reuse"] is not None:
                decision, mapping = task["reuse"]
                mapping_id = mapping["id"]
                source_mapping_task_id = mapping["onet_task_id"]
                mapping_run_id = mapping["mapping_run_id"]
                reason = (
                    "Existing structurally eligible mapping reused by exact task id and statement hash."
                    if decision == "reused_exact_task"
                    else "Existing structurally eligible mapping reused by exact task-statement hash; no mapping regenerated."
                )
            elif task["task_id"] in generated:
                decision = "generated"
                mapping_id = generated[task["task_id"]]
                source_mapping_task_id = task["task_id"]
                mapping_run_id = run_id
                reason = (
                    "Task was left unmapped by the Phase 5 70% stopping rule; mapped deterministically "
                    "during coverage completion and structurally validated."
                )
            elif not task["weighting_eligible"]:
                decision = "source_weight_ineligible"
                reason = "Source importance or frequency is missing; the task is excluded from weighted coverage without imputation."
            elif task["task_id"] in insufficient_ids:
                decision = "unmapped_insufficient_evidence"
                reason = "Task description is ambiguous or insufficient under the approved rubric; no mapping values were invented."
            else:
                decision = "unmapped_after_gate"
                reason = (
                    "No mapping generated: the occupation had already reached the 85% mapping "
                    "completion target before this task was reached."
                )
            counts[decision] += 1
            transitions[f"{base_decisions.get(task['task_id'], 'absent')}->{decision}"] += 1
            dependency_key = canonical_hash({
                "statementHash": task["statement_hash"],
                "taxonomyVersionId": policy["taxonomy_version_id"],
                "rubricVersionId": policy["rubric_version_id"],
                "evidencePolicyVersionId": policy["id"],
                "mappingId": mapping_id,
            })
            exact = {
                "namespaceVersion": namespace_version,
                "mappingScopeVersion": MAPPING_SCOPE_VERSION,
                "onetTaskId": task["task_id"],
                "scopeDecision": decision,
                "mappingId": mapping_id,
                "sourceMappingTaskId": source_mapping_task_id,
                "sourceWeight": task["source_weight"],
                "selectionRank": rank,
                "dependencyReuseKey": dependency_key,
            }
            evidence = [{
                "source": "onet_task_weighting_and_statement",
                "sourceWeight": task["source_weight"],
                "selectionRank": rank,
                "phase5ScopeDecision": base_decisions.get(task["task_id"]),
                "inheritedOccupationCoverage": round(inherited_coverage[task["occupation_code"]], 6),
                "completedOccupationCoverage": round(final_coverage[task["occupation_code"]], 6),
                "maximumDefensibleCoverage": round(ceiling_coverage[task["occupation_code"]], 6),
                "sourceTaskRowHash": task["row_hash"],
                "sourceVersion": task["source_version"],
            }]
            scope_rows.append((
                namespace_id,
                candidate_by_code[task["occupation_code"]],
                task["task_id"],
                decision,
                mapping_id,
                source_mapping_task_id,
                mapping_run_id,
                task["source_weight"],
                rank,
                reason,
                task["statement_hash"],
                dependency_key,
                json.dumps(evidence),
                canonical_hash(exact),
                source_id,
                json.dumps({"phase": "5B", "bounded": True, "missingEvidenceInvented": False,
                            "targetIsQuota": False, "public": False, "production": False}),
                "system:phase5b-completion-mapper",
            ))
        await connection.executemany(
            """
            INSERT INTO phase5_task_mapping_scope (
              namespace_id,candidate_occupation_id,onet_task_id,scope_decision,ai_task_mapping_id,
              source_mapping_task_id,mapping_run_id,source_weight,selection_rank,selection_reason,
              task_statement_hash,dependency_reuse_key,evidence,input_hash,source_id,provenance,created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
            """,
            scope_rows,
        )
        await transaction.commit()
        elapsed_ms = round((time.perf_counter() - started) * 1000)

        buckets: dict[str, int] = defaultdict(int)
        for value in final_coverage.values():
            buckets[coverage_bucket(value)] += 1
        inherited_buckets: dict[str, int] = defaultdict(int)
        for value in inherited_coverage.values():
            inherited_buckets[coverage_bucket(value)] += 1

        return {
            "namespaceId": namespace_id,
            "namespaceVersion": namespace_version,
            "completes": base_namespace_version,
            "mappingRunId": run_id,
            "mappingRunVersion": run_version,
            "mappingCompletionTarget": completion_target,
            "scoringReadyOccupations": len(profile_rows),
            "sourceTasks": len(tasks),
            "scopeRows": len(scope_rows),
            "newMappings": counts["generated"],
            "reusedExactMappings": counts["reused_exact_task"],
            "reusedHashMappings": counts["reused_task_hash"],
            "insufficientDescriptions": counts["unmapped_insufficient_evidence"],
            "unmappedAfterTarget": counts["unmapped_after_gate"],
            "sourceWeightIneligible": counts["source_weight_ineligible"],
            "phase5DecisionTransitions": dict(sorted(transitions.items())),
            "externalAiCalls": 0,
            "estimatedAiTokens": 0,
            "localComputeMilliseconds": elapsed_ms,
            "populationHash": population_hash,
            "coverageBuckets": {"inherited": dict(inherited_buckets), "completed": dict(buckets)},
            "occupationsExhaustedBelowTarget": len(exhausted_below_target),
            "occupationsBelowLaunchGateAtCeiling": sum(
                value < LAUNCH_COVERAGE_GATE for value in ceiling_coverage.values()
            ),
            "projectedCoverage": {
                "minimum": round(min(final_coverage.values()), 4),
                "maximum": round(max(final_coverage.values()), 4),
                "belowScoringThreshold": sum(
                    value < SCORING_ELIGIBILITY_THRESHOLD for value in final_coverage.values()
                ),
                "belowLaunchGate": sum(
                    value < LAUNCH_COVERAGE_GATE for value in final_coverage.values()
                ),
            },
            "reused": False,
        }
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace-version", default=NAMESPACE_VERSION)
    parser.add_argument("--run-version", default=MAPPING_RUN_VERSION)
    parser.add_argument("--base-namespace-version", default=BASE_NAMESPACE_VERSION)
    parser.add_argument("--completion-target", type=float, default=COMPLETION_TARGET)
    parser.add_argument("--dry-run", action="store_true",
                        help="Classify and report without writing anything.")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps(await dry_run(
            args.namespace_version, args.base_namespace_version, args.completion_target), indent=2))
        return
    print(json.dumps(await generate(
        args.namespace_version, args.run_version,
        args.base_namespace_version, args.completion_target), indent=2))


async def dry_run(
    namespace_version: str, base_namespace_version: str, completion_target: float
) -> dict[str, Any]:
    """Report exactly what a completion pass would do. Writes nothing.

    Answers the questions that must be settled before spending the work: how many tasks
    would be newly mapped, how many are genuinely unmappable, and how many occupations
    still cannot defensibly reach the launch gate afterwards.
    """
    connection = await asyncpg.connect(database_url())
    try:
        base_namespace = await connection.fetchrow(
            "SELECT * FROM phase5_candidate_namespaces WHERE namespace_version=$1",
            base_namespace_version,
        )
        if base_namespace is None:
            raise ValueError(f"Missing base namespace {base_namespace_version}")
        rows = await connection.fetch(
            """
            SELECT scope.onet_task_id,scope.scope_decision,scope.source_weight,
                   candidate.occupation_code,task.statement
            FROM phase5_task_mapping_scope scope
            JOIN phase5_candidate_occupations candidate ON candidate.id=scope.candidate_occupation_id
            JOIN onet_tasks task ON task.task_id=scope.onet_task_id
            WHERE scope.namespace_id=$1
            """,
            base_namespace["id"],
        )
        by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_code[row["occupation_code"]].append(dict(row))

        examined = ambiguous = mappable = 0
        inherited: list[float] = []
        completed: list[float] = []
        ceiling: list[float] = []
        for tasks in by_code.values():
            # A reused mapping can exist on a task with no source weight; weighted coverage
            # is defined by the presence of a weight, not by the scope decision.
            weighted = [task for task in tasks if task["source_weight"] is not None]
            total = sum(float(task["source_weight"]) for task in weighted)
            covered = sum(
                float(task["source_weight"]) for task in weighted
                if task["scope_decision"] in ("generated", "reused_exact_task", "reused_task_hash")
            )
            inherited.append(100.0 * covered / total if total else 0.0)
            gated = sorted(
                (task for task in weighted if task["scope_decision"] == "unmapped_after_gate"),
                key=lambda task: (-float(task["source_weight"]), task["onet_task_id"]),
            )
            examined += len(gated)
            ceiling_weight = covered
            simulated = covered
            for task in gated:
                if disposition(task["statement"])[0] != "none":
                    ambiguous += 1
                    continue
                mappable += 1
                ceiling_weight += float(task["source_weight"])
                if total > 0 and 100.0 * simulated / total < completion_target:
                    simulated += float(task["source_weight"])
            completed.append(100.0 * simulated / total if total else 0.0)
            ceiling.append(100.0 * ceiling_weight / total if total else 0.0)

        def buckets(values: list[float]) -> dict[str, int]:
            out: dict[str, int] = defaultdict(int)
            for value in values:
                out[coverage_bucket(value)] += 1
            return dict(out)

        return {
            "baseNamespace": base_namespace_version,
            "targetNamespace": namespace_version,
            "mappingCompletionTarget": completion_target,
            "occupations": len(by_code),
            "unmappedAfterGateExamined": examined,
            "wouldBeMappable": mappable,
            "wouldRemainAmbiguous": ambiguous,
            "coverageBuckets": {"inherited": buckets(inherited), "projected": buckets(completed)},
            "occupationsReachingLaunchGate": {
                "inherited": sum(value >= LAUNCH_COVERAGE_GATE for value in inherited),
                "projected": sum(value >= LAUNCH_COVERAGE_GATE for value in completed),
                "ceiling": sum(value >= LAUNCH_COVERAGE_GATE for value in ceiling),
            },
            "occupationsThatCannotReachLaunchGate": sum(
                value < LAUNCH_COVERAGE_GATE for value in ceiling
            ),
            "externalAiCalls": 0,
            "persisted": False,
        }
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
