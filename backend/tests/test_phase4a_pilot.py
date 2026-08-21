import json
import os

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from scoring.pilot import automation_feasibility, capability_fit

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@postgres:5432/jobsvsai").replace(
        "postgresql+asyncpg://", "postgresql://", 1,
    )


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


async def test_phase4a_cohort_and_mapping_scope_are_exact() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        cohort = await connection.fetchrow(
            "SELECT * FROM phase4a_pilot_cohorts WHERE cohort_version='phase4a-2026q3-v1'"
        )
        counts = await connection.fetchrow("""
          SELECT count(DISTINCT pilot.occupation_code) occupations,count(DISTINCT task.task_id) source_tasks,
                 count(DISTINCT mapping.id) mappings,
                 count(DISTINCT mapping.id) FILTER (WHERE event.scoring_eligible) eligible,
                 count(DISTINCT mapping.id) FILTER (WHERE NOT event.scoring_eligible) excluded,
                 count(DISTINCT mapping.id) FILTER (WHERE pilot.id IS NULL) outside_cohort
          FROM ai_generated_task_mappings mapping
          JOIN ai_generated_task_mapping_runs run ON run.id=mapping.mapping_run_id
          JOIN onet_tasks task ON task.task_id=mapping.onet_task_id
          LEFT JOIN phase4a_pilot_occupations pilot
            ON pilot.occupation_code=task.occupation_code AND pilot.cohort_id=$1
          JOIN LATERAL (
            SELECT validation.scoring_eligible FROM ai_task_mapping_validation_events validation
            WHERE validation.ai_task_mapping_id=mapping.id
            ORDER BY validation.created_at DESC,validation.id DESC LIMIT 1
          ) event ON true
          WHERE run.run_version='phase4a-pilot-mapper-v1-2026q3'
        """, cohort["id"])
        assert dict(counts) == {
            "occupations": 12,
            "source_tasks": 281,
            "mappings": 281,
            "eligible": 230,
            "excluded": 51,
            "outside_cohort": 0,
        }
        run = await connection.fetchrow(
            "SELECT * FROM ai_generated_task_mapping_runs WHERE id=$1", cohort["mapping_run_id"]
        )
        manifest = _json(run["allowed_input_manifest"])
        assert run["prohibited_input_attestation"] is True
        assert run["provider_name"] == "JobsVsAI"
        assert "frontier_capability_values" in manifest["prohibited"]
        assert "occupation_scores" in manifest["prohibited"]
        assert _json(run["inference_configuration"])["runtimeExternalModelCalls"] == 0
    finally:
        await connection.close()


async def test_capability_fit_and_automation_apply_critical_bottlenecks() -> None:
    fit = capability_fit(
        [{
            "slug": "fine-physical-manipulation", "name": "Fine manipulation", "weight": 1.0,
            "requiredLevel": 90, "mappingConfidence": 85, "rationale": "fixture", "evidence": [{}],
        }],
        {"fine-physical-manipulation": {
            "entryId": 1, "score": 10, "confidence": 62, "evidenceIds": [1],
        }},
        {
            "shortfallExponent": 1.35, "geometricFloor": 1,
            "criticalWeightThreshold": .35, "criticalSecondaryWeightThreshold": .2,
            "criticalRequiredLevelThreshold": 70, "bottleneckMatchThreshold": 75,
            "bottleneckHeadroom": 10,
        },
    )
    assert fit["criticalBottleneckCap"] is not None
    assert fit["score"] <= fit["criticalBottleneckCap"]
    automation = automation_feasibility(
        95,
        [{"slug": "safety-criticality", "level": 90, "confidence": 90, "evidence": [{}]}],
        {
            "capabilityFitWeight": .65, "constraintResistanceWeight": .35,
            "criticalConstraintThreshold": 70,
            "constraintWeights": {"safety-criticality": 1.0},
            "bottleneckCapStrength": {"safety-criticality": .9},
        },
    )
    assert automation["preBottleneckScore"] > automation["score"]
    assert automation["score"] == pytest.approx(19.0)


async def test_every_persisted_phase4a_contribution_reconciles() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        latest = await connection.fetchval("SELECT max(id) FROM phase4a_calculation_runs")
        task_rows = await connection.fetch(
            "SELECT ai_capability_fit,automation_feasibility,augmentation_potential,task_ai_exposure,reconciliation FROM phase4a_task_assessments WHERE calculation_run_id=$1",
            latest,
        )
        occupation_rows = await connection.fetch(
            "SELECT ai_exposure,replacement_risk,weighted_task_coverage,reconciliation FROM phase4a_occupation_scores WHERE calculation_run_id=$1",
            latest,
        )
        assert len(task_rows) == 230
        assert len(occupation_rows) == 12
        assert all(_json(row["reconciliation"])["passed"] for row in task_rows)
        for row in occupation_rows:
            reconciliation = _json(row["reconciliation"])
            assert reconciliation["passed"]
            assert float(row["ai_exposure"]) == pytest.approx(reconciliation["taskContributionTotal"], abs=.001)
            assert float(row["replacement_risk"]) == pytest.approx(
                reconciliation["replacementContributionTotal"], abs=.001
            )
            assert 0 < float(row["weighted_task_coverage"]) <= 100
    finally:
        await connection.close()


async def test_replay_and_formula_only_recompute_reuse_mappings_exactly() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        rows = await connection.fetch("""
          SELECT run_kind,mapping_run_id,dependency_hash,new_ai_mapping_calls,reused_mapping_count,
                 reconciliation_status,replay_matches_previous,task_assessment_count,occupation_score_count
          FROM phase4a_calculation_runs WHERE methodology_phase='4A' ORDER BY id
        """)
        assert [row["run_kind"] for row in rows] == [
            "initial", "deterministic_replay", "formula_only_recompute",
        ]
        assert len({row["mapping_run_id"] for row in rows}) == 1
        assert len({row["dependency_hash"] for row in rows}) == 1
        assert all(row["new_ai_mapping_calls"] == 0 for row in rows)
        assert all(row["reconciliation_status"] == "passed" for row in rows)
        assert all(row["task_assessment_count"] == 230 and row["occupation_score_count"] == 12 for row in rows)
        assert rows[1]["replay_matches_previous"] is True
        assert rows[2]["replay_matches_previous"] is True
        assert rows[1]["reused_mapping_count"] == rows[2]["reused_mapping_count"] == 230
        mismatch = await connection.fetchval("""
          SELECT count(*) FROM (
            SELECT onet_task_id,ai_capability_fit,automation_feasibility,augmentation_potential,
                   task_ai_exposure,confidence,input_hash,count(*) versions
            FROM phase4a_task_assessments WHERE methodology_phase='4A'
            GROUP BY onet_task_id,ai_capability_fit,
              automation_feasibility,augmentation_potential,task_ai_exposure,confidence,input_hash
            HAVING count(*)<>3
          ) differences
        """)
        assert mismatch == 0
    finally:
        await connection.close()


async def test_phase4a_isolated_from_production_and_technical_frontier() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("""
          SELECT
            (SELECT count(*) FROM occupation_scores) production_scores,
            (SELECT count(*) FROM task_ai_scores) legacy_task_scores,
            (SELECT count(*) FROM phase4a_occupation_scores WHERE methodology_phase='4A') phase4a_scores,
            (SELECT count(*) FROM phase4a_task_assessments WHERE methodology_phase='4A') phase4a_assessments,
            (SELECT count(*) FROM phase4a_occupation_scores WHERE methodology_phase='4B') phase4b_scores,
            (SELECT count(*) FROM phase4a_task_assessments WHERE methodology_phase='4B') phase4b_assessments,
            (SELECT count(*) FROM frontier_ai_capability_index_entries entry
              JOIN frontier_ai_capability_index_tracks track ON track.id=entry.track_id
              WHERE track.track_code='technical_frontier') technical_values,
            (SELECT bool_and(track.track_code='commercially_deployable')
              FROM phase4a_calculation_runs run
              JOIN frontier_ai_capability_index_tracks track ON track.id=run.frontier_track_id) commercial_only
        """)
        assert dict(row) == {
            "production_scores": 11,
            "legacy_task_scores": 23,
            "phase4a_scores": 36,
            "phase4a_assessments": 690,
            "phase4b_scores": 48,
            "phase4b_assessments": 920,
            "technical_values": 0,
            "commercial_only": True,
        }
    finally:
        await connection.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


async def test_admin_phase4a_exposes_full_drilldown(client: AsyncClient) -> None:
    auth = (os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "change-me-too"))
    response = await client.get("/api/v1/admin/phase4a", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert len(data["occupations"]) == 12
    assert len(data["tasks"]) == 230
    assert len(data["excluded_tasks"]) == 51
    assert len(data["frontier_evidence"]) == 15
    assert len(data["task_formulas"]) == 6
    assert len(data["occupation_formulas"]) == 2
    task = data["tasks"][0]
    assert task["capability_contributions"]
    assert "frontierEvidenceIds" in task["capability_contributions"][0]
    assert len(task["constraint_contributions"]) == 10
    assert task["exact_inputs"]["frontierTrack"] == "commercially_deployable"
