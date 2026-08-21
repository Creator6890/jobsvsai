import json
import os

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@postgres:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


async def test_phase4c_cohort_is_targeted_and_preserves_phase4a() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        cohort = await connection.fetchrow(
            "SELECT * FROM phase4c_validation_cohorts WHERE cohort_version='phase4c-2026q3-v1'"
        )
        rows = await connection.fetch(
            "SELECT occupation_code,cohort_role FROM phase4c_validation_occupations WHERE cohort_id=$1 ORDER BY cohort_order",
            cohort["id"],
        )
        assert len(rows) == 25
        assert sum(row["cohort_role"] == "retained_phase4a" for row in rows) == 12
        assert sum(row["cohort_role"] == "added_validation" for row in rows) == 13
        assert [row["occupation_code"] for row in rows[12:]] == [
            "11-1021.00", "13-2052.00", "15-1212.00", "17-2051.00", "21-1022.00",
            "25-2021.00", "27-3042.00", "29-1141.00", "33-3051.00", "39-5012.00",
            "41-2031.00", "51-4041.00", "53-3032.00",
        ]
        policy = _json(cohort["scope_policy"])
        assert policy["fullCorpusScoringAllowed"] is False
        assert policy["coverageGate"] == 70
        assert policy["missingEvidencePolicy"] == "never_invent_never_impute"
    finally:
        await connection.close()


async def test_phase4c_mapping_scope_reuses_existing_and_generates_only_minimum() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        counts = await connection.fetchrow("""
          SELECT count(*) scope_rows,
                 count(*) FILTER (WHERE scope_decision='reused') reused,
                 count(*) FILTER (WHERE scope_decision='generated') generated,
                 count(*) FILTER (WHERE scope_decision='unmapped_insufficient_evidence') insufficient,
                 count(*) FILTER (WHERE scope_decision='unmapped_after_gate') after_gate,
                 count(*) FILTER (WHERE scope_decision='source_weight_ineligible') source_ineligible
          FROM phase4c_task_mapping_scope
        """)
        assert dict(counts) == {
            "scope_rows": 577, "reused": 281, "generated": 177,
            "insufficient": 41, "after_gate": 78, "source_ineligible": 0,
        }
        run = await connection.fetchrow("""
          SELECT run.* FROM ai_generated_task_mapping_runs run
          WHERE run.run_version='phase4c-targeted-mapper-v1-2026q3'
        """)
        assert run["input_task_count"] == run["output_task_count"] == 218
        assert run["prohibited_input_attestation"] is True
        config = _json(run["inference_configuration"])
        assert config["runtimeExternalModelCalls"] == 0
        assert config["selectionPolicy"] == "descending_source_weight_until_70_percent_validated_coverage"
        manifest = _json(run["allowed_input_manifest"])
        assert "occupation_scores" in manifest["prohibited"]
        assert "frontier_capability_values" in manifest["prohibited"]

        coverage = await connection.fetch("""
          SELECT occupation.occupation_code,
                 100.0*sum(scope.source_weight) FILTER (WHERE latest.scoring_eligible)
                   /sum(scope.source_weight) coverage,
                 count(*) FILTER (WHERE scope.scope_decision='unmapped_after_gate') after_gate,
                 count(*) tasks
          FROM phase4c_validation_occupations occupation
          JOIN phase4c_task_mapping_scope scope ON scope.validation_occupation_id=occupation.id
          LEFT JOIN LATERAL (
            SELECT event.scoring_eligible FROM ai_task_mapping_validation_events event
            WHERE event.ai_task_mapping_id=scope.ai_task_mapping_id
            ORDER BY event.created_at DESC,event.id DESC LIMIT 1
          ) latest ON true
          WHERE occupation.cohort_role='added_validation'
          GROUP BY occupation.id,occupation.occupation_code ORDER BY occupation.occupation_code
        """)
        below = {row["occupation_code"] for row in coverage if float(row["coverage"] or 0) < 70}
        assert below == {"39-5012.00", "41-2031.00"}
        assert all(row["after_gate"] == 0 for row in coverage if row["occupation_code"] in below)
        assert all(row["after_gate"] > 0 for row in coverage if row["occupation_code"] not in below)
    finally:
        await connection.close()


async def test_phase4c_scores_reconcile_replay_and_retain_phase4b_exactly() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        runs = await connection.fetch(
            "SELECT * FROM phase4c_calculation_runs ORDER BY id"
        )
        assert [row["run_kind"] for row in runs] == ["targeted_validation", "deterministic_replay"]
        assert all(row["occupation_score_count"] == 25 for row in runs)
        assert all(row["task_assessment_count"] == 407 for row in runs)
        assert all(row["new_mapping_count"] == 218 for row in runs)
        assert all(row["reused_mapping_count"] == 281 for row in runs)
        assert all(row["external_ai_calls"] == 0 for row in runs)
        assert all(row["reconciliation_status"] == "passed" for row in runs)
        assert runs[1]["replay_matches_previous"] is True
        continuity = _json(runs[0]["provenance"])["continuity"]
        assert continuity == {"checkedOccupations": 12, "mismatches": [], "passed": True}

        task_bad = await connection.fetchval("""
          SELECT count(*) FROM phase4c_task_assessments
          WHERE NOT (reconciliation->>'passed')::boolean
        """)
        occupation_bad = await connection.fetchval("""
          SELECT count(*) FROM phase4c_occupation_scores
          WHERE NOT (reconciliation->>'passed')::boolean
        """)
        assert task_bad == occupation_bad == 0
        mismatch = await connection.fetchval("""
          WITH first AS (
            SELECT assessment.* FROM phase4c_task_assessments assessment
            WHERE calculation_run_id=$1
          ), replay AS (
            SELECT assessment.* FROM phase4c_task_assessments assessment
            WHERE calculation_run_id=$2
          )
          SELECT count(*) FROM first FULL JOIN replay USING (onet_task_id)
          WHERE first.input_hash IS DISTINCT FROM replay.input_hash
             OR first.task_ai_exposure IS DISTINCT FROM replay.task_ai_exposure
             OR first.automation_feasibility IS DISTINCT FROM replay.automation_feasibility
        """, runs[0]["id"], runs[1]["id"])
        assert mismatch == 0
    finally:
        await connection.close()


async def test_phase4c_proxy_directionality_and_provenance_are_explicit() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        snapshots = await connection.fetch("SELECT * FROM phase4c_proxy_snapshots ORDER BY id")
        assert len(snapshots) == 25
        assert all(_json(row["reconciliation"])["passed"] for row in snapshots)
        for row in snapshots:
            inputs = _json(row["exact_inputs"])
            assert inputs["methodologyPhase"] == "4C"
            assert inputs["sourceRatings"]
            assert inputs["sourcePolicy"]["missingRatingPolicy"] == (
                "exclude_and_renormalize_with_confidence_penalty"
            )
        latest_run = await connection.fetchval("SELECT max(id) FROM phase4c_calculation_runs")
        result_counts = await connection.fetchrow("""
          SELECT count(*) results,count(*) FILTER (WHERE passed) passed,
                 count(*) FILTER (WHERE severity='warning') warnings,
                 count(*) FILTER (WHERE severity='failure') failures
          FROM phase4c_proxy_validation_results WHERE calculation_run_id=$1
        """, latest_run)
        assert dict(result_counts) == {"results": 24, "passed": 22, "warnings": 2, "failures": 0}
        warnings = await connection.fetch("""
          SELECT expectation.proxy_metric,higher.occupation_code higher_code,
                 lower.occupation_code lower_code,result.observed_delta
          FROM phase4c_proxy_validation_results result
          JOIN phase4c_proxy_pairwise_expectations expectation ON expectation.id=result.expectation_id
          JOIN phase4c_validation_occupations higher ON higher.id=expectation.higher_occupation_id
          JOIN phase4c_validation_occupations lower ON lower.id=expectation.lower_occupation_id
          WHERE result.calculation_run_id=$1 AND result.severity='warning'
          ORDER BY expectation.proxy_metric
        """, latest_run)
        assert [(row["proxy_metric"], row["higher_code"], row["lower_code"]) for row in warnings] == [
            ("adoption-pressure", "27-3042.00", "51-4041.00"),
            ("consequence-severity", "29-1141.00", "39-5012.00"),
        ]
        assert all(float(row["observed_delta"]) > 0 for row in warnings)
    finally:
        await connection.close()


async def test_phase4c_coverage_gate_blocks_without_forcing_scores() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        latest_run = await connection.fetchval("SELECT max(id) FROM phase4c_calculation_runs")
        rows = await connection.fetch("""
          SELECT occupation.occupation_code,score.weighted_task_coverage,score.coverage_gate_status,
                 score.confidence_penalty,score.scale_eligible
          FROM phase4c_occupation_scores score
          JOIN phase4c_validation_occupations occupation ON occupation.id=score.validation_occupation_id
          WHERE score.calculation_run_id=$1 ORDER BY occupation.occupation_code
        """, latest_run)
        blocked = {row["occupation_code"]: row for row in rows if not row["scale_eligible"]}
        assert set(blocked) == {"11-2022.00", "27-1024.00", "39-5012.00", "41-2031.00"}
        assert all(row["coverage_gate_status"] == "below_threshold" for row in blocked.values())
        assert all(float(row["weighted_task_coverage"]) < 70 for row in blocked.values())
        assert all(float(row["confidence_penalty"]) > 0 for row in blocked.values())
    finally:
        await connection.close()


async def test_phase4c_does_not_write_production_or_score_unmapped_tasks() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        counts = await connection.fetchrow("""
          SELECT (SELECT count(*) FROM occupation_scores) production_occupations,
                 (SELECT count(*) FROM task_ai_scores) production_tasks,
                 (SELECT count(*) FROM phase4c_task_mapping_scope WHERE ai_task_mapping_id IS NULL) unmapped_scope,
                 (SELECT count(*) FROM phase4c_task_assessments assessment
                   JOIN phase4c_task_mapping_scope scope ON scope.onet_task_id=assessment.onet_task_id
                   WHERE scope.ai_task_mapping_id IS NULL) scored_without_mapping
        """)
        assert dict(counts) == {
            "production_occupations": 11,
            "production_tasks": 23,
            "unmapped_scope": 78,
            "scored_without_mapping": 0,
        }
    finally:
        await connection.close()


async def test_admin_phase4c_exposes_cross_occupation_validation() -> None:
    auth = (os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "change-me-too"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/phase4c", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert len(data["occupations"]) == 25
    assert len(data["pairwise_results"]) == 24
    assert len(data["absolute_results"]) > 30
    assert sum(item["passed"] for item in data["pairwise_results"]) == 22
    assert data["runs"][0]["replay_matches_previous"] is True
    assert data["cohort"]["reused_mappings"] == 281
    assert data["cohort"]["new_mapping_rows"] == 218
    assert data["isolation"]["runs_with_ai_calls"] == 0
