import os

import asyncpg
import pytest


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@postgres:5432/jobsvsai").replace(
        "postgresql+asyncpg://", "postgresql://", 1,
    )


@pytest.mark.asyncio
async def test_mvp_policy_is_versioned_active_and_does_not_require_human_gold() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("SELECT * FROM mvp_mapping_policy_validation")
        assert row["policy_version"] == "mvp-evidence-policy-v1"
        assert row["status"] == "active"
        assert row["policy_scope"] == "mvp_provisional_scoring"
        assert row["human_gold_required"] is False
        assert float(row["minimum_mapping_confidence"]) == 70
        assert float(row["minimum_dimension_confidence"]) == 60
        assert float(row["minimum_evidenced_dimension_coverage"]) == 1
        # 4 runs / 13,099 mappings since Phase 5B coverage completion added
        # `phase5b-completion-mapper-v1-2026q3` and its 2,347 deterministic mappings.
        assert row["ai_mapping_runs"] == 4
        assert row["ai_task_mappings"] == 13099
        assert await connection.fetchval("SELECT count(*) FROM mapper_acceptance_gate_configs") == 1
        assert await connection.fetchval("SELECT count(*) FROM task_mapping_gold_review_events") == 175
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_structured_ai_mapping_can_become_provisionally_scoring_eligible() -> None:
    connection = await asyncpg.connect(_database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        policy = await connection.fetchrow("""
          SELECT policy.*,rubric.environment_taxonomy_version_id
          FROM task_mapping_evidence_policy_versions policy
          JOIN task_mapping_rubric_versions rubric ON rubric.id=policy.rubric_version_id
          WHERE policy.policy_version='mvp-evidence-policy-v1'
        """)
        run_id = await connection.fetchval("""
          INSERT INTO ai_generated_task_mapping_runs (
            run_version,taxonomy_version_id,rubric_version_id,evidence_policy_version_id,
            provider_name,model_name,model_version,model_snapshot_date,prompt_name,prompt_version,
            prompt_sha256,inference_configuration,allowed_input_manifest,prohibited_input_attestation,
            status,input_task_count,output_task_count,source_id,evidence,provenance,created_by
          ) VALUES ('rollback-ai-run',$1,$2,$3,'Test provider','Test model','test-v1',CURRENT_DATE,
            'Task mapper','prompt-v1',repeat('a',64),'{}','{"allowed":["task_text"]}',true,
            'completed',2,2,$4,'[{"fixture":true}]','{"rollback":true}','test') RETURNING id
        """, policy["taxonomy_version_id"], policy["rubric_version_id"], policy["id"], policy["source_id"])
        mapping_id = await connection.fetchval("""
          INSERT INTO ai_generated_task_mappings (
            mapping_run_id,onet_task_id,mapping_version,task_statement_hash,ambiguity_state,
            mapping_confidence,initial_validation_status,initial_review_state,rationale,evidence,provenance
          ) SELECT $1,task_id,'test-v1',md5(statement),'none',82,'self_checked','ai_self_checked',
            'Task-local evidence supports the structured requirements.','[{"task_phrase":"designs and concepts"}]','{"rollback":true}'
          FROM onet_tasks WHERE task_id=299 RETURNING id
        """, run_id)
        definitions = await connection.fetch("""
          SELECT id,slug FROM ai_capability_definitions
          WHERE taxonomy_version_id=$1 AND slug IN ('visual-content-generation','general-reasoning')
          ORDER BY slug
        """, policy["taxonomy_version_id"])
        for definition, weight in zip(definitions, (.4, .6), strict=True):
            await connection.execute("""
              INSERT INTO ai_generated_task_capability_requirements (
                ai_task_mapping_id,capability_definition_id,weight,required_capability_level,
                confidence,rationale,evidence,provenance
              ) VALUES ($1,$2,$3,70,78,'Direct task phrase supports this requirement.',
                '[{"task_phrase":"task-local evidence"}]','{"rollback":true}')
            """, mapping_id, definition["id"], weight)
        event_id = await connection.fetchval("""
          SELECT validate_ai_generated_task_mapping($1,$2,'test-validator-v1','Test deterministic validator','v1','test')
        """, mapping_id, policy["id"])
        event = await connection.fetchrow("SELECT * FROM ai_task_mapping_validation_events WHERE id=$1", event_id)
        assert event["validation_status"] == "passed"
        assert event["review_state"] == "ai_validated"
        assert event["scoring_eligible"] is True
        assert event["structural_validation_passed"] is True
        assert event["confidence_threshold_passed"] is True
        assert event["evidence_coverage_passed"] is True
        assert float(event["normalized_weight_total"]) == pytest.approx(1)
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_ambiguous_ai_mapping_is_never_scoring_eligible_under_v1_policy() -> None:
    connection = await asyncpg.connect(_database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        policy = await connection.fetchrow("SELECT * FROM task_mapping_evidence_policy_versions LIMIT 1")
        run_id = await connection.fetchval("""
          INSERT INTO ai_generated_task_mapping_runs (
            run_version,taxonomy_version_id,rubric_version_id,evidence_policy_version_id,
            provider_name,model_name,model_version,prompt_name,prompt_version,prompt_sha256,
            inference_configuration,allowed_input_manifest,prohibited_input_attestation,status,
            input_task_count,output_task_count,source_id,created_by
          ) VALUES ('rollback-ambiguous-run',$1,$2,$3,'Test','Test','v1','Mapper','v1',repeat('b',64),
            '{}','{}',true,'completed',1,1,$4,'test') RETURNING id
        """, policy["taxonomy_version_id"], policy["rubric_version_id"], policy["id"], policy["source_id"])
        mapping_id = await connection.fetchval("""
          INSERT INTO ai_generated_task_mappings (
            mapping_run_id,onet_task_id,mapping_version,task_statement_hash,ambiguity_state,
            mapping_confidence,initial_validation_status,initial_review_state,rationale,evidence
          ) SELECT $1,task_id,'v1',md5(statement),'ambiguous_scope',90,'self_checked','ai_self_checked',
            'Scope is unresolved.','[{"task_phrase":"determine standards"}]'
          FROM onet_tasks WHERE task_id=21668 RETURNING id
        """, run_id)
        definition_id = await connection.fetchval("""
          SELECT id FROM ai_capability_definitions WHERE taxonomy_version_id=$1 ORDER BY id LIMIT 1
        """, policy["taxonomy_version_id"])
        await connection.execute("""
          INSERT INTO ai_generated_task_capability_requirements (
            ai_task_mapping_id,capability_definition_id,weight,required_capability_level,
            confidence,rationale,evidence
          ) VALUES ($1,$2,1,70,90,'Provisional requirement.','[{"task_phrase":"determine"}]')
        """, mapping_id, definition_id)
        event_id = await connection.fetchval("""
          SELECT validate_ai_generated_task_mapping($1,$2,'test-ambiguous-v1','Validator','v1','test')
        """, mapping_id, policy["id"])
        event = await connection.fetchrow("SELECT * FROM ai_task_mapping_validation_events WHERE id=$1", event_id)
        assert event["validation_status"] == "failed"
        assert event["ambiguity_policy_passed"] is False
        assert event["scoring_eligible"] is False
        assert "ambiguity_policy_failed" in event["failure_reasons"]
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_frontier_index_has_complete_provisional_commercial_track_and_empty_technical_track() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        index_row = await connection.fetchrow("SELECT * FROM frontier_ai_capability_index_validation")
        assert index_row["index_version"] == "frontier-ai-index-v1"
        assert index_row["status"] == "draft"
        assert index_row["expected_capability_count"] == 15
        assert index_row["assessment_tracks"] == 2
        assert index_row["populated_tracks"] == 1
        assert index_row["capability_values"] == 15
        assert index_row["commercially_deployable_values"] == 15
        assert index_row["technical_frontier_values"] == 0
        assert index_row["provisional_values"] == 15
        assert index_row["evidence_records"] == 15
        assert index_row["index_valid"] is True

        tracks = await connection.fetch("""
          SELECT track_code,status,assessment_date,
            (SELECT count(*) FROM frontier_ai_capability_index_entries WHERE track_id=track.id) values
          FROM frontier_ai_capability_index_tracks track ORDER BY track_code
        """)
        assert [(row["track_code"], row["status"], row["values"]) for row in tracks] == [
            ("commercially_deployable", "provisional", 15),
            ("technical_frontier", "draft", 0),
        ]
        assert tracks[0]["assessment_date"].isoformat() == "2026-08-20"

        expected_scores = {
            "language-comprehension": 96,
            "language-generation": 97,
            "information-retrieval": 95,
            "quantitative-reasoning": 91,
            "general-reasoning": 90,
            "software-code-generation": 96,
            "visual-understanding": 93,
            "visual-content-generation": 96,
            "planning-workflow-execution": 87,
            "tool-computer-operation": 86,
            "interpersonal-social-interaction": 62,
            "persuasion-negotiation": 60,
            "physical-perception": 38,
            "fine-physical-manipulation": 10,
            "mobility-real-world-operation": 12,
        }
        entries = await connection.fetch("""
          SELECT definition.slug,entry.capability_score,entry.confidence,entry.rationale,
                 entry.assessment_status,entry.assessment_date,count(evidence.id) evidence_count,
                 bool_and(evidence.source_tier IS NOT NULL AND evidence.source_type IS NOT NULL
                   AND evidence.benchmark_name<>'' AND evidence.reported_result<>''
                   AND evidence.source_reference LIKE 'http%') evidence_complete
          FROM frontier_ai_capability_index_entries entry
          JOIN ai_capability_definitions definition ON definition.id=entry.capability_definition_id
          JOIN frontier_ai_capability_evidence_records evidence
            ON evidence.track_id=entry.track_id AND evidence.capability_definition_id=entry.capability_definition_id
          GROUP BY definition.slug,entry.id
        """)
        assert {row["slug"]: float(row["capability_score"]) for row in entries} == expected_scores
        assert all(float(row["confidence"]) > 0 and row["rationale"] for row in entries)
        assert all(row["assessment_status"] == "provisional" for row in entries)
        assert all(row["assessment_date"].isoformat() == "2026-08-20" for row in entries)
        assert all(row["evidence_count"] >= 1 and row["evidence_complete"] for row in entries)
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_policy_and_index_do_not_modify_mapping_activation_or_scores() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("""
          SELECT
            (SELECT count(*) FROM ai_generated_task_mappings) persisted_ai_mappings,
            (SELECT count(*) FROM ai_task_mapping_validation_events WHERE scoring_eligible) eligible_ai_mappings,
            (SELECT count(*) FROM frontier_ai_capability_index_entries) frontier_values,
            (SELECT count(*) FROM ai_capability_benchmark_scores) benchmark_scores,
            (SELECT count(*) FROM task_capability_mapping_sets) mapping_sets,
            (SELECT count(*) FROM occupation_scores) occupation_scores,
            (SELECT count(*) FROM task_ai_scores) legacy_task_scores,
            (SELECT count(*) FROM scoring_jobs WHERE status IN ('queued','running')) active_scoring_jobs
        """)
        assert dict(row) == {
            # +2,347 from the Phase 5B completion mapper; the isolation guarantees this
            # test exists for — no legacy scores, no activation, no scoring jobs — are the
            # zero-valued fields below and are unchanged.
            "persisted_ai_mappings": 13099,
            "eligible_ai_mappings": 13007,
            "frontier_values": 15,
            "benchmark_scores": 0,
            "mapping_sets": 3,
            "occupation_scores": 11,
            "legacy_task_scores": 23,
            "active_scoring_jobs": 0,
        }
    finally:
        await connection.close()
