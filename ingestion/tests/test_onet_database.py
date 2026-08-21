import os
import json

import asyncpg
import pytest

from ingestion.onet_import import RawRecord, _stage_source_versions


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@postgres:5432/jobsvsai").replace(
        "postgresql+asyncpg://", "postgresql://", 1,
    )


@pytest.mark.asyncio
async def test_source_versions_are_idempotent_and_update_safe() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        async with connection.transaction():
            source_id = await connection.fetchval("""
              INSERT INTO data_sources (name, version) VALUES ('O*NET transactional update probe', 'test')
              RETURNING id
            """)
            run_id = await connection.fetchval("""
              INSERT INTO import_runs (source_id, status, scope, source_version)
              VALUES ($1, 'running', 'test', 'test') RETURNING id
            """, source_id)
            original = RawRecord("occupation_data", "99-9999.00", "test://occupation", "a" * 64, {"Title": "Original"})
            changed = RawRecord("occupation_data", "99-9999.00", "test://occupation", "b" * 64, {"Title": "Changed"})

            _, first_writes = await _stage_source_versions(connection, source_id, run_id, "test", [original])
            _, replay_writes = await _stage_source_versions(connection, source_id, run_id, "test", [original])
            _, update_writes = await _stage_source_versions(connection, source_id, run_id, "test", [changed])

            current = await connection.fetchrow("""
              SELECT row_hash, payload FROM source_record_versions
              WHERE source_id=$1 AND dataset_name='occupation_data'
                AND natural_key='99-9999.00' AND is_current
            """, source_id)
            history_count = await connection.fetchval(
                "SELECT count(*) FROM source_record_versions WHERE source_id=$1", source_id,
            )
            assert (first_writes, replay_writes, update_writes) == (1, 0, 1)
            assert current["row_hash"].strip() == "b" * 64
            assert json.loads(current["payload"])["Title"] == "Changed"
            assert history_count == 2
            # The surrounding transaction always rolls the probe back.
            raise RollbackProbe
    except RollbackProbe:
        pass
    finally:
        await connection.close()


class RollbackProbe(Exception):
    pass


@pytest.mark.asyncio
async def test_representative_subset_schema_integrity() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        counts = await connection.fetchrow("""
          SELECT
            (SELECT count(*) FROM onet_occupations WHERE is_current AND source_version='30.3') occupations,
            (SELECT count(*) FROM onet_scales WHERE is_current) scales,
            (SELECT count(*) FROM source_occupation_titles WHERE is_current) titles,
            (SELECT count(*) FROM source_taxonomies WHERE is_current) taxonomies,
            (SELECT count(*) FROM source_occupation_successions WHERE is_current) successions,
            (SELECT count(*) FROM onet_occupation_domain_coverage) coverage_rows,
            (SELECT count(*) FROM onet_tasks WHERE is_current AND weighting_eligible
              AND (importance_score IS NULL OR frequency_score IS NULL)) invalid_eligible_tasks,
            (SELECT count(*) FROM onet_tasks WHERE is_current AND NOT weighting_eligible
              AND rating_status='complete') invalid_ineligible_tasks,
            (SELECT count(*) FROM source_occupation_successions WHERE allocation_weight IS NOT NULL) invented_weights,
            (SELECT count(*) FROM onet_related_occupations
              WHERE relation_namespace <> 'onet_relatedness') leaked_relationships,
            (SELECT count(*) FROM onet_task_ratings rating LEFT JOIN onet_scales scale USING (scale_id)
              WHERE rating.is_current AND scale.scale_id IS NULL) orphan_task_scales,
            (SELECT count(*) FROM onet_element_ratings rating LEFT JOIN onet_scales scale USING (scale_id)
              WHERE rating.is_current AND scale.scale_id IS NULL) orphan_element_scales,
            (SELECT count(*) FROM source_occupation_titles title
              LEFT JOIN source_record_versions source ON source.id=title.source_record_id
              WHERE title.is_current AND source.id IS NULL) unprovenanced_titles
        """)
        assert counts["occupations"] >= 31
        assert counts["scales"] > 0
        assert counts["titles"] > 31
        assert counts["taxonomies"] == 3
        assert counts["successions"] > 0
        assert counts["coverage_rows"] == counts["occupations"] * 10
        for key in (
            "invalid_eligible_tasks", "invalid_ineligible_tasks", "invented_weights",
            "leaked_relationships", "orphan_task_scales", "orphan_element_scales", "unprovenanced_titles",
        ):
            assert counts[key] == 0

        missing = await connection.fetch("""
          SELECT occupation_code, domain, coverage_status, issues
          FROM onet_occupation_domain_coverage
          WHERE coverage_status IN ('partial','missing')
          ORDER BY occupation_code, domain
        """)
        assert missing
        assert all(issue["issues"] for issue in missing)
        assert all(
            all(item.get("imputed") is False for item in json.loads(issue["issues"]))
            for issue in missing
        )
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_promotion_policy_separates_import_scoring_and_publication() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("""
          SELECT
            (SELECT count(*) FROM onet_occupations WHERE is_current) source_occupations,
            (SELECT count(*) FROM occupation_promotion_profiles) profiles,
            (SELECT count(*) FROM occupation_promotion_profiles WHERE ingestion_eligible) ingestion_eligible,
            (SELECT count(*) FROM occupation_promotion_profiles WHERE public_activation_eligible) public_ready,
            (SELECT count(*) FROM occupation_publications WHERE activation_status='public') source_public,
            (SELECT count(*) FROM occupation_identity_resolutions WHERE allocation_weight IS NOT NULL) invented_weights,
            (SELECT count(*) FROM occupation_identity_resolutions WHERE resolution_type='complex_manual'
              AND (automatic_allowed OR review_status<>'pending')) invalid_complex,
            (SELECT count(*) FROM onet_element_ratings WHERE element_type='skill'
              AND is_current AND skill_classification IS NULL) unclassified_skill_rows,
            (SELECT count(*) FROM source_attribution_requirements
              WHERE publication_gate='before_public_activation') attribution_gates
        """)
        assert row["profiles"] == row["source_occupations"]
        assert row["ingestion_eligible"] == row["source_occupations"]
        assert row["public_ready"] == 0
        assert row["source_public"] == 0
        assert row["invented_weights"] == 0
        assert row["invalid_complex"] == 0
        assert row["unclassified_skill_rows"] == 0
        assert row["attribution_gates"] >= 1
    finally:
        await connection.close()
