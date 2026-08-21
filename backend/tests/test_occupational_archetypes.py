import json
import os

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.asyncio(loop_scope="session")


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@postgres:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


async def test_archetype_model_is_deterministic_source_based_and_disabled() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        flag = await connection.fetchrow(
            "SELECT * FROM scoring_enrichment_feature_flags WHERE flag_key='occupational_archetype_layer'"
        )
        assert flag["enabled"] is False
        assert flag["production_allowed"] is False
        model = await connection.fetchrow(
            "SELECT * FROM occupational_archetype_model_versions WHERE model_version='occupational-archetype-v1-draft-2026q3'"
        )
        assert model["cluster_count"] == 28
        assert model["source_version"] == "O*NET 30.3"
        assert model["algorithm"] == "deterministic-farthest-point-kmeans-v1"
        feature_schema = decoded(model["feature_schema"])
        assert feature_schema["featureCount"] == 231
        assert feature_schema["excludes"] == ["SOC", "title", "industry"]
        assert feature_schema["minimumFeatureCompleteness"] == 65
        counts = await connection.fetchrow("""
          SELECT (SELECT count(*) FROM occupational_archetype_definitions
                   WHERE model_version_id=$1) definitions,
                 (SELECT count(*) FROM occupation_archetype_memberships
                   WHERE model_version_id=$1 AND membership_role='primary') primary_memberships,
                 (SELECT count(*) FROM occupation_archetype_memberships
                   WHERE model_version_id=$1 AND membership_role='secondary') secondary_memberships,
                 (SELECT count(*) FROM archetype_structural_baselines baseline
                   JOIN occupational_archetype_definitions definition
                     ON definition.id=baseline.archetype_definition_id
                   WHERE definition.model_version_id=$1) baselines
        """, model["id"])
        assert dict(counts) == {
            "definitions": 28, "primary_memberships": 894,
            "secondary_memberships": 844, "baselines": 308,
        }
    finally:
        await connection.close()


async def test_phase4c_overlay_has_exact_provenance_and_reconciles() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        model_id = await connection.fetchval(
            "SELECT id FROM occupational_archetype_model_versions WHERE model_version='occupational-archetype-v1-draft-2026q3'"
        )
        cohort_memberships = await connection.fetchval("""
          SELECT count(*) FROM phase4c_validation_occupations validation
          JOIN occupation_archetype_memberships membership
            ON membership.occupation_code=validation.occupation_code
           AND membership.model_version_id=$1 AND membership.membership_role='primary'
          WHERE validation.cohort_id=(SELECT id FROM phase4c_validation_cohorts
                                      WHERE cohort_version='phase4c-2026q3-v1')
        """, model_id)
        assert cohort_memberships == 25
        rows = await connection.fetch(
            "SELECT * FROM occupation_archetype_proxy_adjustments WHERE model_version_id=$1", model_id
        )
        assert len(rows) == 275
        assert all(row["occupation_source_evidence"] is not None for row in rows)
        assert all(decoded(row["reconciliation"])["passed"] for row in rows)
        for row in rows:
            inputs = decoded(row["exact_inputs"])
            assert inputs["modelVersion"] == "occupational-archetype-v1-draft-2026q3"
            assert inputs["sourceEvidence"]["evidence"]
            expected = (
                float(row["archetype_baseline"]) * float(row["prior_weight"])
                + float(row["occupation_source_evidence"]) * (1 - float(row["prior_weight"]))
            )
            assert abs(float(row["resulting_proxy"]) - expected) < .001
            assert abs(
                float(row["resulting_proxy"])
                - (float(row["archetype_baseline"]) + float(row["occupation_adjustment"]))
            ) < .001
    finally:
        await connection.close()


async def test_archetype_pilot_replays_and_preserves_phase4c_boundaries() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        runs = await connection.fetch(
            "SELECT * FROM archetype_phase4c_validation_runs ORDER BY id"
        )
        assert [row["run_kind"] for row in runs] == ["archetype_pilot", "deterministic_replay"]
        assert runs[1]["replay_matches_previous"] is True
        assert all(row["occupation_count"] == 25 for row in runs)
        assert all(row["task_assessment_count"] == 407 for row in runs)
        assert all(row["external_ai_calls"] == 0 for row in runs)
        assert all(row["regenerated_mapping_count"] == 0 for row in runs)
        latest_id = runs[-1]["id"]
        blocked = await connection.fetch("""
          SELECT validation.occupation_code
          FROM archetype_phase4c_occupation_scores score
          JOIN phase4c_validation_occupations validation ON validation.id=score.validation_occupation_id
          WHERE score.validation_run_id=$1 AND NOT score.scale_eligible
          ORDER BY validation.occupation_code
        """, latest_id)
        assert [row["occupation_code"] for row in blocked] == [
            "11-2022.00", "27-1024.00", "39-5012.00", "41-2031.00"
        ]
        coverage_changes = await connection.fetchval("""
          SELECT count(*) FROM archetype_phase4c_occupation_scores score
          JOIN phase4c_occupation_scores baseline ON baseline.id=score.baseline_phase4c_score_id
          WHERE score.validation_run_id=$1
            AND (score.weighted_task_coverage<>baseline.weighted_task_coverage
              OR score.coverage_gate_status<>baseline.coverage_gate_status)
        """, latest_id)
        assert coverage_changes == 0
        validation = await connection.fetchrow("""
          SELECT count(*) checks,
                 count(*) FILTER (WHERE improved) improved,
                 count(*) FILTER (WHERE regressed) regressed,
                 count(*) FILTER (WHERE archetype_outcome='failure') failures,
                 count(*) FILTER (WHERE archetype_outcome='warning') warnings
          FROM archetype_proxy_validation_results WHERE validation_run_id=$1
        """, latest_id)
        assert dict(validation) == {
            "checks": 70, "improved": 0, "regressed": 0, "failures": 13, "warnings": 2
        }
        production = await connection.fetchrow("""
          SELECT (SELECT count(*) FROM occupation_scores) occupation_rows,
                 (SELECT count(*) FROM task_ai_scores) task_rows
        """)
        assert dict(production) == {"occupation_rows": 11, "task_rows": 23}
    finally:
        await connection.close()


async def test_admin_archetype_inspector_is_complete_and_read_only() -> None:
    auth = (os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "change-me-too"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/archetypes", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["feature_flag"]["enabled"] is False
    assert data["feature_flag"]["production_allowed"] is False
    assert len(data["archetypes"]) == 28
    assert len(data["occupations"]) == 25
    assert len(data["validations"]) == 70
    assert data["runs"][0]["replay_matches_previous"] is True
    assert data["isolation"]["runs_with_ai_calls"] == 0
    assert data["isolation"]["runs_with_regenerated_mappings"] == 0
    assert all(len(row["adjustments"]) == 11 for row in data["occupations"])
