import json
import os

import asyncpg
import pytest

from scoring.calibration import automation_feasibility_v2, capability_fit_v2

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@postgres:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


async def test_phase4b_is_same_cohort_mapping_only_and_exact_replay() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        rows = await connection.fetch("""
          SELECT run_version,run_kind,mapping_run_id,new_ai_mapping_calls,reused_mapping_count,
                 task_assessment_count,occupation_score_count,reconciliation_status,
                 replay_matches_previous,baseline_run_id,proxy_model_version_id,provenance
          FROM phase4a_calculation_runs WHERE methodology_phase='4B' ORDER BY id
        """)
        assert [row["run_version"] for row in rows] == [
            "phase4b-calibration-v1-2026q3", "phase4b-replay-v1-2026q3",
            "phase4b-calibration-v1.1-2026q3", "phase4b-replay-v1.1-2026q3",
        ]
        assert len({row["mapping_run_id"] for row in rows}) == 1
        assert all(row["mapping_run_id"] == 7 for row in rows)
        assert all(row["new_ai_mapping_calls"] == 0 for row in rows)
        assert all(row["reused_mapping_count"] == 230 for row in rows)
        assert all(row["task_assessment_count"] == 230 for row in rows)
        assert all(row["occupation_score_count"] == 12 for row in rows)
        assert all(row["reconciliation_status"] == "passed" for row in rows)
        assert rows[1]["replay_matches_previous"] is True
        assert rows[3]["replay_matches_previous"] is True
        assert len({row["baseline_run_id"] for row in rows}) == 1
        assert len({row["proxy_model_version_id"] for row in rows}) == 1
        assert all(_json(row["provenance"])["productionScoreWrites"] == 0 for row in rows)

        mismatch = await connection.fetchval("""
          WITH first AS (
            SELECT assessment.* FROM phase4a_task_assessments assessment
            JOIN phase4a_calculation_runs run ON run.id=assessment.calculation_run_id
            WHERE run.run_version='phase4b-calibration-v1.1-2026q3'
          ), replay AS (
            SELECT assessment.* FROM phase4a_task_assessments assessment
            JOIN phase4a_calculation_runs run ON run.id=assessment.calculation_run_id
            WHERE run.run_version='phase4b-replay-v1.1-2026q3'
          )
          SELECT count(*) FROM first FULL JOIN replay USING (onet_task_id)
          WHERE first.input_hash IS DISTINCT FROM replay.input_hash
             OR first.ai_capability_fit IS DISTINCT FROM replay.ai_capability_fit
             OR first.automation_feasibility IS DISTINCT FROM replay.automation_feasibility
             OR first.augmentation_potential IS DISTINCT FROM replay.augmentation_potential
             OR first.task_ai_exposure IS DISTINCT FROM replay.task_ai_exposure
             OR first.confidence IS DISTINCT FROM replay.confidence
        """)
        assert mismatch == 0
    finally:
        await connection.close()


async def test_proxy_snapshots_are_versioned_provenance_aware_and_reconciled() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        rows = await connection.fetch("""
          SELECT snapshot.*,model.model_version,source.name source_name
          FROM phase4b_occupation_proxy_snapshots snapshot
          JOIN phase4b_proxy_model_versions model ON model.id=snapshot.proxy_model_version_id
          JOIN data_sources source ON source.id=snapshot.source_id ORDER BY snapshot.id
        """)
        assert len(rows) == 12
        for row in rows:
            assert row["model_version"] == "phase4b-occupation-proxy-v1"
            assert row["source_name"] == "JobsVsAI Phase 4B calibration"
            assert len(row["input_hash"].strip()) == 64
            assert _json(row["reconciliation"])["passed"]
            inputs = _json(row["exact_inputs"])
            assert inputs["proxyModelVersion"] == "phase4b-occupation-proxy-v1"
            assert inputs["sourceRatings"]
            assert inputs["sourcePolicy"]["excluded"] == [
                "phase1_seed_market_signals", "production_scores", "downstream_automation_outcomes"
            ]
            domains = _json(row["domain_values"])
            assert set(domains) == {
                "physical-presence", "environment-variability", "human-dependency",
                "regulation", "accountability", "consequence-severity",
            }
            assert 0 <= float(row["proxy_confidence"]) <= 60
    finally:
        await connection.close()


async def test_phase4b_coverage_gates_and_confidence_penalties_are_enforced() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        rows = await connection.fetch("""
          SELECT pilot.occupation_code,score.weighted_task_coverage,score.coverage_gate_status,
                 score.confidence_penalty,score.scale_eligible,score.warnings
          FROM phase4a_occupation_scores score
          JOIN phase4a_calculation_runs run ON run.id=score.calculation_run_id
          JOIN phase4a_pilot_occupations pilot ON pilot.id=score.pilot_occupation_id
          WHERE run.run_version='phase4b-calibration-v1.1-2026q3'
          ORDER BY pilot.occupation_code
        """)
        assert len(rows) == 12
        blocked = {row["occupation_code"]: row for row in rows if not row["scale_eligible"]}
        assert set(blocked) == {"11-2022.00", "27-1024.00"}
        for row in blocked.values():
            assert float(row["weighted_task_coverage"]) < 70
            assert row["coverage_gate_status"] == "below_threshold"
            assert float(row["confidence_penalty"]) > 0
            assert any(
                warning["code"] == "weighted_coverage_below_threshold"
                for warning in _json(row["warnings"])
            )
        assert all(
            row["coverage_gate_status"] == "passed" and float(row["confidence_penalty"]) == 0
            for row in rows if row["occupation_code"] not in blocked
        )
    finally:
        await connection.close()


async def test_phase4b_diagnostics_show_desaturation_and_reconcile() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        rows = await connection.fetch("""
          SELECT metric_scope,metric_name,baseline_summary,calibrated_summary,delta_summary,reconciliation
          FROM phase4b_distribution_diagnostics
          WHERE calibration_run_id=(SELECT max(calibration_run_id) FROM phase4b_distribution_diagnostics)
          ORDER BY metric_scope,metric_name
        """)
        assert len(rows) == 7
        by_name = {row["metric_name"]: row for row in rows}
        for row in rows:
            reconciliation = _json(row["reconciliation"])
            expected = 230 if row["metric_scope"] == "task" else 12
            assert reconciliation == {
                "baselineCount": expected, "calibratedCount": expected, "passed": True
            }
        for metric in ("ai_capability_fit", "automation_feasibility", "task_ai_exposure"):
            baseline = _json(by_name[metric]["baseline_summary"])
            calibrated = _json(by_name[metric]["calibrated_summary"])
            assert calibrated["atOrAbove90"] < baseline["atOrAbove90"]
            assert calibrated["mean"] < baseline["mean"]
        automation = by_name["automation_feasibility"]
        assert _json(automation["baseline_summary"])["atOrAbove90"] == 179
        assert _json(automation["calibrated_summary"])["atOrAbove90"] == 1
        assert _json(automation["delta_summary"])["mean"] == pytest.approx(-29.2301)
    finally:
        await connection.close()


async def test_v2_formulas_apply_smooth_fit_and_constraint_bottlenecks() -> None:
    parameters = {
        "logisticSlope": 14, "geometricFloor": .5, "criticalWeightThreshold": .35,
        "criticalSecondaryWeightThreshold": .2, "criticalRequiredLevelThreshold": 70,
        "bottleneckMatchThreshold": 50, "bottleneckHeadroom": 8,
    }
    fit = capability_fit_v2(
        [{"slug": "general", "weight": 1, "requiredLevel": 50, "mappingConfidence": 90}],
        {"general": {"entryId": 1, "score": 50, "confidence": 80, "evidenceIds": [1]}},
        parameters,
    )
    assert fit["score"] == pytest.approx(50)
    assert fit["score"] < 100
    automation = automation_feasibility_v2(95, [{
        "slug": "consequence-severity", "level": 90, "confidence": 60,
        "source": "occupation_metadata_proxy", "fixedWeight": 1, "evidence": [],
    }], {
        "constraintExponent": 1.35, "capabilityFitWeight": .5,
        "constraintResistanceWeight": .5, "criticalConstraintThreshold": 65,
        "bottleneckCapStrength": {"consequence-severity": .7},
        "maximumProxyConfidencePenalty": 18, "proxyUsagePenaltyWeight": 10,
        "proxyUncertaintyPenaltyWeight": 8,
    })
    assert automation["score"] == pytest.approx(37)
    assert automation["preBottleneckScore"] > automation["score"]
    assert automation["proxyConfidencePenalty"] > 0


async def test_phase4b_remains_isolated_from_public_and_production_scores() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        counts = await connection.fetchrow("""
          SELECT (SELECT count(*) FROM occupation_scores) production_occupations,
                 (SELECT count(*) FROM task_ai_scores) production_tasks,
                 (SELECT count(*) FROM ai_generated_task_mappings mapping
                   JOIN ai_generated_task_mapping_runs run ON run.id=mapping.mapping_run_id
                   WHERE run.run_version='phase4a-pilot-mapper-v1-2026q3') frozen_mappings,
                 (SELECT count(*) FROM phase4b_occupation_proxy_snapshots) proxy_snapshots
        """)
        assert dict(counts) == {
            "production_occupations": 11, "production_tasks": 23,
            "frozen_mappings": 281, "proxy_snapshots": 12,
        }
    finally:
        await connection.close()
