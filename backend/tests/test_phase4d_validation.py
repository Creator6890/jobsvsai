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


async def test_phase4d_v2_formulas_are_versioned_direct_and_title_blind() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        models = await connection.fetch("SELECT * FROM phase4d_proxy_model_versions ORDER BY id")
        assert [row["model_version"] for row in models] == [
            "phase4d-direct-structural-proxy-v1", "phase4d-direct-structural-proxy-v2"
        ]
        latest = models[-1]
        assert decoded(latest["reconstructed_families"]) == [
            "physical-presence", "environment-variability", "accountability", "consequence-severity"
        ]
        policy = decoded(latest["missing_data_policy"])
        assert policy["imputation"] == "prohibited"
        assert policy["inventedValues"] is False
        provenance = decoded(latest["provenance"])
        assert provenance["occupationTitleUsed"] is False
        assert provenance["socUsedAsFormulaInput"] is False
        assert provenance["archetypeScoring"] is False
        parameters = decoded(latest["formula_parameters"])
        assert parameters["consequence-severity"]["clinicalGate"]["required"].endswith(
            "title and SOC are prohibited"
        )
    finally:
        await connection.close()


async def test_phase4d_snapshots_expose_exact_sources_and_reconcile() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        model_id = await connection.fetchval(
            "SELECT id FROM phase4d_proxy_model_versions WHERE model_version='phase4d-direct-structural-proxy-v2'"
        )
        rows = await connection.fetch(
            "SELECT * FROM phase4d_proxy_snapshots WHERE proxy_model_version_id=$1 ORDER BY validation_occupation_id",
            model_id,
        )
        assert len(rows) == 25
        clinical_codes = set()
        for row in rows:
            families = decoded(row["family_values"])
            assert set(families) == {
                "physical-presence", "environment-variability", "accountability", "consequence-severity"
            }
            assert decoded(row["reconciliation"])["passed"] is True
            exact = decoded(row["exact_inputs"])
            assert "occupation_title" in exact["prohibitedInputs"]
            assert "archetype_membership" in exact["prohibitedInputs"]
            assert exact["sourceRecordHashes"]
            assert exact["taskRecordHashes"]
            for family in families.values():
                assert family["reconciliation"]["passed"] is True
                normalized = family["reconciliation"].get(
                    "normalizedUsedWeightTotal",
                    family["reconciliation"].get("base", {}).get("normalizedUsedWeightTotal"),
                )
                assert abs(normalized - 1.0) < .000001
                assert family["missingDataPolicy"]
                for component in family["components"]:
                    assert component["status"] in {"used", "missing", "suppressed"}
                    if component["status"] == "used":
                        assert component["transformedValue"] is not None
                        assert component["normalizedUsedWeight"] > 0
                        if component["kind"] == "element":
                            assert component["evidence"]["rowHash"]
                            assert component["evidence"]["sourceVersion"] == "30.3"
            if families["consequence-severity"]["clinicalGatePassed"]:
                code = await connection.fetchval(
                    "SELECT occupation_code FROM phase4c_validation_occupations WHERE id=$1",
                    row["validation_occupation_id"],
                )
                clinical_codes.add(code)
        assert clinical_codes == {"21-1022.00", "29-1141.00", "29-1171.00"}
    finally:
        await connection.close()


async def test_phase4d_replay_preserves_fit_coverage_and_production_isolation() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        model_id = await connection.fetchval(
            "SELECT id FROM phase4d_proxy_model_versions WHERE model_version='phase4d-direct-structural-proxy-v2'"
        )
        runs = await connection.fetch(
            "SELECT * FROM phase4d_calculation_runs WHERE proxy_model_version_id=$1 ORDER BY id", model_id
        )
        assert [row["run_kind"] for row in runs] == ["direct_proxy_recompute", "deterministic_replay"]
        assert runs[-1]["replay_matches_previous"] is True
        assert all(row["occupation_count"] == 25 and row["task_assessment_count"] == 407 for row in runs)
        assert all(row["external_ai_calls"] == 0 for row in runs)
        assert all(row["regenerated_mapping_count"] == 0 for row in runs)
        assert all(row["production_score_writes"] == 0 for row in runs)
        assert all(row["archetype_scoring_enabled"] is False for row in runs)
        latest_id = runs[-1]["id"]
        fit_changes = await connection.fetchval("""
          SELECT count(*) FROM phase4d_task_assessments current
          JOIN phase4c_task_assessments baseline
            ON baseline.ai_task_mapping_id=current.ai_task_mapping_id AND baseline.calculation_run_id=1
          WHERE current.calculation_run_id=$1
            AND current.ai_capability_fit<>baseline.ai_capability_fit
        """, latest_id)
        assert fit_changes == 0
        coverage_changes = await connection.fetchval("""
          SELECT count(*) FROM phase4d_occupation_scores current
          JOIN phase4c_occupation_scores baseline ON baseline.id=current.baseline_phase4c_score_id
          WHERE current.calculation_run_id=$1 AND (
            current.weighted_task_coverage<>baseline.weighted_task_coverage
            OR current.coverage_gate_status<>baseline.coverage_gate_status)
        """, latest_id)
        assert coverage_changes == 0
        blocked = await connection.fetch("""
          SELECT validation.occupation_code FROM phase4d_occupation_scores score
          JOIN phase4c_validation_occupations validation ON validation.id=score.validation_occupation_id
          WHERE score.calculation_run_id=$1 AND NOT score.scale_eligible
          ORDER BY validation.occupation_code
        """, latest_id)
        assert [row["occupation_code"] for row in blocked] == [
            "11-2022.00", "27-1024.00", "39-5012.00", "41-2031.00"
        ]
        isolation = await connection.fetchrow("""
          SELECT (SELECT count(*) FROM occupation_scores) occupation_rows,
                 (SELECT count(*) FROM task_ai_scores) task_rows,
                 (SELECT enabled FROM scoring_enrichment_feature_flags
                  WHERE flag_key='occupational_archetype_layer') archetype_enabled
        """)
        assert dict(isolation) == {
            "occupation_rows": 11, "task_rows": 23, "archetype_enabled": False
        }
    finally:
        await connection.close()


async def test_phase4d_materially_reduces_failures_without_reversals() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        run_id = await connection.fetchval(
            "SELECT id FROM phase4d_calculation_runs WHERE run_version='phase4d-direct-proxy-replay-v2-2026q3'"
        )
        counts = await connection.fetchrow("""
          SELECT count(*) FILTER (WHERE validation_type='absolute_band'
                                  AND baseline_outcome='failure') baseline_failures,
                 count(*) FILTER (WHERE validation_type='absolute_band'
                                  AND phase4d_outcome='failure') phase4d_failures,
                 count(*) FILTER (WHERE validation_type='pairwise'
                                  AND phase4d_outcome='pass') pairwise_passes,
                 count(*) FILTER (WHERE validation_type='pairwise'
                                  AND phase4d_outcome='warning') warnings,
                 count(*) FILTER (WHERE validation_type='pairwise'
                                  AND phase4d_outcome='failure') reversals,
                 count(*) FILTER (WHERE improved) improvements,
                 count(*) FILTER (WHERE regressed) regressions
          FROM phase4d_proxy_validation_results WHERE calculation_run_id=$1
        """, run_id)
        assert dict(counts) == {
            "baseline_failures": 13, "phase4d_failures": 3, "pairwise_passes": 23,
            "warnings": 1, "reversals": 0, "improvements": 11, "regressions": 0,
        }
        remaining = await connection.fetch(
            """SELECT validation_key,proxy_family FROM phase4d_proxy_validation_results
               WHERE calculation_run_id=$1 AND phase4d_outcome='failure' ORDER BY validation_key""",
            run_id,
        )
        assert [(row["validation_key"], row["proxy_family"]) for row in remaining] == [
            ("21-1022.00:regulation", "regulation"),
            ("27-3042.00:adoption-pressure", "adoption-pressure"),
            ("27-3042.00:labour-market-resilience", "labour-market-resilience"),
        ]
    finally:
        await connection.close()


async def test_admin_phase4d_exposes_full_direct_derivation() -> None:
    auth = (os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "change-me-too"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/phase4d", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["models"][0]["model_version"] == "phase4d-direct-structural-proxy-v2"
    assert data["runs"][0]["replay_matches_previous"] is True
    assert len(data["occupations"]) == 25
    assert len(data["validations"]) == 70
    assert data["summary"]["baseline_absolute_failures"] == 13
    assert data["summary"]["phase4d_absolute_failures"] == 3
    assert data["summary"]["pairwise_reversals"] == 0
    assert data["isolation"]["runs_with_production_writes"] == 0
    assert data["isolation"]["archetype_layer_enabled"] is False
    assert all(len(row["family_values"]) == 4 for row in data["occupations"])
