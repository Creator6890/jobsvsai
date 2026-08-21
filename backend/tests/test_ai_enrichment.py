import os

import asyncpg
import pytest


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@postgres:5432/jobsvsai").replace(
        "postgresql+asyncpg://", "postgresql://", 1,
    )


@pytest.mark.asyncio
async def test_taxonomy_v1_is_draft_versioned_and_test_only() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("""
          SELECT taxonomy.version, taxonomy.status,
            count(DISTINCT definition.id) definitions,
            count(DISTINCT mapping_set.id) mapping_sets,
            count(DISTINCT mapping.id) mappings,
            bool_and(mapping_set.is_test_fixture) all_sets_test_only,
            count(DISTINCT benchmark.id) benchmark_snapshots,
            count(DISTINCT assessment.id) assessments
          FROM ai_capability_taxonomy_versions taxonomy
          LEFT JOIN ai_capability_definitions definition ON definition.taxonomy_version_id=taxonomy.id
          LEFT JOIN task_capability_mapping_sets mapping_set ON mapping_set.taxonomy_version_id=taxonomy.id
          LEFT JOIN task_capability_requirement_mappings mapping ON mapping.mapping_set_id=mapping_set.id
          LEFT JOIN ai_capability_benchmark_snapshots benchmark ON benchmark.taxonomy_version_id=taxonomy.id
          LEFT JOIN task_ai_enrichment_assessments assessment ON assessment.taxonomy_version_id=taxonomy.id
          WHERE taxonomy.version='jvs-ai-cap-v1'
          GROUP BY taxonomy.id
        """)
        assert row["version"] == "jvs-ai-cap-v1"
        assert row["status"] == "draft"
        assert row["definitions"] == 15
        assert row["mapping_sets"] == 3
        assert row["mappings"] == 13
        assert row["all_sets_test_only"] is True
        assert row["benchmark_snapshots"] == 0
        assert row["assessments"] == 0
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_mapping_weights_versions_ranges_and_provenance_reconcile() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        rows = await connection.fetch("""
          SELECT mapping_set.id, mapping_set.onet_task_id, taxonomy.version,
            sum(mapping.weight) weight_sum,
            bool_and(definition.taxonomy_version_id=mapping_set.taxonomy_version_id) versions_match,
            bool_and(mapping.weight>0 AND mapping.weight<=1) weights_valid,
            bool_and(mapping.required_capability_level BETWEEN 0 AND 100) levels_valid,
            bool_and(mapping.confidence BETWEEN 0 AND 100) confidence_valid,
            bool_and(jsonb_array_length(mapping.evidence)>0) evidence_present
          FROM task_capability_mapping_sets mapping_set
          JOIN ai_capability_taxonomy_versions taxonomy ON taxonomy.id=mapping_set.taxonomy_version_id
          JOIN task_capability_requirement_mappings mapping ON mapping.mapping_set_id=mapping_set.id
          JOIN ai_capability_definitions definition ON definition.id=mapping.capability_definition_id
          GROUP BY mapping_set.id,taxonomy.version ORDER BY mapping_set.onet_task_id
        """)
        assert len(rows) == 3
        for row in rows:
            assert float(row["weight_sum"]) == pytest.approx(1, abs=0.000001)
            assert row["versions_match"] and row["weights_valid"]
            assert row["levels_valid"] and row["confidence_valid"] and row["evidence_present"]
            assert await connection.fetchval("SELECT validate_task_capability_mapping_set($1)", row["id"])
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_environment_constraints_are_separate_test_fixtures() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("""
          SELECT
            (SELECT count(*) FROM task_environment_constraint_definitions) definitions,
            (SELECT count(*) FROM task_environment_constraint_mappings) mappings,
            (SELECT bool_and(is_test_fixture) FROM task_environment_constraint_mappings) all_test,
            (SELECT bool_and(constraint_level BETWEEN 0 AND 100 AND confidence BETWEEN 0 AND 100)
              FROM task_environment_constraint_mappings) ranges_valid
        """)
        assert dict(row) == {"definitions": 10, "mappings": 7, "all_test": True, "ranges_valid": True}
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_invalid_normalized_mapping_is_rejected_at_commit() -> None:
    connection = await asyncpg.connect(_database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        taxonomy_id, source_id, capability_id = await connection.fetchrow("""
          SELECT taxonomy.id, taxonomy.source_id, definition.id capability_id
          FROM ai_capability_taxonomy_versions taxonomy
          JOIN ai_capability_definitions definition ON definition.taxonomy_version_id=taxonomy.id
          WHERE taxonomy.version='jvs-ai-cap-v1' ORDER BY definition.id LIMIT 1
        """)
        set_id = await connection.fetchval("""
          INSERT INTO task_capability_mapping_sets (
            onet_task_id,taxonomy_version_id,mapping_set_version,mapping_method,
            mapping_method_version,review_state,source_id,is_test_fixture,created_by
          ) VALUES (299,$1,'rollback-invalid-weight','architecture_test_fixture','test','test_validated',$2,true,'test')
          RETURNING id
        """, taxonomy_id, source_id)
        await connection.execute("""
          INSERT INTO task_capability_requirement_mappings (
            mapping_set_id,capability_definition_id,weight,required_capability_level,
            confidence,source_id,created_by
          ) VALUES ($1,$2,.5,50,50,$3,'test')
        """, set_id, capability_id, source_id)
        with pytest.raises(asyncpg.PostgresError, match="weights must sum to 1"):
            await transaction.commit()
    finally:
        if connection.is_in_transaction():
            await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_snapshot_reconciliation_can_validate_without_persisting_scores() -> None:
    connection = await asyncpg.connect(_database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        taxonomy_id, source_id, capability_id = await connection.fetchrow("""
          SELECT taxonomy.id, taxonomy.source_id, definition.id capability_id
          FROM ai_capability_taxonomy_versions taxonomy
          JOIN ai_capability_definitions definition ON definition.taxonomy_version_id=taxonomy.id
          WHERE taxonomy.version='jvs-ai-cap-v1' ORDER BY definition.id LIMIT 1
        """)
        snapshot_id = await connection.fetchval("""
          INSERT INTO ai_capability_benchmark_snapshots (
            taxonomy_version_id,snapshot_version,provider_name,model_name,model_version,
            benchmark_method,benchmark_method_version,observed_at,expected_capability_count,
            review_state,source_id,evidence,provenance,is_test_fixture,created_by
          ) VALUES ($1,'rollback-test','Test provider','Test model','test','architecture_test','v1',
            now(),1,'test_validated',$2,'[{"fixture":true}]','{"rollback":true}',true,'test')
          RETURNING id
        """, taxonomy_id, source_id)
        await connection.execute("""
          INSERT INTO ai_capability_benchmark_scores (
            snapshot_id,capability_definition_id,capability_level,confidence,
            evidence,provenance,source_id,created_by
          ) VALUES ($1,$2,50,60,'[{"fixture":true}]','{"rollback":true}',$3,'test')
        """, snapshot_id, capability_id, source_id)
        assert await connection.fetchval("SELECT validate_benchmark_snapshot($1)", snapshot_id)
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_task_assessment_rejects_mismatched_taxonomy_versions() -> None:
    connection = await asyncpg.connect(_database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        source_id, mapping_set_id = await connection.fetchrow("""
          SELECT taxonomy.source_id, mapping_set.id
          FROM ai_capability_taxonomy_versions taxonomy
          JOIN task_capability_mapping_sets mapping_set ON mapping_set.taxonomy_version_id=taxonomy.id
          WHERE taxonomy.version='jvs-ai-cap-v1' ORDER BY mapping_set.id LIMIT 1
        """)
        second_taxonomy = await connection.fetchval("""
          INSERT INTO ai_capability_taxonomy_versions (
            version,name,description,status,source_id,methodology_version,created_by
          ) VALUES ('rollback-v2','Rollback','Mismatch test','draft',$1,'test','test') RETURNING id
        """, source_id)
        await connection.execute("""
          INSERT INTO task_ai_enrichment_assessments (
            onet_task_id,taxonomy_version_id,capability_mapping_set_id,assessment_version,
            ai_capability_fit,automation_feasibility,augmentation_potential,confidence,
            assessment_method,assessment_method_version,review_state,input_versions,
            source_id,is_test_fixture,created_by
          ) VALUES (299,$1,$2,'rollback',50,50,50,50,'test','v1','test_validated',
            '{"fixture":true}',$3,true,'test')
        """, second_taxonomy, mapping_set_id, source_id)
        with pytest.raises(asyncpg.PostgresError, match="mapping set taxonomy mismatch"):
            await transaction.commit()
    finally:
        if connection.is_in_transaction():
            await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_enrichment_history_is_append_only_and_production_scores_untouched() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        validation = await connection.fetchrow("SELECT * FROM ai_enrichment_validation")
        assert validation["invalid_mapping_sets"] == 0
        assert validation["invalid_snapshots"] == 0
        assert validation["task_assessments"] == 0
        assert validation["benchmark_scores"] == 0
        assert validation["production_score_rows"] == 11
        assert validation["legacy_task_ai_score_rows"] == 23
        transaction = connection.transaction()
        await transaction.start()
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await connection.execute("UPDATE task_capability_mapping_sets SET review_state='reviewed' WHERE id=(SELECT min(id) FROM task_capability_mapping_sets)")
        await transaction.rollback()
    finally:
        await connection.close()
