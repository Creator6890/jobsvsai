import json
import os

import asyncpg
import pytest


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@postgres:5432/jobsvsai").replace(
        "postgresql+asyncpg://", "postgresql://", 1,
    )


@pytest.mark.asyncio
async def test_benchmark_frame_is_diverse_but_pending_real_human_review() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("""
          SELECT * FROM task_mapper_benchmark_validation
          WHERE dataset_version='gold-v1-175-pending-human-review'
        """)
        assert row["status"] == "draft"
        assert row["tasks"] == 175
        assert 25 <= row["occupations"] <= 30
        assert row["mappable_tasks"] > 0
        assert row["ambiguous_tasks"] > 0
        assert row["insufficient_tasks"] > 0
        assert row["human_reviewed_tasks"] == 0
        assert row["independently_human_reviewed_tasks"] == 0
        assert row["adjudicated_tasks"] == 0
        review_kinds = await connection.fetchrow("""
          SELECT count(*) reviews,count(*) FILTER (WHERE reviewer_kind='human') human_reviews,
                 bool_and((review.provenance->>'counts_as_gold')::boolean=false) non_gold
          FROM task_mapping_gold_review_events review
          JOIN task_capability_gold_items item ON item.id=review.gold_item_id
          JOIN task_capability_gold_datasets dataset ON dataset.id=item.gold_dataset_id
          WHERE dataset.dataset_version='gold-v1-175-pending-human-review'
        """)
        assert dict(review_kinds) == {"reviews": 175, "human_reviews": 0, "non_gold": True}
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_candidate_mapper_is_complete_score_blind_and_non_activating() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        run = await connection.fetchrow("""
          SELECT run.*,validation.*
          FROM task_mapping_candidate_runs run
          CROSS JOIN LATERAL candidate_run_validation(run.id) validation
          WHERE run.run_version='draft-rules-v1-175-20260820'
        """)
        manifest = json.loads(run["allowed_input_manifest"])
        assert run["status"] == "completed"
        assert run["input_task_count"] == run["output_task_count"] == run["total_tasks"] == 175
        assert run["prohibited_input_attestation"] is True
        assert "occupation_scores" in manifest["prohibited"]
        assert "task_ai_scores" in manifest["prohibited"]
        assert run["invalid_tasks"] == 0
        false_inference_rows = await connection.fetchval("""
          SELECT count(*) FROM candidate_task_mappings candidate
          WHERE candidate.candidate_run_id=$1 AND candidate.disposition<>'mappable' AND (
            EXISTS (SELECT 1 FROM candidate_task_capability_requirements requirement WHERE requirement.candidate_task_mapping_id=candidate.id)
            OR EXISTS (SELECT 1 FROM candidate_task_environment_constraints constraint_mapping WHERE constraint_mapping.candidate_task_mapping_id=candidate.id)
          )
        """, run["id"])
        assert false_inference_rows == 0
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_independent_verification_pass_reconciles_all_candidates() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("""
          SELECT verification.* FROM task_mapping_verification_runs verification
          JOIN task_mapping_candidate_runs candidate ON candidate.id=verification.candidate_run_id
          WHERE candidate.run_version='draft-rules-v1-175-20260820' AND verification.status='passed'
          ORDER BY verification.created_at DESC,verification.id DESC LIMIT 1
        """)
        summary = json.loads(row["summary"])
        assert row["independent_implementation_attestation"] is True
        assert summary["tasksChecked"] == 175
        assert summary["errors"] == 0
        assert summary["falseInferenceFindings"] == 0
        assert summary["taskHashesReconciled"] is True
        assert summary["scoreBlindAttestationPresent"] is True
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_aggregate_metrics_and_configurable_acceptance_gates_are_persisted() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        evaluation = await connection.fetchrow("""
          SELECT evaluation.*,gate.minimum_human_reviewed_tasks,gate.minimum_occupations,
                 gate.minimum_capability_set_agreement,gate.maximum_false_inference_rate
          FROM task_mapper_evaluation_runs evaluation
          JOIN mapper_acceptance_gate_configs gate ON gate.id=evaluation.gate_config_id
          WHERE evaluation.evaluation_version='evaluation-v1-run1-controls'
        """)
        metrics = json.loads(evaluation["metrics"])
        gates = json.loads(evaluation["gate_results"])
        assert evaluation["status"] == "ineligible"
        assert evaluation["minimum_human_reviewed_tasks"] == 150
        assert evaluation["minimum_occupations"] == 25
        assert set(metrics) == {
            "capabilitySetAgreement", "meanWeightDeviation", "meanRequirementLevelDeviation",
            "meanConstraintDeviation", "confidenceAgreement", "extraDimensions",
            "missingDimensions", "extraDimensionRate", "missingDimensionRate",
            "falseInferenceCount", "falseInferenceRate", "dispositionAgreement",
        }
        assert metrics["falseInferenceRate"] == 0
        assert gates["minimumHumanReviewedTasks"] is False
        assert gates["independentVerification"] is True
        assert gates["falseInference"] is True
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_mapper_work_remains_isolated_from_taxonomy_activation_and_scores() -> None:
    connection = await asyncpg.connect(_database_url())
    try:
        row = await connection.fetchrow("""
          SELECT
            (SELECT count(*) FROM ai_capability_taxonomy_versions WHERE status='active') active_taxonomies,
            (SELECT count(*) FROM ai_capability_benchmark_scores) benchmark_scores,
            (SELECT count(*) FROM task_ai_enrichment_assessments) assessments,
            (SELECT count(*) FROM occupation_scores) occupation_scores,
            (SELECT count(*) FROM task_ai_scores) legacy_task_scores,
            (SELECT count(*) FROM scoring_jobs WHERE status IN ('queued','running')) active_scoring_jobs,
            (SELECT count(*) FROM task_capability_mapping_sets) activated_or_fixture_mapping_sets
        """)
        assert row["active_taxonomies"] == 0
        assert row["benchmark_scores"] == row["assessments"] == row["active_scoring_jobs"] == 0
        assert row["occupation_scores"] == 11 and row["legacy_task_scores"] == 23
        assert row["activated_or_fixture_mapping_sets"] == 3
    finally:
        await connection.close()
