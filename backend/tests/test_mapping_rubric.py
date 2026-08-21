import json
import os

import asyncpg
import pytest


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@postgres:5432/jobsvsai").replace(
        "postgresql+asyncpg://", "postgresql://", 1,
    )


@pytest.mark.asyncio
async def test_rubric_has_complete_anchored_scales_and_thresholds() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("SELECT * FROM task_mapping_rubric_validation")
        thresholds = await connection.fetchrow("""
          SELECT rubric.status,rubric.minimum_meaningful_weight,rubric.dominant_weight_threshold,
            rubric.maximum_capabilities_per_task,rubric.minimum_meaningful_requirement_level,
            rubric.minimum_meaningful_constraint_level,rubric.ambiguity_confidence_ceiling,
            capability.status capability_status,environment.status environment_status
          FROM task_mapping_rubric_versions rubric
          JOIN ai_capability_taxonomy_versions capability ON capability.id=rubric.capability_taxonomy_version_id
          JOIN task_environment_taxonomy_versions environment ON environment.id=rubric.environment_taxonomy_version_id
          WHERE rubric.version='jvs-task-capability-rubric-v1'
        """)
        assert row["rubric_valid"] is True
        assert row["capability_anchors"] == 75
        assert row["constraint_anchors"] == 50
        assert row["confidence_states"] == 5
        assert thresholds["status"] == "review"
        assert thresholds["capability_status"] == thresholds["environment_status"] == "draft"
        assert float(thresholds["minimum_meaningful_weight"]) == pytest.approx(.05)
        assert float(thresholds["dominant_weight_threshold"]) == pytest.approx(.40)
        assert thresholds["maximum_capabilities_per_task"] == 6
        assert float(thresholds["minimum_meaningful_requirement_level"]) == 10
        assert float(thresholds["minimum_meaningful_constraint_level"]) == 10
        assert float(thresholds["ambiguity_confidence_ceiling"]) == 49
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_gold_set_is_small_versioned_reviewed_and_reconciled() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("""
          SELECT dataset.id,dataset.dataset_version,dataset.status,dataset.is_test_fixture,
            dataset.reviewed_by,dataset.reviewed_at,count(DISTINCT item.id) items,
            count(DISTINCT item.id) FILTER (WHERE item.disposition='mappable') mappable,
            count(DISTINCT item.id) FILTER (WHERE item.disposition='ambiguous_scope') ambiguous,
            count(DISTINCT requirement.id) requirements,count(DISTINCT constraint_mapping.id) constraints,
            bool_and(jsonb_array_length(item.reviewer_provenance)>=2) reviewer_provenance_complete
          FROM task_capability_gold_datasets dataset
          JOIN task_capability_gold_items item ON item.gold_dataset_id=dataset.id
          LEFT JOIN gold_task_capability_requirements requirement ON requirement.gold_item_id=item.id
          LEFT JOIN gold_task_environment_constraints constraint_mapping ON constraint_mapping.gold_item_id=item.id
          WHERE dataset.dataset_version='gold-v1-representative-test'
          GROUP BY dataset.id
        """)
        assert row["status"] == "test_validated" and row["is_test_fixture"] is True
        assert row["reviewed_by"] and row["reviewed_at"]
        assert row["items"] == 4 and row["mappable"] == 3 and row["ambiguous"] == 1
        assert row["requirements"] == 13 and row["constraints"] == 7
        assert row["reviewer_provenance_complete"] is True
        assert await connection.fetchval("SELECT validate_task_capability_gold_dataset($1)", row["id"])
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_candidate_fixtures_reconcile_exactly_with_gold() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        dataset_id = await connection.fetchval(
            "SELECT id FROM task_capability_gold_datasets WHERE dataset_version='gold-v1-representative-test'"
        )
        candidate_ids = await connection.fetch("""
          SELECT mapping_set.id FROM task_capability_mapping_sets mapping_set
          JOIN task_capability_gold_items item ON item.onet_task_id=mapping_set.onet_task_id
          WHERE item.gold_dataset_id=$1 AND item.disposition='mappable' AND mapping_set.is_test_fixture
          ORDER BY mapping_set.onet_task_id
        """, dataset_id)
        assert len(candidate_ids) == 3
        for candidate in candidate_ids:
            report = json.loads(await connection.fetchval(
                "SELECT compare_task_mapping_to_gold($1,$2)::text", candidate["id"], dataset_id,
            ))
            summary = report["summary"]
            assert float(summary["meanAbsoluteWeightDeviation"]) == 0
            assert float(summary["meanAbsoluteLevelDeviation"]) == 0
            assert float(summary["meanAbsoluteConstraintDeviation"]) == 0
            assert summary["missingCapabilities"] == summary["extraCapabilities"] == 0
            assert summary["thresholdViolations"] == 0
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_comparison_reports_weight_level_and_confidence_deviations() -> None:
    connection = await asyncpg.connect(_database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        original = await connection.fetchrow("""
          SELECT mapping_set.* FROM task_capability_mapping_sets mapping_set
          WHERE mapping_set.onet_task_id=299 ORDER BY mapping_set.id LIMIT 1
        """)
        candidate_id = await connection.fetchval("""
          INSERT INTO task_capability_mapping_sets (
            onet_task_id,taxonomy_version_id,mapping_set_version,mapping_method,
            mapping_method_version,review_state,source_id,evidence,provenance,is_test_fixture,created_by
          ) VALUES ($1,$2,'rollback-rubric-deviation','human_expert','rubric-test','draft',$3,
            '[{"fixture":true}]','{"rollback":true}',true,'test') RETURNING id
        """, original["onet_task_id"], original["taxonomy_version_id"], original["source_id"])
        await connection.execute("""
          INSERT INTO task_capability_requirement_mappings (
            mapping_set_id,capability_definition_id,weight,required_capability_level,confidence,
            rationale,evidence,provenance,source_id,created_by
          )
          SELECT $1,capability_definition_id,
            CASE WHEN weight=.45 THEN .35 WHEN weight=.15 THEN .25 ELSE weight END,
            CASE WHEN weight=.45 THEN required_capability_level-20 ELSE required_capability_level END,
            CASE WHEN weight=.45 THEN confidence-25 ELSE confidence END,
            rationale,evidence,'{"rollback":true}',source_id,'test'
          FROM task_capability_requirement_mappings WHERE mapping_set_id=$2
        """, candidate_id, original["id"])
        dataset_id = await connection.fetchval("SELECT id FROM task_capability_gold_datasets LIMIT 1")
        report = json.loads(await connection.fetchval(
            "SELECT compare_task_mapping_to_gold($1,$2)::text", candidate_id, dataset_id,
        ))
        assert float(report["summary"]["meanAbsoluteWeightDeviation"]) > 0
        assert float(report["summary"]["meanAbsoluteLevelDeviation"]) > 0
        assert float(report["summary"]["meanAbsoluteCapabilityConfidenceDeviation"]) > 0
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_ambiguous_gold_item_cannot_contain_invented_mappings() -> None:
    connection = await asyncpg.connect(_database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        rubric = await connection.fetchrow("SELECT * FROM task_mapping_rubric_versions LIMIT 1")
        dataset_id = await connection.fetchval("""
          INSERT INTO task_capability_gold_datasets (
            rubric_version_id,dataset_version,name,description,status,expected_task_count,
            source_id,evidence,provenance,is_test_fixture,created_by,reviewed_by,reviewed_at
          ) VALUES ($1,'rollback-invalid-ambiguous','Rollback','Test','test_validated',1,$2,
            '[{"fixture":true}]','{"rollback":true}',true,'test','reviewer-a + reviewer-b',now()) RETURNING id
        """, rubric["id"], rubric["source_id"])
        gold_item_id = await connection.fetchval("""
          INSERT INTO task_capability_gold_items (
            gold_dataset_id,onet_task_id,disposition,task_statement_hash,disposition_rationale,
            reviewer_provenance,evidence,provenance,created_by,reviewed_at
          ) SELECT $1,21668,'ambiguous_scope',md5(statement),'Ambiguous fixture',
            '[{"reviewer":"a"},{"reviewer":"b"}]','[]','{"rollback":true}','test',now()
          FROM onet_tasks WHERE task_id=21668 RETURNING id
        """, dataset_id)
        definition_id = await connection.fetchval("SELECT id FROM ai_capability_definitions ORDER BY id LIMIT 1")
        state_id = await connection.fetchval("SELECT id FROM mapping_confidence_states WHERE code='low'")
        await connection.execute("""
          INSERT INTO gold_task_capability_requirements (
            gold_item_id,capability_definition_id,weight,required_capability_level,confidence,
            confidence_state_id,rationale,source_id,created_by
          ) VALUES ($1,$2,1,50,40,$3,'Invented value',$4,'test')
        """, gold_item_id, definition_id, state_id, rubric["source_id"])
        with pytest.raises(asyncpg.PostgresError, match="invalid task items"):
            await transaction.commit()
    finally:
        if connection.is_in_transaction():
            await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_rubric_infrastructure_is_score_and_benchmark_neutral() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("""
          SELECT
            (SELECT count(*) FROM ai_capability_taxonomy_versions WHERE status='active') active_taxonomies,
            (SELECT count(*) FROM ai_capability_benchmark_snapshots) snapshots,
            (SELECT count(*) FROM ai_capability_benchmark_scores) benchmark_scores,
            (SELECT count(*) FROM task_ai_enrichment_assessments) assessments,
            (SELECT count(*) FROM occupation_scores) occupation_scores,
            (SELECT count(*) FROM task_ai_scores) legacy_task_scores
        """)
        assert dict(row) == {
            "active_taxonomies": 0,
            "snapshots": 0,
            "benchmark_scores": 0,
            "assessments": 0,
            "occupation_scores": 11,
            "legacy_task_scores": 23,
        }
    finally:
        await connection.close()
